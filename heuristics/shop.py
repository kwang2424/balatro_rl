"""Parameterized rule-based shop policy.

Each call looks at the current game state and returns one shop action; call it
again with the new state until it returns next_round.

Priority per call:
  0. Use owned planets (and a few no-target consumables); sell other consumables.
  1. Buy a good voucher if it doesn't break the money reserve.
  2. Buy the best item if it clears the threshold: jokers, planets for the
     hands the bot plays, and Buffoon/Celestial packs compete in one list.
  3. If joker slots are full and a shop joker beats our worst one by a margin,
     sell the worst one (the next call then buys the new joker).
  4. Reroll while money is above the reroll reserve and under the reroll cap.
  5. Leave the shop.

In an opened booster pack it takes the best joker or planet, or skips.

All numbers live in ShopParams so they can be tuned later (e.g. with CMA-ES)
via to_vector()/from_vector().

The game state format is the BalatroBot API's (https://github.com/coder/balatrobot).
Actions are (method, params) tuples such as ("buy", {"card": 0}); run them with
BalatroClient.do().
"""

from dataclasses import dataclass, fields

from heuristics import jokers as J


@dataclass
class ShopParams:
    # Base value of each tier
    tier_s: float = 10.0
    tier_a: float = 7.5
    tier_b: float = 5.0
    tier_c: float = 3.0
    tier_d: float = 1.0

    # Role adjustments. Early/late blend linearly between ante 1 and 8.
    econ_early: float = 2.0
    econ_late: float = -2.0
    xmult_early: float = -0.5
    xmult_late: float = 2.5
    scaling_early: float = 1.5
    scaling_late: float = -1.5
    chips_mult_early: float = 1.0  # flat +chips/+mult matter most early

    # Synergy with the bot's build and with jokers already owned
    build_bonus: float = 2.0          # joker supports preferred build
    shared_tag_bonus: float = 0.75    # per build tag shared with owned jokers
    copy_per_xmult_owned: float = 1.0 # Blueprint/Brainstorm get better with xmult
    setup_penalty: float = 3.0
    risky_penalty: float = 1.0
    rental_penalty: float = 2.0

    # Editions
    foil_bonus: float = 0.5
    holo_bonus: float = 1.0
    polychrome_bonus: float = 2.5

    # Economy
    cost_weight: float = 0.15      # value lost per $ spent
    early_reserve: float = 0.0     # money to keep in antes <= early_antes
    reserve: float = 25.0          # money to keep afterwards (capped at interest cap)
    early_antes: float = 2.0
    reserve_break_value: float = 8.0  # a joker this good may break the reserve

    # Thresholds
    buy_threshold: float = 3.0
    replace_margin: float = 2.5
    voucher_threshold: float = 5.0

    # Rerolls
    reroll_reserve: float = 30.0
    max_rerolls: float = 2.0

    # Planets and packs. A planet is worth planet_value times the share of
    # plays that use its hand; the build's hand starts with build_hand_prior
    # pretend plays so the first planets go to it.
    planet_value: float = 6.0
    build_hand_prior: float = 5.0
    buffoon_pack_value: float = 4.0
    celestial_pack_value: float = 3.0
    big_pack_bonus: float = 1.0     # per size step: jumbo +1x, mega +2x

    def to_vector(self):
        return [getattr(self, f.name) for f in fields(self)]

    @classmethod
    def from_vector(cls, vec):
        return cls(**{f.name: float(v) for f, v in zip(fields(cls), vec)})


BUILD_TAGS = frozenset({
    "flush", "straight", "pair", "two_pair", "three_kind", "four_kind",
    "full_house", "high_card", "face", "hearts", "diamonds", "clubs", "spades",
    "even", "odd",
})

INTEREST_CAP_VOUCHERS = {"v_seed_money": 50, "v_money_tree": 100}


def _cards(G, area):
    return list((G.get(area) or {}).get("cards") or [])


def _is_joker(card):
    return card.get("set") == "JOKER" or (card.get("key") or "").startswith("j_")


def _buy_cost(card):
    return (card.get("cost") or {}).get("buy", 99)


def _sell_cost(card):
    return (card.get("cost") or {}).get("sell", 0)


def _modifier(card):
    return card.get("modifier") or {}


def _set(card):
    return card.get("set") or ""


def _edition(card):
    return (_modifier(card).get("edition") or "").lower() or None


