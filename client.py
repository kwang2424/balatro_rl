"""Minimal client for the BalatroBot JSON-RPC API (https://github.com/coder/balatrobot).

Start the game with the mod first, e.g. `uvx balatrobot serve --fast`.
Every action method returns the resulting game state dict.
"""

import json
import urllib.request


class BalatroError(Exception):
    def __init__(self, method, error):
        self.method = method
        self.code = error.get("code")
        self.name = (error.get("data") or {}).get("name")
        super().__init__(f"{method}: {self.name or self.code}: {error.get('message')}")


class BalatroClient:
    def __init__(self, host="127.0.0.1", port=12346, timeout=60.0):
        self.url = f"http://{host}:{port}"
        self.timeout = timeout
        self._id = 0

    def rpc(self, method, **params):
        self._id += 1
        body = {"jsonrpc": "2.0", "method": method, "id": self._id}
        if params:
            body["params"] = params
        req = urllib.request.Request(
            self.url,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            data = json.loads(resp.read())
        if "error" in data:
            raise BalatroError(method, data["error"])
        return data["result"]

    # --- run control ---
    def health(self):
        return self.rpc("health")

    def gamestate(self):
        return self.rpc("gamestate")

    def menu(self):
        return self.rpc("menu")

    def start(self, deck="RED", stake="WHITE", seed=None):
        params = {"deck": deck, "stake": stake}
        if seed:
            params["seed"] = seed
        return self.rpc("start", **params)

    def save(self, path):
        return self.rpc("save", path=path)

    def load(self, path):
        return self.rpc("load", path=path)

    # --- blinds / round ---
    def select(self):
        return self.rpc("select")

    def skip(self):
        return self.rpc("skip")

    def play(self, cards):
        return self.rpc("play", cards=list(cards))

    def discard(self, cards):
        return self.rpc("discard", cards=list(cards))

    def cash_out(self):
        return self.rpc("cash_out")

    # --- shop ---
    def buy(self, card=None, voucher=None, pack=None):
        params = {k: v for k, v in (("card", card), ("voucher", voucher), ("pack", pack))
                  if v is not None}
        return self.rpc("buy", **params)

    def sell(self, joker=None, consumable=None):
        params = {k: v for k, v in (("joker", joker), ("consumable", consumable))
                  if v is not None}
        return self.rpc("sell", **params)

    def reroll(self):
        return self.rpc("reroll")

    def next_round(self):
        return self.rpc("next_round")

    def pack(self, card=None, targets=None, skip=False):
        if skip:
            return self.rpc("pack", skip=True)
        params = {"card": card}
        if targets:
            params["targets"] = list(targets)
        return self.rpc("pack", **params)

    def do(self, action):
        """Execute an action tuple (method, params) as returned by the policies."""
        method, params = action
        return self.rpc(method, **params)
