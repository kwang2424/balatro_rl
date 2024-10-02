import gymnasium as gym
from gymnasium import spaces
import numpy as np
from connect import Connection, Actions
import time

rank_map = {
    '2': 2,
    '3': 3,
    '4': 4,
    '5': 5,
    '6': 6,
    '7': 7,
    '8': 8,
    '9': 9,
    '10': 10,
    'J': 11,
    'Q': 12,
    'K': 13,
    'A': 14
}

suit_map = {
    'Hearts': 0,
    'Diamonds': 1,
    'Clubs': 2,
    'Spades': 3
}

class BalatroGym(gym.Env):
    def __init__(self, max_steps=10000):
        self.connection = None
        self.port = 12346
        # actions are just, 5 cards + play or discard?
        self.actions = spaces.MultiDiscrete([2] * 5 + [2])

        # eventually add actions that include shop decisions

        # obs is just game state
        # rank, suit, chips, hands_remaining, discards_remaining
        # also would want to consider vouchers, shops, planets, jokers
        ranks = spaces.Box(low=2, high=14, shape=(5,), dtype=int)
        suits = spaces.Box(low=0, high=3, shape=(5,), dtype=int)
        chips = spaces.Box(low=0, high=np.inf, shape=(1,), dtype=int)
        hands = spaces.Box(low=0, high=100, shape=(1,), dtype=int)
        discards = spaces.Box(low=0, high=100, shape=(1,), dtype=int)

        self.obs_space = spaces.Dict({
            'rank': ranks,
            'suit': suits,
            'chips': chips,
            'hands': hands,
            'discards': discards
        })
        # also later on, want to build functionality that lets it select or skip blinds

        self.max_steps = max_steps

    def reset(self):
        if self.connection is None:
            self.connection = Connection("local_host", self.port)
            if not self.connection.ping():
                self.connection.start_instance()
                time.sleep(10)

        return 
    
    def to_menu(self):
        G = self.get_state()
        current_round = G["current_round"]
        if current_round["hands_played"] == 0 and current_round["discards_used"] == 0:
            return
        self.connection.send_message("MENU")

    def step(self, action):
        self.step_count += 1
        cards = action[:-1]
        discard = action[-1]

        if self.step_count > self.max_steps:
            return self.G, 0, True, {}
        if discard:
            self.G = self.play_hand(cards)
        else:
            self.G = self.discard_hand(cards)
        return self.G, 0, False, {}
    
    def get_state(self):
        G = self.connection.ping()
        while (
            not G.get("waitingForAction", False)
            or G["waitingFor"] != "select_cards_from_hand"
        ):
            if G.get("waitingForAction", False):
                auto_action = self.hardcoded_action(G)
                self.connection.send_message(auto_action)

            G = self.connection.ping()

        return G
    
    def hardcoded_action(self, game_state):
        match game_state["waitingFor"]:
            case "start_run":
                return [
                    Actions.START_RUN,
                    self.stake,
                    self.deck,
                    self.seed,
                    self.challenge,
                ]
            case "skip_or_select_blind":
                return [Actions.SELECT_BLIND]
            case "select_cards_from_hand":
                return None
            case "select_shop_action":
                return [Actions.END_SHOP]
            case "select_booster_action":
                return [Actions.SKIP_BOOSTER_PACK]
            case "sell_jokers":
                return [Actions.SELL_JOKER, []]
            case "rearrange_jokers":
                return [Actions.REARRANGE_JOKERS, []]
            case "use_or_sell_consumables":
                return [Actions.USE_CONSUMABLE, []]
            case "rearrange_consumables":
                return [Actions.REARRANGE_CONSUMABLES, []]
            case "rearrange_hand":
                return [Actions.REARRANGE_HAND, []]