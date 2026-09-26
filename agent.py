"""Plays full runs by routing each game state to a policy.

The hand and shop policies are plain callables taking the game state and
returning a (method, params) action, so a learned policy can replace either one.
"""

import time

from client import BalatroError
from heuristics.hand import HandPolicy
from heuristics.shop import ShopPolicy

# States where the game is animating/transitioning and we just poll again
POLL_DELAY = 0.05


class Agent:
    def __init__(self, client, hand_policy=None, shop_policy=None, log=print):
        self.client = client
        self.hand_policy = hand_policy or HandPolicy()
        self.shop_policy = shop_policy or ShopPolicy(build={"flush"})
        self.log = log

    def act(self, G):
        """Take one action for the current state and return the new state."""
        c = self.client
        state = G.get("state")
        if state == "BLIND_SELECT":
            return c.select()
        if state == "SELECTING_HAND":
            return c.do(self.hand_policy(G))
        if state == "ROUND_EVAL":
            return c.cash_out()
        if state == "SHOP":
            action = self.shop_policy(G)
            try:
                return c.do(action)
            except BalatroError as e:
                # A rejected shop action shouldn't end the run; leave the shop.
                self.log(f"shop action {action} rejected ({e}); leaving shop")
                return c.next_round()
        if state == "SMODS_BOOSTER_OPENED":
            return c.pack(skip=True)
        time.sleep(POLL_DELAY)
        return c.gamestate()

    def advance_to(self, G, states, max_steps=500):
        """Act until the state is one of `states`, the run ends, or it's won."""
        for _ in range(max_steps):
            if G.get("state") in states or G.get("state") == "GAME_OVER" or G.get("won"):
                return G
            G = self.act(G)
        raise RuntimeError(f"stuck in state {G.get('state')} after {max_steps} steps")

    def play_run(self, deck="RED", stake="WHITE", seed=None, max_steps=5000):
        """Play one run to the end. Returns a summary dict."""
        c = self.client
        t0 = time.time()
        c.menu()
        G = c.start(deck=deck, stake=stake, seed=seed)
        steps, error = 0, None
        try:
            while G.get("state") != "GAME_OVER" and not G.get("won"):
                if steps >= max_steps:
                    error = f"max_steps reached in {G.get('state')}"
                    break
                G = self.act(G)
                steps += 1
        except Exception as e:  # keep going with the next seed
            error = repr(e)
            try:
                G = c.gamestate()
            except Exception:
                pass

        jokers = [j.get("key") for j in (G.get("jokers") or {}).get("cards") or []]
        return {
            "seed": G.get("seed", seed),
            "deck": deck,
            "stake": stake,
            "won": bool(G.get("won")),
            "ante": G.get("ante_num"),
            "round": G.get("round_num"),
            "money": G.get("money"),
            "jokers": " ".join(jokers),
            "steps": steps,
            "seconds": round(time.time() - t0, 1),
            "error": error or "",
        }
