"""Run the agent on the jackdaw simulator instead of the live game.

jackdaw (https://github.com/TylerFlar/jackdaw-balatro) is a Python
reimplementation of the Balatro engine that speaks the BalatroBot API, so
SimClient is a drop-in replacement for BalatroClient. It needs Python 3.12+:

    pip install "jackdaw @ git+https://github.com/TylerFlar/jackdaw-balatro@e66de78855df84755d3af7d9a016129f3449f878"

jackdaw validates itself against the real game, but it is still a
reimplementation; spot-check important results with live runs.
"""

import pickle
import random

from client import BalatroClient, BalatroError

try:
    from jackdaw.bridge.backend import RPCError, SimBackend
    from jackdaw.engine.actions import PlayHand
    from jackdaw.engine.game import step
    from jackdaw.engine.rng import PseudoRandom
except ImportError as e:  # pragma: no cover - depends on optional install
    raise ImportError(
        "SimClient needs the jackdaw simulator (Python 3.12+). Install it with:\n"
        '  pip install "jackdaw @ git+https://github.com/TylerFlar/jackdaw-balatro"'
    ) from e


class SimClient(BalatroClient):
    def __init__(self, rng=None):
        super().__init__()
        self.backend = SimBackend()
        self._rng = rng or random.Random()

    def rpc(self, method, **params):
        try:
            result = self.backend.handle(method, params or None)
        except RPCError as e:
            raise BalatroError(method, {"code": e.code, "message": e.message,
                                        "data": e.data}) from None
        self._mark_forced_cards(result)
        return result

    def _mark_forced_cards(self, result):
        """Show Cerulean Bell's forced card as highlighted, like the live game.

        jackdaw enforces the forced selection but always serializes
        highlight=False, so a policy couldn't see which card it is.
        """
        gs = self.backend._gs
        cards = ((result or {}).get("hand") or {}).get("cards") if isinstance(result, dict) else None
        if not gs or not cards:
            return
        for card, engine_card in zip(cards, gs.get("hand") or []):
            ability = getattr(engine_card, "ability", None)
            if isinstance(ability, dict) and ability.get("forced_selection"):
                card.setdefault("state", {})["highlight"] = True

    def score_plays(self, candidates):
        """Exact score of each candidate play (lists of hand indices).

        Each play is simulated on a copy of the game, so jokers, enhancements,
        editions, hand levels and boss blinds all count. The copy gets a fresh
        random seed, so chance effects (Lucky cards, Misprint, ...) are sampled
        rather than read off the run's seed, which the live game wouldn't
        reveal either.
        """
        gs = self.backend._gs
        if gs is None:
            raise BalatroError("score_plays", {"message": "no active run"})
        frozen = pickle.dumps(gs, pickle.HIGHEST_PROTOCOL)
        base = gs.get("chips", 0)
        scores = []
        for idx in candidates:
            clone = pickle.loads(frozen)
            clone["rng"] = PseudoRandom(f"SCORE{self._rng.getrandbits(40):X}")
            try:
                step(clone, PlayHand(tuple(idx)))
            except Exception:
                scores.append(-1)
                continue
            result = clone.get("last_score_result")
            scores.append(result.total if result is not None else clone.get("chips", 0) - base)
        return scores
