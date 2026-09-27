import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from heuristics import jokers as J
from heuristics.shop import ShopParams, ShopPolicy


def joker(key, cost=5, sell_cost=2, **modifier):
    return {"key": key, "set": "JOKER", "cost": {"buy": cost, "sell": sell_cost},
            "modifier": modifier}


def voucher(key, cost=10):
    return {"key": key, "set": "VOUCHER", "cost": {"buy": cost, "sell": 0}, "modifier": {}}


def state(dollars=10, ante=1, jokers=(), cards=(), vouchers=(), slots=5,
          reroll_cost=5, round_=1, used_vouchers=None, packs=(), consumables=(),
          played=None, pack=None):
    G = {
        "state": "SHOP",
        "seed": "TEST",
        "money": dollars,
        "ante_num": ante,
        "round_num": round_,
        "used_vouchers": used_vouchers or {},
        "round": {"reroll_cost": reroll_cost},
        "hands": {name: {"played": n} for name, n in (played or {}).items()},
        "jokers": {"cards": list(jokers), "limit": slots},
        "consumables": {"cards": list(consumables), "limit": 2},
        "shop": {"cards": list(cards)},
        "vouchers": {"cards": list(vouchers)},
        "packs": {"cards": list(packs)},
    }
    if pack is not None:
        G["state"] = "SMODS_BOOSTER_OPENED"
        G["pack"] = {"cards": list(pack)}
    return G


def planet(key, cost=3):
    return {"key": key, "set": "PLANET", "cost": {"buy": cost, "sell": 1}, "modifier": {}}


def tarot(key, cost=3):
    return {"key": key, "set": "TAROT", "cost": {"buy": cost, "sell": 1}, "modifier": {}}


def pack(key, cost=4):
    return {"key": key, "set": "BOOSTER", "cost": {"buy": cost, "sell": 0}, "modifier": {}}


class JokerTableTest(unittest.TestCase):
    def test_keys_unique_and_prefixed(self):
        self.assertEqual(len(J.BY_KEY), len(J.JOKERS))
        for j in J.JOKERS:
            self.assertTrue(j.key.startswith("j_"), j.key)

    def test_lookup_falls_back_to_name(self):
        self.assertEqual(J.lookup({"name": "Blueprint"}).key, "j_blueprint")
        self.assertIsNone(J.lookup({"key": "j_not_real"}))


