"""In-memory stand-in for the BalatroBot API, for testing the plumbing.

It follows the same state machine and state format, scores hands with the
heuristic evaluator (jokers do nothing), and rejects illegal actions the way
the real API does. It is not a faithful Balatro simulator.
"""

import random

from client import BalatroError
from heuristics import jokers as J
from heuristics.hand import estimate_score

RANKS = "23456789TJQKA"
SUITS = "HDCS"
BLIND_BASE = [300, 800, 2000, 5000, 11000, 20000, 35000, 50000]


def _err(method, name):
    return BalatroError(method, {"code": -32000, "message": name, "data": {"name": name}})


class FakeClient:
    def __init__(self, hand_size=8, joker_slots=5):
        self.hand_size = hand_size
        self.joker_slots = joker_slots
        self.calls = []
        self.state = "MENU"
        self.seed = None

    # --- helpers ---
    def _card(self, rank, suit):
        return {"key": f"{suit}_{rank}", "set": "DEFAULT", "value": {"rank": rank, "suit": suit},
                "modifier": {}, "state": {}, "cost": {"buy": 0, "sell": 0}}

    def _joker(self):
        info = self.rng.choice(J.JOKERS)
        return {"key": info.key, "set": "JOKER", "label": info.name, "modifier": {},
                "cost": {"buy": self.rng.randint(3, 8), "sell": 2}}

    def _draw(self):
        while len(self.hand) < self.hand_size and self.deck:
            self.hand.append(self.deck.pop())

    def _stock_shop(self):
        self.shop = [self._joker(), self._joker()]

    def _blind_target(self):
        mult = [1, 1.5, 2][self.blind_idx]
        return int(BLIND_BASE[min(self.ante, 8) - 1] * mult)

    def _gs(self):
        names = ["small", "big", "boss"]
        blinds = {}
        for i, n in enumerate(names):
            status = "UPCOMING"
            if self.state == "SELECTING_HAND" and i == self.blind_idx:
                status = "CURRENT"
            blinds[n] = {"type": n.upper(), "status": status,
                         "score": int(BLIND_BASE[min(self.ante, 8) - 1] * [1, 1.5, 2][i])}
        return {
            "state": self.state, "seed": self.seed, "won": self.won,
            "ante_num": self.ante, "round_num": self.round_num, "money": self.money,
            "used_vouchers": {},
            "round": {"hands_left": self.hands_left, "discards_left": self.discards_left,
                      "chips": self.chips, "reroll_cost": 5},
            "blinds": blinds,
            "hands": {},
            "hand": {"cards": list(self.hand), "limit": self.hand_size},
            "jokers": {"cards": list(self.jokers), "limit": self.joker_slots},
            "shop": {"cards": list(self.shop)},
            "vouchers": {"cards": []},
            "packs": {"cards": []},
        }

    def _require(self, method, *states):
        if self.state not in states:
            raise _err(method, "INVALID_STATE")

    # --- API ---
    def health(self):
        return {"status": "ok"}

    def gamestate(self):
        return self._gs()

    def menu(self):
        self.calls.append("menu")
        self.state = "MENU"
        return {"state": "MENU"}

    def start(self, deck="RED", stake="WHITE", seed=None):
        self.calls.append("start")
        self._require("start", "MENU")
        self.seed = seed or "FAKE"
        self.rng = random.Random(self.seed)
        self.ante, self.blind_idx, self.round_num = 1, 0, 0
        self.money, self.won, self.chips = 4, False, 0
        self.hands_left, self.discards_left = 4, 3
        self.hand, self.deck, self.jokers, self.shop = [], [], [], []
        self.state = "BLIND_SELECT"
        return self._gs()

    def select(self):
        self.calls.append("select")
        self._require("select", "BLIND_SELECT")
        self.deck = [self._card(r, s) for r in RANKS for s in SUITS]
        self.rng.shuffle(self.deck)
        self.hand, self.chips = [], 0
        self.hands_left, self.discards_left = 4, 3
        self.round_num += 1
        self._draw()
        self.state = "SELECTING_HAND"
        return self._gs()

    def _check_cards(self, method, cards):
        if not cards or len(cards) > 5 or len(set(cards)) != len(cards) \
                or any(not 0 <= i < len(self.hand) for i in cards):
            raise _err(method, "BAD_REQUEST")

    def play(self, cards):
        self.calls.append("play")
        self._require("play", "SELECTING_HAND")
        self._check_cards("play", cards)
        score, _ = estimate_score([self.hand[i] for i in cards])
        self.chips += score
        self.hands_left -= 1
        self.hand = [c for i, c in enumerate(self.hand) if i not in cards]
        self._draw()
        if self.chips >= self._blind_target():
            if self.blind_idx == 2 and self.ante == 8:
                self.won = True
            self.state = "ROUND_EVAL"
        elif self.hands_left == 0:
            self.state = "GAME_OVER"
        return self._gs()

    def discard(self, cards):
        self.calls.append("discard")
        self._require("discard", "SELECTING_HAND")
        self._check_cards("discard", cards)
        if self.discards_left <= 0:
            raise _err("discard", "NOT_ALLOWED")
        self.discards_left -= 1
        self.hand = [c for i, c in enumerate(self.hand) if i not in cards]
        self._draw()
        return self._gs()

    def cash_out(self):
        self.calls.append("cash_out")
        self._require("cash_out", "ROUND_EVAL")
        self.money += 3 + self.hands_left + min(self.money // 5, 5)
        self._stock_shop()
        self.state = "SHOP"
        return self._gs()

    def buy(self, card=None, voucher=None, pack=None):
        self.calls.append("buy")
        self._require("buy", "SHOP")
        if card is None or not 0 <= card < len(self.shop):
            raise _err("buy", "BAD_REQUEST")
        item = self.shop[card]
        if item["cost"]["buy"] > self.money or len(self.jokers) >= self.joker_slots:
            raise _err("buy", "NOT_ALLOWED")
        self.money -= item["cost"]["buy"]
        self.jokers.append(self.shop.pop(card))
        return self._gs()

    def sell(self, joker=None, consumable=None):
        self.calls.append("sell")
        if joker is None or not 0 <= joker < len(self.jokers):
            raise _err("sell", "BAD_REQUEST")
        self.money += self.jokers.pop(joker)["cost"]["sell"]
        return self._gs()

    def reroll(self):
        self.calls.append("reroll")
        self._require("reroll", "SHOP")
        if self.money < 5:
            raise _err("reroll", "NOT_ALLOWED")
        self.money -= 5
        self._stock_shop()
        return self._gs()

    def next_round(self):
        self.calls.append("next_round")
        self._require("next_round", "SHOP")
        self.blind_idx += 1
        if self.blind_idx == 3:
            self.blind_idx, self.ante = 0, self.ante + 1
        self.state = "BLIND_SELECT"
        return self._gs()

    def pack(self, card=None, targets=None, skip=False):
        raise _err("pack", "INVALID_STATE")

    def do(self, action):
        method, params = action
        return getattr(self, method)(**params)
