"""Play N runs with the heuristic agent and report how far it gets.

Live game:  start it with `uvx balatrobot serve --fast`, then
            python run_baseline.py --runs 20
Simulator:  python run_baseline.py --sim --runs 500 --workers 8
            (needs jackdaw, see sim_client.py)
"""

import argparse
import csv
import json
import multiprocessing
import random
import string
import sys
from collections import Counter

from agent import Agent
from client import BalatroClient
from heuristics.hand import HandPolicy
from heuristics.shop import ShopParams, ShopPolicy

FIELDS = ["seed", "deck", "stake", "won", "ante", "round", "money", "jokers",
          "steps", "seconds", "error"]


def make_seeds(n, base_seed):
    rng = random.Random(base_seed)
    alphabet = string.ascii_uppercase + string.digits
    return ["".join(rng.choices(alphabet, k=8)) for _ in range(n)]


def summarize(rows):
    n = len(rows)
    if not n:
        return "no runs"
    wins = sum(r["won"] for r in rows)
    antes = [r["ante"] or 0 for r in rows]
    dist = Counter(antes)
    lines = [
        f"runs: {n}   wins: {wins} ({100 * wins / n:.0f}%)   "
        f"mean ante: {sum(antes) / n:.2f}   errors: {sum(bool(r['error']) for r in rows)}",
        "ante reached: " + "  ".join(f"{a}:{dist[a]}" for a in sorted(dist)),
    ]
    return "\n".join(lines)


def build_agent(args, client):
    build = set() if args.no_flush else {"flush"}
    scorer = getattr(client, "score_plays", None) if args.exact_scoring else None
    return Agent(client,
                 hand_policy=HandPolicy(chase_flush=not args.no_flush, scorer=scorer),
                 shop_policy=ShopPolicy(load_shop_params(args.shop_params), build=build),
                 log=lambda *_: None)


def load_shop_params(path):
    """ShopParams from a tune_shop.py output file (or defaults if path is None)."""
    if not path:
        return ShopParams()
    with open(path) as f:
        data = json.load(f)
    return ShopParams(**data.get("params", data))


_worker_agent = None


def _init_worker(args):
    global _worker_agent
    from sim_client import SimClient
    _worker_agent = build_agent(args, SimClient())


def _play_seed(job):
    seed, deck, stake = job
    return _worker_agent.play_run(deck=deck, stake=stake, seed=seed)


def iter_runs(args, seeds):
    """Yield one result row per seed, in order."""
    jobs = [(seed, args.deck, args.stake) for seed in seeds]
    if args.sim and args.workers > 1:
        with multiprocessing.Pool(args.workers, _init_worker, (args,)) as pool:
            yield from pool.imap(_play_seed, jobs)
        return
    if args.sim:
        _init_worker(args)
    else:
        global _worker_agent
        _worker_agent = build_agent(args, BalatroClient(args.host, args.port))
    for job in jobs:
        yield _play_seed(job)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--deck", default="RED")
    ap.add_argument("--stake", default="WHITE")
    ap.add_argument("--seed", type=int, default=0,
                    help="base seed for generating the run seeds (same value = same runs)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=12346)
    ap.add_argument("--out", default="baseline_results.csv")
    ap.add_argument("--no-flush", action="store_true",
                    help="don't chase flushes or favor flush jokers")
    ap.add_argument("--sim", action="store_true",
                    help="play on the jackdaw simulator instead of the live game")
    ap.add_argument("--workers", type=int, default=1,
                    help="parallel simulator processes (--sim only)")
    ap.add_argument("--no-exact-scoring", dest="exact_scoring", action="store_false",
                    help="with --sim, rank plays by the joker-blind estimate instead of "
                         "simulating them (matches what the live game can do)")
    ap.add_argument("--shop-params", help="JSON file from tune_shop.py")
    args = ap.parse_args(argv)

    if args.sim:
        try:
            import sim_client  # noqa: F401
        except ImportError as e:
            print(e, file=sys.stderr)
            return 1
    else:
        client = BalatroClient(args.host, args.port)
        try:
            client.health()
        except Exception as e:
            print(f"Can't reach BalatroBot at {client.url} ({e}).\n"
                  f"Start it with: uvx balatrobot serve --fast, or use --sim",
                  file=sys.stderr)
            return 1

    seeds = make_seeds(args.runs, args.seed)
    rows = []
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, (seed, row) in enumerate(zip(seeds, iter_runs(args, seeds)), 1):
            rows.append(row)
            writer.writerow(row)
            f.flush()
            status = "WON" if row["won"] else f"ante {row['ante']}"
            err = f"  error: {row['error']}" if row["error"] else ""
            print(f"[{i}/{args.runs}] {seed}: {status}  ${row['money']}  "
                  f"jokers: {row['jokers'] or '-'}  ({row['seconds']}s){err}")

    print()
    print(summarize(rows))
    print(f"results written to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