class ShopPolicyTest(unittest.TestCase):
    def test_buys_good_joker_with_free_slot(self):
        G = state(dollars=10, cards=[joker("j_egg", 4), joker("j_blueprint", 10)])
        self.assertEqual(ShopPolicy()(G), ("buy", {"card": 1}))

    def test_skips_unaffordable_and_buys_next_best(self):
        G = state(dollars=6, cards=[joker("j_blueprint", 10), joker("j_green_joker", 4)])
        self.assertEqual(ShopPolicy()(G), ("buy", {"card": 1}))

    def test_ignores_non_jokers(self):
        G = state(dollars=10, cards=[{"key": "c_jupiter", "set": "PLANET", "cost": {"buy": 3}}])
        self.assertEqual(ShopPolicy()(G), ("next_round", {}))

    def test_respects_reserve_after_early_antes(self):
        G = state(dollars=27, ante=4, cards=[joker("j_green_joker", 5)])
        self.assertEqual(ShopPolicy()(G), ("next_round", {}))
        G = state(dollars=31, ante=4, cards=[joker("j_green_joker", 5)])
        self.assertEqual(ShopPolicy()(G), ("buy", {"card": 0}))

    def test_great_joker_breaks_reserve(self):
        G = state(dollars=12, ante=4, cards=[joker("j_blueprint", 10)])
        self.assertEqual(ShopPolicy()(G), ("buy", {"card": 0}))

    def test_full_slots_sells_worst_then_buys(self):
        owned = [joker("j_blueprint"), joker("j_egg", sell_cost=3),
                 joker("j_cavendish"), joker("j_green_joker"), joker("j_duo")]
        G = state(dollars=10, jokers=owned, cards=[joker("j_brainstorm", 10)])
        policy = ShopPolicy()
        self.assertEqual(policy(G), ("sell", {"joker": 1}))

        G2 = state(dollars=13, jokers=owned[:1] + owned[2:],
                   cards=[joker("j_brainstorm", 10)])
        self.assertEqual(policy(G2), ("buy", {"card": 0}))

    def test_never_sells_eternal(self):
        owned = [joker("j_egg", eternal=True)] + [joker("j_blueprint")] * 4
        G = state(dollars=10, jokers=owned, cards=[joker("j_green_joker", 4)])
        self.assertEqual(ShopPolicy()(G), ("next_round", {}))

    def test_negative_needs_no_slot(self):
        owned = [joker("j_blueprint")] * 5
        G = state(dollars=10, jokers=owned,
                  cards=[joker("j_green_joker", 6, edition="NEGATIVE")])
        self.assertEqual(ShopPolicy()(G), ("buy", {"card": 0}))

    def test_build_bonus(self):
        G = state(dollars=10, ante=1, cards=[joker("j_crafty", 4)])
        self.assertEqual(ShopPolicy(ShopParams(buy_threshold=4.5))(G), ("next_round", {}))
        policy = ShopPolicy(ShopParams(buy_threshold=4.5), build={"flush"})
        self.assertEqual(policy(G), ("buy", {"card": 0}))

    def test_voucher(self):
        G = state(dollars=12, vouchers=[voucher("v_grabber")])
        self.assertEqual(ShopPolicy()(G), ("buy", {"voucher": 0}))

    def test_reroll_cap_resets_per_shop(self):
        policy = ShopPolicy(ShopParams(max_rerolls=1))
        G = state(dollars=40, ante=4, round_=5)
        self.assertEqual(policy(G), ("reroll", {}))
        self.assertEqual(policy(G), ("next_round", {}))
        G = state(dollars=40, ante=4, round_=6)
        self.assertEqual(policy(G), ("reroll", {}))

    def test_seed_money_raises_reserve_cap(self):
        policy = ShopPolicy(ShopParams(reserve=40))
        self.assertEqual(policy.reserve(state(ante=4)), 25)
        self.assertEqual(policy.reserve(state(ante=4, used_vouchers={"v_seed_money": ""})), 40)

    def test_rental_penalty(self):
        G = state(dollars=10, cards=[joker("j_green_joker", 4, rental=True)])
        self.assertEqual(ShopPolicy(ShopParams(rental_penalty=10))(G), ("next_round", {}))

    def test_uses_planets_and_sells_other_consumables(self):
        G = state(consumables=[tarot("c_fool"), planet("c_jupiter")])
        self.assertEqual(ShopPolicy()(G), ("use", {"consumable": 1}))
        G = state(consumables=[tarot("c_fool")])
        self.assertEqual(ShopPolicy()(G), ("sell", {"consumable": 0}))

    def test_buys_planet_for_build_hand_only(self):
        G = state(dollars=10, cards=[planet("c_mercury"), planet("c_jupiter")])
        self.assertEqual(ShopPolicy(build={"flush"})(G), ("buy", {"card": 1}))
        G = state(dollars=10, cards=[planet("c_mercury")])
        self.assertEqual(ShopPolicy(build={"flush"})(G), ("next_round", {}))

    def test_planet_follows_hands_actually_played(self):
        G = state(dollars=10, cards=[planet("c_mercury")], played={"Pair": 30, "Flush": 1})
        self.assertEqual(ShopPolicy(build={"flush"})(G), ("buy", {"card": 0}))

    def test_buys_celestial_and_buffoon_packs_not_arcana(self):
        policy = ShopPolicy(build={"flush"})
        G = state(dollars=10, packs=[pack("p_arcana_normal_1"), pack("p_celestial_mega_1", 8)])
        self.assertEqual(policy(G), ("buy", {"pack": 1}))
        G = state(dollars=10, packs=[pack("p_buffoon_normal_1")])
        self.assertEqual(policy(G), ("buy", {"pack": 0}))
        full = [joker("j_blueprint")] * 5
        G = state(dollars=10, jokers=full, packs=[pack("p_buffoon_normal_1")])
        self.assertEqual(policy(G), ("next_round", {}))

    def test_choose_from_opened_pack(self):
        policy = ShopPolicy(build={"flush"})
        G = state(pack=[planet("c_mercury"), planet("c_jupiter"), planet("c_pluto")])
        self.assertEqual(policy(G), ("pack", {"card": 1}))
        G = state(pack=[joker("j_egg"), joker("j_blueprint")])
        self.assertEqual(policy(G), ("pack", {"card": 1}))
        G = state(pack=[tarot("c_fool"), tarot("c_magician")])
        self.assertEqual(policy(G), ("pack", {"skip": True}))
        G = state(jokers=[joker("j_egg")] * 5, pack=[joker("j_blueprint")])
        self.assertEqual(policy(G), ("pack", {"skip": True}))

    def test_rejected_action_is_not_repeated(self):
        policy = ShopPolicy()
        G = state(consumables=[planet("c_jupiter")])
        action = policy(G)
        self.assertEqual(action, ("use", {"consumable": 0}))
        policy.rejected(action)
        self.assertEqual(policy(G), ("sell", {"consumable": 0}))
        policy.rejected(("sell", {"consumable": 0}))
        self.assertEqual(policy(G), ("next_round", {}))
        # A new run clears the bans.
        G2 = dict(G, seed="OTHER")
        self.assertEqual(policy(G2), ("use", {"consumable": 0}))

    def test_params_vector_roundtrip(self):
        p = ShopParams(reserve=10)
        self.assertEqual(ShopParams.from_vector(p.to_vector()), p)


if __name__ == "__main__":
    unittest.main()
