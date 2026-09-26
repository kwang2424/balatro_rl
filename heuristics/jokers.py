"""Static joker knowledge: a rough tier list plus tags used for synergy scoring.

Tiers are loosely based on community tier lists, adjusted for what this bot can
actually exploit. The bot doesn't use tarots/spectrals, enhance cards, or
manipulate its deck, so jokers that need that kind of setup carry the "setup"
tag and get penalized by the shop policy.

Tags
  role:  chips, mult, xmult, econ, scaling, retrigger, copy, utility
  build: flush, straight, pair, two_pair, three_kind, four_kind, full_house,
         high_card, face, hearts, diamonds, clubs, spades, even, odd
  other: setup (needs things the bot doesn't do), risky (can self-destruct or
         harm the run)
"""

from dataclasses import dataclass

TIERS = ("S", "A", "B", "C", "D")


@dataclass(frozen=True)
class JokerInfo:
    key: str
    name: str
    tier: str
    tags: frozenset


def _j(key, name, tier, *tags):
    assert tier in TIERS, key
    return JokerInfo(key, name, tier, frozenset(tags))


JOKERS = [
    # --- plain mult / chips ---
    _j("j_joker", "Joker", "C", "mult"),
    _j("j_greedy_joker", "Greedy Joker", "C", "mult", "diamonds"),
    _j("j_lusty_joker", "Lusty Joker", "C", "mult", "hearts"),
    _j("j_wrathful_joker", "Wrathful Joker", "C", "mult", "spades"),
    _j("j_gluttenous_joker", "Gluttonous Joker", "C", "mult", "clubs"),
    _j("j_jolly", "Jolly Joker", "C", "mult", "pair"),
    _j("j_zany", "Zany Joker", "C", "mult", "three_kind"),
    _j("j_mad", "Mad Joker", "C", "mult", "two_pair"),
    _j("j_crazy", "Crazy Joker", "C", "mult", "straight"),
    _j("j_droll", "Droll Joker", "B", "mult", "flush"),
    _j("j_sly", "Sly Joker", "C", "chips", "pair"),
    _j("j_wily", "Wily Joker", "C", "chips", "three_kind"),
    _j("j_clever", "Clever Joker", "C", "chips", "two_pair"),
    _j("j_devious", "Devious Joker", "C", "chips", "straight"),
    _j("j_crafty", "Crafty Joker", "C", "chips", "flush"),
    _j("j_half", "Half Joker", "B", "mult", "high_card", "pair", "three_kind"),
    _j("j_misprint", "Misprint", "C", "mult"),
    _j("j_abstract", "Abstract Joker", "B", "mult"),
    _j("j_raised_fist", "Raised Fist", "C", "mult"),
    _j("j_fibonacci", "Fibonacci", "B", "mult"),
    _j("j_scary_face", "Scary Face", "C", "chips", "face"),
    _j("j_smiley", "Smiley Face", "C", "mult", "face"),
    _j("j_even_steven", "Even Steven", "C", "mult", "even"),
    _j("j_odd_todd", "Odd Todd", "C", "chips", "odd"),
    _j("j_scholar", "Scholar", "C", "chips", "mult"),
    _j("j_banner", "Banner", "C", "chips"),
    _j("j_mystic_summit", "Mystic Summit", "C", "mult"),
    _j("j_blackboard", "Blackboard", "C", "xmult", "spades", "clubs"),
    _j("j_arrowhead", "Arrowhead", "C", "chips", "spades"),
    _j("j_onyx_agate", "Onyx Agate", "C", "mult", "clubs"),
    _j("j_bloodstone", "Bloodstone", "B", "xmult", "hearts"),
    _j("j_rough_gem", "Rough Gem", "C", "econ", "diamonds"),
    _j("j_walkie_talkie", "Walkie Talkie", "C", "chips", "mult"),
    _j("j_stuntman", "Stuntman", "B", "chips"),
    _j("j_bull", "Bull", "B", "chips"),
    _j("j_bootstraps", "Bootstraps", "B", "mult"),
    _j("j_swashbuckler", "Swashbuckler", "C", "mult"),
    _j("j_popcorn", "Popcorn", "C", "mult"),
    _j("j_ice_cream", "Ice Cream", "C", "chips"),
    _j("j_gros_michel", "Gros Michel", "B", "mult", "risky"),
    _j("j_cavendish", "Cavendish", "A", "xmult"),
    _j("j_shoot_the_moon", "Shoot the Moon", "C", "mult", "face"),
    _j("j_flower_pot", "Flower Pot", "C", "xmult"),
    _j("j_seeing_double", "Seeing Double", "C", "xmult", "clubs"),
    _j("j_stencil", "Joker Stencil", "B", "xmult"),
    _j("j_card_sharp", "Card Sharp", "B", "xmult"),
    _j("j_acrobat", "Acrobat", "B", "xmult"),
    _j("j_photograph", "Photograph", "B", "xmult", "face"),
    _j("j_ancient", "Ancient Joker", "B", "xmult"),
    _j("j_idol", "The Idol", "B", "xmult"),
    _j("j_baron", "Baron", "B", "xmult", "setup"),
    _j("j_duo", "The Duo", "A", "xmult", "pair", "two_pair", "full_house"),
    _j("j_trio", "The Trio", "A", "xmult", "three_kind", "full_house"),
    _j("j_family", "The Family", "B", "xmult", "four_kind"),
    _j("j_order", "The Order", "B", "xmult", "straight"),
    _j("j_tribe", "The Tribe", "A", "xmult", "flush"),
    _j("j_baseball", "Baseball Card", "B", "xmult"),
    _j("j_ramen", "Ramen", "B", "xmult"),
    _j("j_supernova", "Supernova", "B", "mult"),
    _j("j_drivers_license", "Driver's License", "D", "xmult", "setup"),
    _j("j_steel_joker", "Steel Joker", "D", "xmult", "setup"),
    _j("j_glass", "Glass Joker", "D", "xmult", "setup"),
    _j("j_stone", "Stone Joker", "D", "chips", "setup"),
    _j("j_ticket", "Golden Ticket", "D", "econ", "setup"),
    _j("j_lucky_cat", "Lucky Cat", "D", "xmult", "scaling", "setup"),
    _j("j_vampire", "Vampire", "D", "xmult", "scaling", "setup"),
    _j("j_midas_mask", "Midas Mask", "D", "utility", "setup"),
    _j("j_marble", "Marble Joker", "D", "utility", "setup"),
    _j("j_mime", "Mime", "D", "retrigger", "setup"),
    _j("j_8_ball", "8 Ball", "D", "utility", "setup"),
    _j("j_superposition", "Superposition", "D", "utility", "straight", "setup"),
    _j("j_seance", "Seance", "D", "utility", "straight", "flush", "setup"),
    _j("j_sixth_sense", "Sixth Sense", "D", "utility", "setup"),
    _j("j_cartomancer", "Cartomancer", "D", "utility", "setup"),
    _j("j_astronomer", "Astronomer", "D", "econ", "setup"),
    _j("j_fortune_teller", "Fortune Teller", "D", "mult", "setup"),
    _j("j_constellation", "Constellation", "C", "xmult", "scaling", "setup"),
    _j("j_hologram", "Hologram", "D", "xmult", "scaling", "setup"),
    _j("j_campfire", "Campfire", "C", "xmult", "scaling", "setup"),
    _j("j_dna", "DNA", "D", "utility", "setup"),
    _j("j_certificate", "Certificate", "D", "utility", "setup"),
    _j("j_erosion", "Erosion", "D", "mult", "setup"),
    _j("j_hallucination", "Hallucination", "D", "utility", "setup"),
    _j("j_vagabond", "Vagabond", "D", "utility", "setup"),
    _j("j_perkeo", "Perkeo", "C", "utility", "setup"),
    _j("j_caino", "Caino", "B", "xmult", "scaling", "face", "setup"),
    # --- scaling ---
    _j("j_ride_the_bus", "Ride the Bus", "B", "mult", "scaling"),
    _j("j_green_joker", "Green Joker", "B", "mult", "scaling"),
    _j("j_runner", "Runner", "B", "chips", "scaling", "straight"),
    _j("j_square", "Square Joker", "B", "chips", "scaling"),
    _j("j_wee", "Wee Joker", "B", "chips", "scaling"),
    _j("j_castle", "Castle", "B", "chips", "scaling"),
    _j("j_hiker", "Hiker", "B", "chips", "scaling"),
    _j("j_trousers", "Spare Trousers", "B", "mult", "scaling", "two_pair"),
    _j("j_flash", "Flash Card", "C", "mult", "scaling"),
    _j("j_red_card", "Red Card", "D", "mult", "scaling"),
    _j("j_throwback", "Throwback", "D", "xmult", "scaling"),
    _j("j_obelisk", "Obelisk", "C", "xmult", "scaling"),
    _j("j_madness", "Madness", "C", "xmult", "scaling", "risky"),
    _j("j_yorick", "Yorick", "A", "xmult", "scaling"),
    _j("j_ceremonial", "Ceremonial Dagger", "D", "mult", "scaling", "risky"),
    _j("j_loyalty_card", "Loyalty Card", "B", "xmult"),
    _j("j_selzer", "Seltzer", "C", "retrigger"),
    # --- retriggers / copy ---
    _j("j_blueprint", "Blueprint", "S", "copy"),
    _j("j_brainstorm", "Brainstorm", "S", "copy"),
    _j("j_hanging_chad", "Hanging Chad", "B", "retrigger"),
    _j("j_sock_and_buskin", "Sock and Buskin", "B", "retrigger", "face"),
    _j("j_hack", "Hack", "C", "retrigger"),
    _j("j_dusk", "Dusk", "C", "retrigger"),
    _j("j_triboulet", "Triboulet", "S", "xmult", "face"),
    # --- hand-type / rule changers ---
    _j("j_four_fingers", "Four Fingers", "B", "utility", "flush", "straight"),
    _j("j_shortcut", "Shortcut", "C", "utility", "straight"),
    _j("j_smeared", "Smeared Joker", "B", "utility", "flush"),
    _j("j_pareidolia", "Pareidolia", "C", "utility", "face"),
    _j("j_splash", "Splash", "D", "utility"),
    _j("j_oops", "Oops! All 6s", "D", "utility", "setup"),
    _j("j_juggler", "Juggler", "B", "utility"),
    _j("j_drunkard", "Drunkard", "B", "utility"),
    _j("j_troubadour", "Troubadour", "C", "utility"),
    _j("j_merry_andy", "Merry Andy", "C", "utility"),
    _j("j_burglar", "Burglar", "C", "utility"),
    _j("j_turtle_bean", "Turtle Bean", "C", "utility"),
    _j("j_mr_bones", "Mr. Bones", "B", "utility"),
    _j("j_chicot", "Chicot", "A", "utility"),
    _j("j_ring_master", "Showman", "D", "utility"),
    _j("j_invisible", "Invisible Joker", "C", "utility", "setup"),
    _j("j_space", "Space Joker", "B", "utility", "scaling"),
    _j("j_burnt", "Burnt Joker", "B", "utility", "scaling"),
    _j("j_blue_joker", "Blue Joker", "C", "chips"),
    _j("j_luchador", "Luchador", "D", "utility", "setup"),
    _j("j_riff_raff", "Riff-raff", "D", "utility", "setup"),
    _j("j_chaos", "Chaos the Clown", "C", "utility"),
    _j("j_mail", "Mail-In Rebate", "D", "econ"),
    _j("j_hit_the_road", "Hit the Road", "D", "xmult", "scaling", "setup"),
    # --- economy ---
    _j("j_golden", "Golden Joker", "B", "econ"),
    _j("j_rocket", "Rocket", "B", "econ"),
    _j("j_cloud_9", "Cloud 9", "B", "econ"),
    _j("j_to_the_moon", "To the Moon", "C", "econ"),
    _j("j_delayed_grat", "Delayed Gratification", "C", "econ"),
    _j("j_egg", "Egg", "D", "econ"),
    _j("j_gift", "Gift Card", "D", "econ"),
    _j("j_business", "Business Card", "C", "econ", "face"),
    _j("j_faceless", "Faceless Joker", "D", "econ", "face"),
    _j("j_reserved_parking", "Reserved Parking", "C", "econ", "face"),
    _j("j_trading", "Trading Card", "D", "econ"),
    _j("j_credit_card", "Credit Card", "D", "econ"),
    _j("j_matador", "Matador", "D", "econ"),
    _j("j_todo_list", "To Do List", "D", "econ"),
    _j("j_satellite", "Satellite", "D", "econ", "setup"),
    _j("j_diet_cola", "Diet Cola", "D", "econ"),
]

