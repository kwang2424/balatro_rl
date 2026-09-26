"""Play N runs with the heuristic agent and report how far it gets.

Start the game first:   uvx balatrobot serve --fast
Then:                   python run_baseline.py --runs 20
"""

import argparse
import csv
import random
import string
import sys
from collections import Counter

from agent import Agent
from client import BalatroClient
from heuristics.hand import HandPolicy
from heuristics.shop import ShopPolicy

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
    args = ap.parse_args(argv)

    client = BalatroClient(args.host, args.port)
    try:
        client.health()
    except Exception as e:
        print(f"Can't reach BalatroBot at {client.url} ({e}).\n"
              f"Start it with: uvx balatrobot serve --fast", file=sys.stderr)
        return 1

    build = set() if args.no_flush else {"flush"}
    agent = Agent(client,
                  hand_policy=HandPolicy(chase_flush=not args.no_flush),
                  shop_policy=ShopPolicy(build=build))

    rows = []
    with open(args.out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for i, seed in enumerate(make_seeds(args.runs, args.seed), 1):
            row = agent.play_run(deck=args.deck, stake=args.stake, seed=seed)
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
