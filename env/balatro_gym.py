"""Gymnasium env for the hand-play part of Balatro.

The agent only chooses which cards to play or discard. Blinds, cashing out,
shops and packs are handled by the heuristic Agent between hands.

Action: MultiBinary(MAX_HAND + 1). The first MAX_HAND bits select cards by
position in hand; the last bit is 1 = play, 0 = discard. Invalid actions
(no cards, more than 5, selecting empty slots, discarding with none left) are
penalized and don't change the game.

Reward: chips scored this step / current blind's target, +1 for clearing a
blind, -1 when the run is lost.

Run from the repo root so the top-level modules import, with the game started
via `uvx balatrobot serve --fast`.
"""

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from agent import Agent
from client import BalatroClient
from heuristics.hand import RANK_VALUE, current_blind_score

MAX_HAND = 12
SUITS = {"H": 0, "D": 1, "C": 2, "S": 3}
INVALID_PENALTY = -0.1


class BalatroGym(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, client=None, agent=None, deck="RED", stake="WHITE",
                 max_steps=10000):
        self.client = client or BalatroClient()
        self.agent = agent or Agent(self.client)
        self.deck = deck
        self.stake = stake
        self.max_steps = max_steps

        self.action_space = spaces.MultiBinary(MAX_HAND + 1)
        self.observation_space = spaces.Dict({
            "rank": spaces.Box(0, 14, shape=(MAX_HAND,), dtype=np.int64),   # 0 = empty
            "suit": spaces.Box(-1, 3, shape=(MAX_HAND,), dtype=np.int64),   # -1 = empty
            "hands_left": spaces.Box(0, 100, shape=(1,), dtype=np.int64),
            "discards_left": spaces.Box(0, 100, shape=(1,), dtype=np.int64),
            "progress": spaces.Box(0, np.inf, shape=(1,), dtype=np.float32),  # chips / target
            "ante": spaces.Box(0, 100, shape=(1,), dtype=np.int64),
        })
        self.G = None
        self.step_count = 0

    # ---------- gym API ----------

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        run_seed = (options or {}).get("run_seed")
        if run_seed is None and seed is not None:
            run_seed = f"GYM{seed:05d}"
        self.client.menu()
        G = self.client.start(deck=self.deck, stake=self.stake, seed=run_seed)
        self.G = self.agent.advance_to(G, {"SELECTING_HAND"})
        self.step_count = 0
        return self._obs(self.G), {"state": self.G}

    def step(self, action):
        self.step_count += 1
        G = self.G
        cards = (G.get("hand") or {}).get("cards") or []
        rnd = G.get("round") or {}
        selected = [i for i in range(MAX_HAND) if action[i]]
        play = bool(action[MAX_HAND])

        valid = (1 <= len(selected) <= 5 and all(i < len(cards) for i in selected)
                 and (play or rnd.get("discards_left", 0) > 0))
        truncated = self.step_count >= self.max_steps
        if not valid:
            return self._obs(G), INVALID_PENALTY, False, truncated, {"invalid": True}

        target = current_blind_score(G) or 1
        chips_before = rnd.get("chips") or 0
        G = self.client.play(selected) if play else self.client.discard(selected)

        reward = 0.0
        if G.get("state") == "SELECTING_HAND":
            reward += ((G.get("round") or {}).get("chips", 0) - chips_before) / target
        else:
            # Blind over: cleared (ROUND_EVAL or won) or lost (GAME_OVER).
            if G.get("state") == "GAME_OVER":
                reward -= 1.0
            else:
                reward += max(target - chips_before, 0) / target + 1.0
            G = self.agent.advance_to(G, {"SELECTING_HAND"})

        self.G = G
        terminated = G.get("state") == "GAME_OVER" or bool(G.get("won"))
        return self._obs(G), reward, terminated, truncated, {"state": G}

    # ---------- helpers ----------

    def action_mask(self):
        """Which card slots currently hold a card (for masking policies)."""
        n = len((self.G.get("hand") or {}).get("cards") or [])
        return np.array([i < n for i in range(MAX_HAND)], dtype=bool)

    def _obs(self, G):
        rank = np.zeros(MAX_HAND, dtype=np.int64)
        suit = np.full(MAX_HAND, -1, dtype=np.int64)
        for i, card in enumerate(((G.get("hand") or {}).get("cards") or [])[:MAX_HAND]):
            v = card.get("value") or {}
            rank[i] = RANK_VALUE.get(v.get("rank"), 0)
            suit[i] = SUITS.get(v.get("suit"), -1)
        rnd = G.get("round") or {}
        target = current_blind_score(G) or 1
        return {
            "rank": rank,
            "suit": suit,
            "hands_left": np.array([rnd.get("hands_left", 0)], dtype=np.int64),
            "discards_left": np.array([rnd.get("discards_left", 0)], dtype=np.int64),
            "progress": np.array([(rnd.get("chips") or 0) / target], dtype=np.float32),
            "ante": np.array([G.get("ante_num") or 0], dtype=np.int64),
        }
