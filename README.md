# balatro_rl

An attempt at using reinforcement learning to train an agent to play Balatro.

The game is driven through the [BalatroBot](https://github.com/coder/balatrobot)
mod, which exposes a JSON-RPC API on `127.0.0.1:12346`. This repo contains only
the Python side: an API client, heuristic policies, a baseline runner and a
Gymnasium environment.

## Setup

1. Install [Lovely Injector](https://github.com/ethangreen-dev/lovely-injector),
   [Steamodded](https://github.com/Steamodded/smods/wiki) and
   [uv](https://docs.astral.sh/uv).
2. Install the BalatroBot mod by following its
   [installation guide](https://coder.github.io/balatrobot/installation/).
3. Start the game with the mod:
   ```
   uvx balatrobot==1.5.2 serve --fast
   ```
4. Check that it responds:
   ```
   python -c "from client import BalatroClient; print(BalatroClient().health())"
   ```

The baseline only needs the Python standard library (3.10+). The Gym env also
needs `pip install -r requirements.txt`.

## Baseline

```
python run_baseline.py --runs 20
```

This plays 20 seeded runs (same `--seed` gives the same runs) and writes one row
per run to `baseline_results.csv`, then prints the win rate and the ante
distribution.

The agent (`agent.py`) routes each game state to a policy:

- **Hand play** (`heuristics/hand.py`): estimates each 1-5 card play from hand
  levels and card chips (ignoring jokers). It plays the best hand if it's a
  flush or better or is on pace to beat the blind. Otherwise it discards
  off-suit cards to chase a flush.
- **Shop** (`heuristics/shop.py`): values jokers from a tier list with tags
  (`heuristics/jokers.py`), adjusted for ante, synergy with the build and
  owned jokers, editions and cost. It buys vouchers and jokers, sells the
  worst joker to make room for a clearly better one, rerolls within a budget
  and keeps money for interest. Every number is in `ShopParams`
  (`to_vector()`/`from_vector()`) for later tuning.
- Blinds are always selected and booster packs are skipped.

## Gym env

`env/balatro_gym.py` wraps the hand-play decisions only. Everything between
hands is handled by the heuristic agent. See the module docstring for the
action, observation and reward definitions.

## Tests

```
python -m unittest discover -s tests -t .
```

The tests run against `tests/fake_game.py`, an in-memory stand-in for the API.
It checks the plumbing, not strategy: jokers have no effect there.
