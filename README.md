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
3. Optional but recommended: patch the mod so web pages open in your browser
   can't send it commands (see `patches/patch_balatrobot.py` for details):
   ```
   python patches/patch_balatrobot.py "<Balatro Mods folder>/balatrobot"
   ```
   Re-run it after updating the mod;
   `--revert` undoes it.
4. Start the game with the mod:
   ```
   uvx balatrobot==1.5.2 serve --fast
   ```
5. Check that it responds:
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

## Simulator

[jackdaw](https://github.com/TylerFlar/jackdaw-balatro) is a Python
reimplementation of the Balatro engine that speaks the same API and validates
itself against the real game. `sim_client.SimClient` is a drop-in replacement
for `BalatroClient`, so everything here runs on it without the game. It needs
Python 3.12+:

```
pip install "jackdaw @ git+https://github.com/TylerFlar/jackdaw-balatro@e66de78855df84755d3af7d9a016129f3449f878"
python run_baseline.py --sim --runs 500 --workers 8
```

On the simulator, hand play scores its shortlisted plays exactly by simulating
each one on a copy of the game (jokers, enhancements, boss blinds included;
chance effects are sampled, not read off the seed). The live game can't do
this, so pass `--no-exact-scoring` to compare like with like.

For reference, on 200 seeds (`--seed 0`, Red deck, White stake):

| Hand scoring | Mean ante | Wins | Time (4 workers) |
|---|---|---|---|
| Estimate (ignores jokers) | 3.27 | 0 | 5 s |
| Exact (simulated) | 3.72 | 0 | 16 s |

Treat simulator results as provisional until spot-checked on the live game.

## Gym env

`env/balatro_gym.py` wraps the hand-play decisions only. Everything between
hands is handled by the heuristic agent. See the module docstring for the
action, observation and reward definitions. Pass `client=SimClient()` to
train on the simulator.

## Tests

```
python -m unittest discover -s tests -t .
```

`tests/test_balatrobot_patch.py` also runs the patched mod server under LuaJIT;
it needs `pip install lupa` and a BalatroBot checkout (`BALATROBOT_SRC`), and
is skipped otherwise.

The other tests run against `tests/fake_game.py`, an in-memory stand-in for the API.
It checks the plumbing, not strategy: jokers have no effect there.
