"""Tests for SimClient (skipped unless the jackdaw simulator is installed)."""

import os
import pickle
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

try:
    from sim_client import SimClient
except ImportError:
    SimClient = None

from agent import Agent
from heuristics.hand import HandPolicy


@unittest.skipUnless(SimClient, "jackdaw not installed")
class SimClientTest(unittest.TestCase):
    def start_round(self, seed="SIMTEST1"):
        client = SimClient()
        client.menu()
        G = client.start(seed=seed)
        return client, client.select()

    def test_score_plays_does_not_change_the_game(self):
        client, G = self.start_round()
        before = pickle.dumps(client.backend._gs)
        client.score_plays([[0], [0, 1], [0, 1, 2, 3, 4]])
        self.assertEqual(pickle.dumps(client.backend._gs), before)

    def test_score_matches_actual_play(self):
        # No jokers yet, so nothing random affects the score.
        client, G = self.start_round()
        play = [0, 1, 2]
        predicted = client.score_plays([play])[0]
        G2 = client.play(play)
        self.assertEqual(G2["round"]["chips"] - G["round"]["chips"], predicted)

    def test_forced_card_is_shown_and_respected(self):
        client, G = self.start_round()
        client.backend._gs["hand"][2].ability["forced_selection"] = True
        G = client.gamestate()
        self.assertTrue(G["hand"]["cards"][2]["state"]["highlight"])
        with self.assertRaises(Exception):
            client.discard([0, 1])
        method, params = HandPolicy()(G)
        self.assertIn(2, params["cards"])
        client.do((method, params))  # accepted

    def test_illegal_play_scores_negative(self):
        client, G = self.start_round()
        self.assertEqual(client.score_plays([[99]]), [-1])

    def test_agent_runs_with_exact_scoring(self):
        client = SimClient()
        agent = Agent(client, hand_policy=HandPolicy(scorer=client.score_plays),
                      log=lambda *_: None)
        row = agent.play_run(seed="SIMTEST2")
        self.assertEqual(row["error"], "")
        self.assertGreaterEqual(row["ante"], 1)


if __name__ == "__main__":
    unittest.main()
