# Shop tuning 2: with planets and packs

After the shop learned to buy and use planets and open Buffoon/Celestial packs,
`tune_shop.py` was rerun starting from the first run's result:

```
tune_shop.py --init results/shop_tuning/tuned_shop_params.json --sigma 0.15 --seed 1 \
    --generations 25 --popsize 12 --runs-per-eval 100 --workers 4
```

Jackdaw simulator, Red deck, White stake, flush build, exact hand scoring. About
32,000 training runs in 45 minutes on 4 cores; no errors in the final 20
generations or the holdout runs (one errored run in generation 2).

## Holdout result

The same 1,000 unseen seeds as `results/shop_tuning` (`run_baseline.py --sim --seed 1000003`):

| Version | Blinds cleared | Mean ante | Ante 5+ | Ante 7+ | Wins |
|---|---|---|---|---|---|
| Original defaults, no planets/packs | 9.28 | 3.63 | 23% | 1% | 1 |
| Tuning run 1, no planets/packs | 10.38 | 3.98 | 34% | 2% | 0 |
| Defaults + planets/packs | 10.23 | 3.93 | 31% | 3% | 1 |
| Tuning run 1 + planets/packs | 11.72 | 4.40 | 49% | 4% | 1 |
| **Tuning run 2** (`tuned_shop_params.json`) | **13.28** | **4.91** | **63%** | **12%** | **13** |

Tuning run 2 vs tuning run 1 + planets/packs: **+1.56 blinds per run (95% CI
±0.24)**, paired on the same seeds. Versus the original defaults: +3.99 ± 0.29.
The tuner's own holdout on a different 1,000 seeds agrees (13.27 blinds,
0.9% wins).

## What changed

The consistent theme is **spend more**:

- Planets are worth far more (`planet_value` 6 → 13.6), with a bigger head
  start for the build's hand (`build_hand_prior` 5 → 9.4).
- A lower savings target (`reserve` 25 → 18, below full interest) and a lower
  bar for buying anything (`buy_threshold` 3 → 0.45).
- More rerolls (`reroll_reserve` 34 → 16).
- Buffoon packs up (4 → 7.3); jumbo/mega packs barely worth more than normal
  ones (`big_pack_bonus` 1 → 0.2).
- Economy jokers down further (`econ_early` −0.2 → −2.7); foil/holo editions up.

The tier values moved in opposite directions from run 1 (A 7.5 → 4.3 → 8.1,
S 10 → 11.6 → 7.7), so they are mostly fitting noise. Only a handful of jokers
are S or A tier, so these values have little data behind them.

## Files

- `tuned_shop_params.json`: the parameters, plus the tuner's own holdout numbers.
- `holdout_*.csv`: per-run results on seeds 1000003 for the rows above.
- `tune_log.csv`, `tune_output.txt`: per-generation progress.