BY_KEY = {j.key: j for j in JOKERS}
BY_NAME = {j.name.lower(): j for j in JOKERS}

UNKNOWN_TIER = "C"


def lookup(card):
    """Find JokerInfo for a card dict from the game state, or None."""
    info = BY_KEY.get(card.get("key"))
    if info is None and card.get("name"):
        info = BY_NAME.get(card["name"].lower())
    return info


# Vouchers worth buying for a bot that doesn't use consumables.
# Values are on the same scale as joker tier values.
VOUCHER_VALUES = {
    "v_grabber": 8,          # +1 hand per round
    "v_nacho_tong": 8,
    "v_wasteful": 6,         # +1 discard per round
    "v_recyclomancy": 6,
    "v_paint_brush": 7,      # +1 hand size
    "v_palette": 7,
    "v_antimatter": 10,      # +1 joker slot
    "v_overstock_norm": 6,   # +1 shop slot
    "v_overstock_plus": 5,
    "v_clearance_sale": 5,   # shop discounts
    "v_liquidation": 5,
    "v_reroll_surplus": 4,
    "v_reroll_glut": 4,
    "v_seed_money": 4,       # interest cap
    "v_money_tree": 4,
    "v_hone": 3,             # editions
    "v_glow_up": 3,
    "v_blank": 1,            # only useful as a step toward Antimatter
}
