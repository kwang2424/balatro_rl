"""Tune ShopParams on the jackdaw simulator with CMA-ES.

Each generation draws a fresh batch of training seeds, plays every candidate
parameter set on that same batch (so candidates are compared on equal luck),
and maximizes blinds cleared per run. At the end, the defaults and the best
parameters are compared on a separate set of holdout seeds.

    pip install cma
    python tune_shop.py --generations 25 --runs-per-eval 100 --workers 8

Writes the best parameters to tuned_shop_params.json (use them with
`run_baseline.py --shop-params tuned_shop_params.json`) and a per-generation
log to tune_log.csv. Needs jackdaw (see sim_client.py).
"""

import argparse
import csv
import json
import multiprocessing
import sys
import time
from dataclasses import asdict, fields

from heuristics.shop import ShopParams, ShopPolicy
from run_baseline import make_seeds

# Search range for each parameter. CMA-ES works in [0, 1] per parameter.
RANGES = {
    "tier_s": (0, 15), "tier_a": (0, 12), "tier_b": (0, 10), "tier_c": (0, 8),
    "tier_d": (-2, 6),
    "econ_early": (-3, 5), "econ_late": (-5, 3),
    "xmult_early": (-3, 3), "xmult_late": (-1, 6),
    "scaling_early": (-2, 4), "scaling_late": (-4, 2),
    "chips_mult_early": (-1, 3),
    "build_bonus": (0, 5), "shared_tag_bonus": (0, 3), "copy_per_xmult_owned": (0, 3),
    "setup_penalty": (0, 6), "risky_penalty": (0, 4), "rental_penalty": (0, 5),
    "foil_bonus": (0, 3), "holo_bonus": (0, 4), "polychrome_bonus": (0, 6),
    "cost_weight": (0, 0.6), "early_reserve": (0, 25), "reserve": (0, 50),
    "early_antes": (0, 6), "reserve_break_value": (3, 15),
    "buy_threshold": (-2, 8), "replace_margin": (0, 6), "voucher_threshold": (0, 12),
    "reroll_reserve": (0, 60), "max_rerolls": (0, 6),
}
NAMES = [f.name for f in fields(ShopParams)]
assert set(RANGES) == set(NAMES), set(NAMES) ^ set(RANGES)

HOLDOUT_BASE_SEED = 1_000_003  # far from the training seeds


def to_unit(params):
    return [(getattr(params, n) - RANGES[n][0]) / (RANGES[n][1] - RANGES[n][0]) for n in NAMES]


def from_unit(x):
    vals = {}
    for n, v in zip(NAMES, x):
        lo, hi = RANGES[n]
        vals[n] = lo + min(max(float(v), 0.0), 1.0) * (hi - lo)
    return ShopParams(**vals)


def blinds_cleared(row):
    return max((row["round"] or 1) - 1, 0) + (1 if row["won"] else 0)


# ---------- parallel evaluation ----------

_agent = None
_build = _deck = _stake = None


def _init_worker(exact_scoring, build, deck, stake):
    global _agent, _build, _deck, _stake
    from agent import Agent
    from heuristics.hand import HandPolicy
    from sim_client import SimClient

    client = SimClient()
    scorer = client.score_plays if exact_scoring else None
    _agent = Agent(client, hand_policy=HandPolicy(chase_flush="flush" in build, scorer=scorer),
                   log=lambda *_: None)
    _build, _deck, _stake = build, deck, stake


def _run(job):
    params_vec, seed = job
    _agent.shop_policy = ShopPolicy(ShopParams.from_vector(params_vec), build=_build)
    row = _agent.play_run(deck=_deck, stake=_stake, seed=seed)
    return blinds_cleared(row), row["ante"] or 0, bool(row["won"]), bool(row["error"])