class ShopPolicy:
    def __init__(self, params=None, build=(), overrides=None):
        """
        params:    ShopParams
        build:     build tags the hand-play policy aims for, e.g. {"flush"}
        overrides: {joker_key: value} to replace the computed value entirely
        """
        self.params = params or ShopParams()
        self.build = frozenset(build)
        self.build_hands = {J.BUILD_HANDS[b] for b in self.build if b in J.BUILD_HANDS}
        self.overrides = dict(overrides or {})
        self._shop_id = None
        self._rerolls = 0
        self._run_seed = None
        self._banned = set()      # (method, card key) the game rejected this run
        self._last = None         # (method, card key) of the last action returned

    # ---------- valuation ----------

    def _tier_value(self, tier):
        p = self.params
        return {"S": p.tier_s, "A": p.tier_a, "B": p.tier_b,
                "C": p.tier_c, "D": p.tier_d}[tier]

    def joker_value(self, card, owned, ante):
        """Heuristic value of a joker given the jokers we own (excluding it)."""
        info = J.lookup(card)
        key = info.key if info else card.get("key")
        if key in self.overrides:
            return self.overrides[key]

        p = self.params
        tier = info.tier if info else J.UNKNOWN_TIER
        tags = info.tags if info else frozenset()
        t = min(max((ante - 1) / 7.0, 0.0), 1.0)  # 0 at ante 1, 1 at ante 8

        v = self._tier_value(tier)
        if "econ" in tags:
            v += (1 - t) * p.econ_early + t * p.econ_late
        if "xmult" in tags:
            v += (1 - t) * p.xmult_early + t * p.xmult_late
        if "scaling" in tags:
            v += (1 - t) * p.scaling_early + t * p.scaling_late
        if tags & {"chips", "mult"} and "xmult" not in tags:
            v += (1 - t) * p.chips_mult_early
        if "setup" in tags:
            v -= p.setup_penalty
        if "risky" in tags:
            v -= p.risky_penalty
        if _modifier(card).get("rental"):
            v -= p.rental_penalty

        build_tags = tags & BUILD_TAGS
        if build_tags & self.build:
            v += p.build_bonus
        owned_infos = [i for i in map(J.lookup, owned) if i]
        owned_tags = set()
        for oi in owned_infos:
            owned_tags |= oi.tags & BUILD_TAGS
        v += p.shared_tag_bonus * len(build_tags & owned_tags)

        if "copy" in tags:
            v += p.copy_per_xmult_owned * sum("xmult" in oi.tags for oi in owned_infos)

        v += {"foil": p.foil_bonus, "holo": p.holo_bonus,
              "polychrome": p.polychrome_bonus}.get(_edition(card), 0.0)
        return v

    def hand_weights(self, G):
        """How much each poker hand is worth leveling, from 0 to 1.

        Plays per hand relative to the most-played hand (so the main hand
        counts fully), with build_hand_prior pretend plays for the build's hand.
        """
        prior = self.params.build_hand_prior
        counts = {name: (h.get("played") or 0) for name, h in (G.get("hands") or {}).items()}
        for name in self.build_hands:
            counts[name] = counts.get(name, 0) + prior
        top = max(counts.values(), default=0)
        return {n: c / top for n, c in counts.items()} if top > 0 else {}

    def planet_value(self, card, weights):
        key = card.get("key")
        if key == J.BLACK_HOLE:
            return self.params.planet_value
        return self.params.planet_value * weights.get(J.PLANET_HANDS.get(key), 0.0)

    def pack_value(self, card, weights, joker_slot_free):
        kind = J.pack_kind(card.get("key"))
        if kind is None:
            return None
        name, size = kind
        p = self.params
        bonus = 1 + p.big_pack_bonus * size
        if name == "buffoon" and joker_slot_free:
            return p.buffoon_pack_value * bonus
        if name == "celestial":
            return p.celestial_pack_value * bonus * max(weights.values(), default=0.0)
        return None

    def reserve(self, G):
        p = self.params
        used = G.get("used_vouchers") or {}
        cap = max([25] + [c for k, c in INTEREST_CAP_VOUCHERS.items() if k in used])
        if self._ante(G) <= p.early_antes:
            return min(p.early_reserve, cap)
        return min(p.reserve, cap)

    # ---------- helpers ----------

    @staticmethod
    def _ante(G):
        return G.get("ante_num") or 1

    @staticmethod
    def _slots(G):
        return (G.get("jokers") or {}).get("limit") or 5

    def rejected(self, action):
        """Called when the game refuses the last action: don't try it again this run."""
        if self._last and self._last[0] == action[0]:
            self._banned.add(self._last)

    def _pick(self, method, params, card):
        """Return an action, remembering it so a rejection can ban it."""
        self._last = (method, card.get("key")) if card else None
        return (method, params)

    def _ok(self, method, card):
        return (method, card.get("key")) not in self._banned

    def _new_shop_visit(self, G):
        if G.get("seed") != self._run_seed:
            self._run_seed = G.get("seed")
            self._banned = set()
        shop_id = (G.get("seed"), G.get("round_num"), self._ante(G))
        if shop_id != self._shop_id:
            self._shop_id = shop_id
            self._rerolls = 0

    def _worst_owned(self, owned, ante):
        """(index, value) of the least valuable sellable joker, or None."""
        worst = None
        for i, card in enumerate(owned):
            if _modifier(card).get("eternal"):
                continue
            v = self.joker_value(card, owned[:i] + owned[i + 1:], ante)
            if worst is None or v < worst[1]:
                worst = (i, v)
        return worst

    # ---------- decision ----------

    def __call__(self, G):
        return self.choose(G)

    def choose(self, G):
        if G.get("state") == "SMODS_BOOSTER_OPENED":
            return self.choose_pack(G)
        self._new_shop_visit(G)
        p = self.params
        owned = _cards(G, "jokers")
        money = G.get("money") or 0
        ante = self._ante(G)
        reserve = self.reserve(G)
        weights = self.hand_weights(G)

        # 0. Consumables: use the ones that help right away, sell the rest.
        consumables = _cards(G, "consumables")
        for i, card in enumerate(consumables):
            if card.get("key") in J.USE_ON_SIGHT and self._ok("use", card):
                return self._pick("use", {"consumable": i}, card)
        for i, card in enumerate(consumables):
            if not _modifier(card).get("eternal") and self._ok("sell", card):
                return self._pick("sell", {"consumable": i}, card)

        # 1. Vouchers
        for i, card in enumerate(_cards(G, "vouchers")):
            v = J.VOUCHER_VALUES.get(card.get("key"), 0)
            cost = _buy_cost(card)
            if (v >= p.voucher_threshold and cost <= money and money - cost >= reserve
                    and self._ok("buy", card)):
                return self._pick("buy", {"voucher": i}, card)

        # 2/3. Jokers, planets and packs, best first
        free_slot = len(owned) < self._slots(G)
        consumable_room = len(consumables) < ((G.get("consumables") or {}).get("limit") or 2)
        candidates = []
        for i, card in enumerate(_cards(G, "shop")):
            cost = _buy_cost(card)
            if _is_joker(card):
                value = self.joker_value(card, owned, ante)
                candidates.append((value - p.cost_weight * cost, "joker", i, card, cost))
            elif (_set(card) == "PLANET" or card.get("key") == J.BLACK_HOLE) and consumable_room:
                value = self.planet_value(card, weights)
                candidates.append((value - p.cost_weight * cost, "planet", i, card, cost))
        for i, card in enumerate(_cards(G, "packs")):
            value = self.pack_value(card, weights, free_slot)
            if value is not None:
                cost = _buy_cost(card)
                candidates.append((value - p.cost_weight * cost, "pack", i, card, cost))
        candidates.sort(key=lambda c: -c[0])

        for net, kind, i, card, cost in candidates:
            if net < p.buy_threshold:
                break
            if not self._ok("buy", card):
                continue
            affordable = cost <= money and (money - cost >= reserve or net >= p.reserve_break_value)
            if kind == "pack":
                if affordable:
                    return self._pick("buy", {"pack": i}, card)
                continue
            if kind == "planet":
                if affordable:
                    return self._pick("buy", {"card": i}, card)
                continue

            needs_slot = _edition(card) != "negative"
            if free_slot or not needs_slot:
                if affordable:
                    return self._pick("buy", {"card": i}, card)
                continue

            worst = self._worst_owned(owned, ante)
            if worst is None:
                continue
            w_idx, w_val = worst
            # Value the candidate as it will be after the sale, so the buy on
            # the next call sees exactly this number and goes through.
            remaining = owned[:w_idx] + owned[w_idx + 1:]
            net_after = self.joker_value(card, remaining, ante) - p.cost_weight * cost
            after = money + _sell_cost(owned[w_idx]) - cost
            if (net_after >= p.buy_threshold
                    and net_after - w_val >= p.replace_margin and after >= 0
                    and (after >= reserve or net_after >= p.reserve_break_value)):
                return self._pick("sell", {"joker": w_idx}, owned[w_idx])

        # 4. Reroll
        reroll_cost = (G.get("round") or {}).get("reroll_cost")
        if (reroll_cost is not None and self._rerolls < p.max_rerolls
                and money - reroll_cost >= max(p.reroll_reserve, reserve)):
            self._rerolls += 1
            return self._pick("reroll", {}, None)

        # 5. Done
        return self._pick("next_round", {}, None)

    def choose_pack(self, G):
        """Pick from an opened booster pack: the best joker or planet, else skip."""
        owned = _cards(G, "jokers")
        free_slot = len(owned) < self._slots(G)
        weights = self.hand_weights(G)
        best = None
        for i, card in enumerate(_cards(G, "pack")):
            if _is_joker(card):
                if not (free_slot or _edition(card) == "negative"):
                    continue
                value = self.joker_value(card, owned, self._ante(G))
                if value < self.params.buy_threshold:
                    continue
            elif _set(card) == "PLANET" or card.get("key") == J.BLACK_HOLE:
                value = self.planet_value(card, weights)
            else:
                continue
            if best is None or value > best[0]:
                best = (value, i)
        if best is None:
            return ("pack", {"skip": True})
        return ("pack", {"card": best[1]})
