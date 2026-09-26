import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent import Agent
from heuristics.hand import HandPolicy, best_play, classify, estimate_score
from tests.fake_game import FakeClient


def c(code):
    """'AH' -> card dict (rank then suit)."""
    return {"value": {"rank": code[0], "suit": code[1]}, "state": {}}


def cards(*codes):
    return [c(x) for x in codes]


class ClassifyTest(unittest.TestCase):
    def check(self, codes, name):
        self.assertEqual(classify(cards(*codes))[0], name, codes)

    def test_hand_types(self):
        self.check(["AH", "KH", "QH", "JH", "TH"], "Straight Flush")
        self.check(["AH", "2D", "3C", "4S", "5H"], "Straight")
        self.check(["2H", "7H", "9H", "JH", "KH"], "Flush")
        self.check(["QH", "QD", "QC", "4S", "4H"], "Full House")
        self.check(["9H", "9D", "9C", "9S", "2H"], "Four of a Kind")
        self.check(["9H", "9D", "9C", "3S"], "Three of a Kind")
        self.check(["9H", "9D", "3C", "3S", "KH"], "Two Pair")
        self.check(["9H", "9D", "3C"], "Pair")
        self.check(["9H", "KD", "3C"], "High Card")
        self.check(["QH", "KD", "AC", "2S", "3H"], "High Card")  # no wraparound

    def test_scoring_cards_only(self):
        # Pair of 9s with a king kicker: (10 + 9 + 9) * 2
        self.assertEqual(estimate_score(cards("9H", "9D", "KC"))[0], 56)
        # High card counts only the top card: (5 + 11) * 1
        self.assertEqual(estimate_score(cards("AH", "2D"))[0], 16)

    def test_uses_hand_levels_from_state(self):
        levels = {"Pair": {"chips": 25, "mult": 3}}
        self.assertEqual(estimate_score(cards("9H", "9D"), levels)[0], (25 + 18) * 3)

    def test_best_play_finds_flush(self):
        hand = cards("2H", "7H", "9H", "JH", "KH", "KD", "3C", "4S")
        _, idx, name = best_play(hand)
        self.assertEqual(name, "Flush")
        self.assertEqual(sorted(idx), [0, 1, 2, 3, 4])


class HandPolicyTest(unittest.TestCase):
    def G(self, codes, need=300, chips=0, hands=4, discards=3):
        return {"hand": {"cards": cards(*codes)},
                "round": {"hands_left": hands, "discards_left": discards, "chips": chips},
                "blinds": {"small": {"status": "CURRENT", "score": need}}}

    def test_plays_when_on_pace(self):
        action = HandPolicy()(self.G(["AH", "AD", "AC", "KS", "2H", "5D", "7C", "9S"]))
        self.assertEqual(action[0], "play")

    def test_discards_off_suit_when_behind(self):
        G = self.G(["2H", "5H", "9H", "JH", "KD", "3C", "4S", "6D"], need=5000)
        method, params = HandPolicy()(G)
        self.assertEqual(method, "discard")
        self.assertEqual(sorted(params["cards"]), [4, 5, 6, 7])

    def test_plays_when_out_of_discards(self):
        G = self.G(["2H", "5H", "9H", "JH", "KD", "3C", "4S", "6D"], need=5000, discards=0)
        self.assertEqual(HandPolicy()(G)[0], "play")


class AgentTest(unittest.TestCase):
    def test_full_runs_on_fake_game(self):
        client = FakeClient()
        agent = Agent(client, log=lambda *_: None)
        for seed in ["A1", "B2", "C3"]:
            row = agent.play_run(seed=seed, max_steps=3000)
            self.assertEqual(row["error"], "", row)
            self.assertTrue(row["won"] or client.state == "GAME_OVER")
            self.assertGreaterEqual(row["ante"], 1)
        self.assertIn("cash_out", client.calls)
        self.assertIn("next_round", client.calls)

    def test_rejected_shop_action_leaves_shop(self):
        client = FakeClient()
        logs = []
        agent = Agent(client, shop_policy=lambda G: ("buy", {"card": 99}), log=logs.append)
        client.menu()
        client.start(seed="X")
        client.select()
        client.state, client.hands_left = "ROUND_EVAL", 3
        G = agent.act(client.cash_out())
        self.assertEqual(G["state"], "BLIND_SELECT")
        self.assertTrue(logs)


class GymEnvTest(unittest.TestCase):
    def setUp(self):
        try:
            import gymnasium  # noqa: F401
        except ImportError:
            self.skipTest("gymnasium not installed")

    def test_episode(self):
        import numpy as np
        from env.balatro_gym import MAX_HAND, BalatroGym

        env = BalatroGym(client=FakeClient(), agent=Agent(FakeClient(), log=lambda *_: None))
        env.agent.client = env.client
        obs, _ = env.reset(seed=1)
        self.assertTrue(env.observation_space.contains(obs))
        self.assertEqual(env.action_mask().sum(), 8)

        bad = np.zeros(MAX_HAND + 1, dtype=np.int8)
        _, r, *_ = env.step(bad)
        self.assertLess(r, 0)

        policy = HandPolicy()
        total, done, steps = 0.0, False, 0
        while not done and steps < 2000:
            method, params = policy(env.G)
            a = np.zeros(MAX_HAND + 1, dtype=np.int8)
            a[params["cards"]] = 1
            a[MAX_HAND] = method == "play"
            obs, r, term, trunc, _ = env.step(a)
            self.assertTrue(env.observation_space.contains(obs))
            total += r
            done = term or trunc
            steps += 1
        self.assertTrue(done)
        self.assertGreater(total, 0)


if __name__ == "__main__":
    unittest.main()
