# Shop tuning: first CMA-ES run

`tune_shop.py --generations 25 --popsize 12 --runs-per-eval 100 --workers 4`
on the jackdaw simulator (commit e66de78), Red deck, White stake, flush build,
exact hand scoring. About 32,000 training runs in 42 minutes on 4 cores.

## Holdout result

1,000 seeds the tuner never saw (`run_baseline.py --sim --seed 1000003`), same
seeds for both, rerun after the Cerulean Bell fix:

| Shop params | Blinds cleared | Mean ante | Reached ante 5+ | Wins |
|---|---|---|---|---|
| Defaults | 9.28 | 3.63 | 23.3% | 1 |
| Tuned (`tuned_shop_params.json`) | **10.38** | **3.98** | **34.1%** | 0 |

Paired difference: **+1.10 blinds per run (95% CI ±0.21)**. Tuned did better on
426 seeds, worse on 196, and tied on 378. Wins stay near zero either way.

Files: `tuned_shop_params.json` (params plus the tuner's own holdout numbers),
`holdout_defaults.csv` and `holdout_tuned.csv` (per-run results),
`tune_log.csv` and `tune_output.txt` (per-generation progress).

## What changed

With noisy evaluation, only large moves are worth reading into:

- **Money:** no savings reserve until ante ~6 (`early_antes` 2 → 5.9), then
  keep the full interest reserve and almost never break it
  (`reserve_break_value` 8 → 14.7). Spend early, bank late.
- **Economy jokers devalued** (`econ_early` +2 → −0.2, `econ_late` −2 → −3.9).
  For this bot, a slot is worth more for scoring than for income.
- **Early game wants immediate points:** flat chips/mult up
  (`chips_mult_early` 1 → 2.8); scaling and xmult jokers down early
  (`scaling_early` 1.5 → −0.6, `xmult_early` −0.5 → −2.4).
- **Build synergy matters more** (`build_bonus` 2 → 4.1): flush jokers are worth
  much more to a bot that plays flushes.
- **The tier list got flattened:** A down (7.5 → 4.3), B and C up (5 → 7.9,
  3 → 5.6), D down (1 → −1.6). The community A-tier jokers aren't reliably
  better than B/C ones for this bot. Per-joker values would be the next
  refinement.

## Caveats

- Tuned for the simulator with exact hand scoring. The live game uses the
  estimate-based hand policy; `tune_shop.py --no-exact-scoring` tunes for that.
- The simulator's fidelity is jackdaw's claim; confirm with live runs.
- The defaults in `ShopParams` are unchanged. Use `--shop-params` to opt in.
