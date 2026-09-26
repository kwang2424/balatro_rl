import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot import Actions
from heuristics import jokers as J
from heuristics.shop import ShopParams, ShopPolicy


def joker(key, cost=5, sell_cost=2, **kw):
    return {"key": key, "set": "Joker", "cost": cost, "sell_cost": sell_cost, **kw}


def state(dollars=10, ante=1, jokers=(), cards=(), vouchers=(), slots=5,
          reroll_cost=5, round_=1):
    return {
        "dollars": dollars,
        "round": round_,
        "interest_cap": 25,
        "joker_slots": slots,
        "ante": {"number": ante},
        "jokers": list(jokers),
        "shop": {"cards": list(cards), "vouchers": list(vouchers),
                 "boosters": [], "reroll_cost": reroll_cost},
    }


class JokerTableTest(unittest.TestCase):
    def test_keys_unique_and_prefixed(self):
        self.assertEqual(len(J.BY_KEY), len(J.JOKERS))
        for j in J.JOKERS:
            self.assertTrue(j.key.startswith("j_"), j.key)

    def test_lookup_falls_back_to_name(self):
        self.assertEqual(J.lookup({"ability_name": "Blueprint"}).key, "j_blueprint")
        self.assertIsNone(J.lookup({"key": "j_not_real"}))


class ShopPolicyTest(unittest.TestCase):
    def test_buys_good_joker_with_free_slot(self):
        G = state(dollars=10, cards=[joker("j_egg", 4), joker("j_blueprint", 10)])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_CARD, [2]])

    def test_skips_unaffordable_and_buys_next_best(self):
        G = state(dollars=6, cards=[joker("j_blueprint", 10), joker("j_green_joker", 4)])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_CARD, [2]])

    def test_ignores_non_jokers(self):
        G = state(dollars=10, cards=[{"key": "c_jupiter", "set": "Planet", "cost": 3}])
        self.assertEqual(ShopPolicy()(G), [Actions.END_SHOP])

    def test_respects_reserve_after_early_antes(self):
        G = state(dollars=27, ante=4, cards=[joker("j_green_joker", 5)])
        self.assertEqual(ShopPolicy()(G), [Actions.END_SHOP])
        G = state(dollars=31, ante=4, cards=[joker("j_green_joker", 5)])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_CARD, [1]])

    def test_great_joker_breaks_reserve(self):
        G = state(dollars=12, ante=4, cards=[joker("j_blueprint", 10)])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_CARD, [1]])

    def test_full_slots_sells_worst_then_buys(self):
        owned = [joker("j_blueprint"), joker("j_egg", sell_cost=3),
                 joker("j_cavendish"), joker("j_green_joker"), joker("j_duo")]
        G = state(dollars=10, jokers=owned, cards=[joker("j_brainstorm", 10)])
        policy = ShopPolicy()
        self.assertEqual(policy(G), [Actions.SHOP_SELL_JOKER, [2]])

        G2 = state(dollars=13, jokers=owned[:1] + owned[2:],
                   cards=[joker("j_brainstorm", 10)])
        self.assertEqual(policy(G2), [Actions.BUY_CARD, [1]])

    def test_never_sells_eternal(self):
        owned = [joker("j_egg", eternal=True)] + [joker("j_blueprint")] * 4
        G = state(dollars=10, jokers=owned, cards=[joker("j_green_joker", 4)])
        self.assertEqual(ShopPolicy()(G), [Actions.END_SHOP])

    def test_negative_needs_no_slot(self):
        owned = [joker("j_blueprint")] * 5
        G = state(dollars=10, jokers=owned,
                  cards=[joker("j_green_joker", 6, edition="negative")])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_CARD, [1]])

    def test_build_bonus(self):
        G = state(dollars=10, ante=1, cards=[joker("j_crafty", 4)])
        self.assertEqual(ShopPolicy(ShopParams(buy_threshold=4.5))(G), [Actions.END_SHOP])
        policy = ShopPolicy(ShopParams(buy_threshold=4.5), build={"flush"})
        self.assertEqual(policy(G), [Actions.BUY_CARD, [1]])

    def test_voucher(self):
        G = state(dollars=12, vouchers=[{"key": "v_grabber", "cost": 10}])
        self.assertEqual(ShopPolicy()(G), [Actions.BUY_VOUCHER, [1]])

    def test_reroll_cap_resets_per_shop(self):
        policy = ShopPolicy(ShopParams(max_rerolls=1))
        G = state(dollars=40, ante=4, round_=5)
        self.assertEqual(policy(G), [Actions.REROLL_SHOP])
        self.assertEqual(policy(G), [Actions.END_SHOP])
        G = state(dollars=40, ante=4, round_=6)
        self.assertEqual(policy(G), [Actions.REROLL_SHOP])

    def test_params_vector_roundtrip(self):
        p = ShopParams(reserve=10)
        self.assertEqual(ShopParams.from_vector(p.to_vector()), p)


if __name__ == "__main__":
    unittest.main()