def evaluate(pool, workers, param_sets, seeds):
    """Mean (blinds cleared, ante, win rate, errors) for each parameter set."""
    jobs = [(p.to_vector(), s) for p in param_sets for s in seeds]
    results = pool.map(_run, jobs, chunksize=max(1, len(jobs) // (workers * 8)))
    out, n = [], len(seeds)
    for i in range(len(param_sets)):
        chunk = results[i * n:(i + 1) * n]
        out.append((sum(r[0] for r in chunk) / n, sum(r[1] for r in chunk) / n,
                    sum(r[2] for r in chunk) / n, sum(r[3] for r in chunk)))
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--generations", type=int, default=25)
    ap.add_argument("--popsize", type=int, default=12)
    ap.add_argument("--runs-per-eval", type=int, default=100,
                    help="training seeds per candidate per generation")
    ap.add_argument("--holdout-runs", type=int, default=1000)
    ap.add_argument("--sigma", type=float, default=0.2, help="initial step size in [0,1] units")
    ap.add_argument("--workers", type=int, default=multiprocessing.cpu_count())
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--deck", default="RED")
    ap.add_argument("--stake", default="WHITE")
    ap.add_argument("--no-flush", action="store_true")
    ap.add_argument("--no-exact-scoring", dest="exact_scoring", action="store_false",
                    help="tune for the live-game hand policy (joker-blind estimate)")
    ap.add_argument("--out", default="tuned_shop_params.json")
    ap.add_argument("--log", default="tune_log.csv")
    args = ap.parse_args(argv)

    try:
        import cma
        import sim_client  # noqa: F401
    except ImportError as e:
        print(e, file=sys.stderr)
        return 1

    build = () if args.no_flush else ("flush",)
    default = ShopParams()
    es = cma.CMAEvolutionStrategy(
        to_unit(default), args.sigma,
        {"bounds": [0, 1], "popsize": args.popsize, "seed": args.seed + 1, "verbose": -9})

    best = (float("-inf"), default)
    t0 = time.time()
    with multiprocessing.Pool(args.workers, _init_worker,
                              (args.exact_scoring, build, args.deck, args.stake)) as pool, \
            open(args.log, "w", newline="") as logf:
        log = csv.writer(logf)
        log.writerow(["generation", "best_blinds", "mean_blinds", "default_blinds",
                      "best_ante", "best_winrate", "errors", "seconds"])
        for gen in range(1, args.generations + 1):
            seeds = make_seeds(args.runs_per_eval, args.seed * 100_000 + gen)
            xs = es.ask()
            candidates = [from_unit(x) for x in xs]
            # Include the defaults each generation as a reference point.
            scores = evaluate(pool, args.workers, candidates + [default], seeds)
            ref = scores.pop()
            es.tell(xs, [-s[0] for s in scores])  # cma minimizes

            i = max(range(len(scores)), key=lambda k: scores[k][0])
            gen_best = scores[i]
            margin = gen_best[0] - ref[0]
            if gen_best[0] > best[0]:
                best = (gen_best[0], candidates[i])
            errors = sum(s[3] for s in scores) + ref[3]
            elapsed = time.time() - t0
            mean = sum(s[0] for s in scores) / len(scores)
            log.writerow([gen, f"{gen_best[0]:.3f}", f"{mean:.3f}", f"{ref[0]:.3f}",
                          f"{gen_best[1]:.3f}", f"{gen_best[2]:.3f}", errors, int(elapsed)])
            logf.flush()
            print(f"gen {gen:2d}: best {gen_best[0]:.2f} blinds (ante {gen_best[1]:.2f}), "
                  f"population mean {mean:.2f}, defaults {ref[0]:.2f} "
                  f"({margin:+.2f})  errors {errors}  [{elapsed:.0f}s]", flush=True)

        # CMA-ES's mean is a less noisy pick than the single luckiest candidate.
        tuned = from_unit(es.result.xfavorite)
        holdout = make_seeds(args.holdout_runs, HOLDOUT_BASE_SEED + args.seed)
        print(f"\nholdout: {args.holdout_runs} unseen seeds ...", flush=True)
        d, t, b = evaluate(pool, args.workers, [default, tuned, best[1]], holdout)

    def fmt(r):
        return f"{r[0]:.2f} blinds, ante {r[1]:.2f}, wins {100 * r[2]:.1f}%, errors {r[3]}"

    print(f"  defaults:           {fmt(d)}")
    print(f"  tuned (CMA mean):   {fmt(t)}")
    print(f"  best single sample: {fmt(b)}")
    winner = max([("tuned", t, tuned), ("best_sample", b, best[1]), ("defaults", d, default)],
                 key=lambda w: w[1][0])
    with open(args.out, "w") as f:
        json.dump({
            "params": asdict(winner[2]),
            "picked": winner[0],
            "holdout": {"runs": args.holdout_runs, "defaults": d, "tuned": t, "best_sample": b},
            "settings": vars(args),
        }, f, indent=2)
    print(f"wrote {winner[0]} parameters to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
