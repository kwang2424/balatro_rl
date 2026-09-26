"""Hand-play heuristics: a small poker-hand evaluator and a greedy policy.

Scores are estimates that ignore jokers, enhancements and boss effects: the
hand type's current chips/mult (from the game state, so planet levels count)
plus the chip value of the scoring cards.
"""

from collections import Counter
from itertools import combinations

RANKS = "23456789TJQKA"
RANK_VALUE = {r: i + 2 for i, r in enumerate(RANKS)}
CARD_CHIPS = {**{r: RANK_VALUE[r] for r in "23456789"}, "T": 10, "J": 10, "Q": 10,
              "K": 10, "A": 11}

# Base (chips, mult) at level 1, used if the game state has no hand info
BASE_HANDS = {
    "Flush Five": (160, 16),
    "Flush House": (140, 14),
    "Five of a Kind": (120, 12),
    "Straight Flush": (100, 8),
    "Four of a Kind": (60, 7),
    "Full House": (40, 4),
    "Flush": (35, 4),
    "Straight": (30, 4),
    "Three of a Kind": (30, 3),
    "Two Pair": (20, 2),
    "Pair": (10, 2),
    "High Card": (5, 1),
}


def _value(card):
    v = card.get("value") or {}
    return v.get("rank"), v.get("suit")


def _is_straight(ranks):
    if len(ranks) != 5:
        return False
    vals = sorted({RANK_VALUE[r] for r in ranks})
    if len(vals) != 5:
        return False
    return vals[-1] - vals[0] == 4 or vals == [2, 3, 4, 5, 14]  # A-2-3-4-5


def classify(cards):
    """Return (hand_name, scoring_cards) for the cards played."""
    ranked = [c for c in cards if _value(c)[0] in RANK_VALUE]  # skips stone cards
    ranks = [_value(c)[0] for c in ranked]
    suits = [_value(c)[1] for c in ranked]
    counts = Counter(ranks)
    shape = sorted(counts.values(), reverse=True)

    flush = len(ranked) == 5 and len(set(suits)) == 1
    straight = _is_straight(ranks)

    if shape and shape[0] == 5:
        return ("Flush Five" if flush else "Five of a Kind"), ranked
    if flush and shape[:2] == [3, 2]:
        return "Flush House", ranked
    if flush and straight:
        return "Straight Flush", ranked
    if shape and shape[0] == 4:
        return "Four of a Kind", [c for c in ranked if counts[_value(c)[0]] == 4]
    if shape[:2] == [3, 2]:
        return "Full House", ranked
    if flush:
        return "Flush", ranked
    if straight:
        return "Straight", ranked
    if shape and shape[0] == 3:
        return "Three of a Kind", [c for c in ranked if counts[_value(c)[0]] == 3]
    if shape[:2] == [2, 2]:
        return "Two Pair", [c for c in ranked if counts[_value(c)[0]] == 2]
    if shape and shape[0] == 2:
        return "Pair", [c for c in ranked if counts[_value(c)[0]] == 2]
    if ranked:
        return "High Card", [max(ranked, key=lambda c: RANK_VALUE[_value(c)[0]])]
    return "High Card", []


def estimate_score(cards, hands_info=None):
    name, scoring = classify(cards)
    info = (hands_info or {}).get(name)
    chips, mult = (info["chips"], info["mult"]) if info else BASE_HANDS[name]
    chips += sum(CARD_CHIPS[_value(c)[0]] for c in scoring
                 if not (c.get("state") or {}).get("debuff"))
    return chips * mult, name


def all_plays(hand_cards, hands_info=None):
    """(score, indices, hand_name) for every 1-5 card play, best first."""
    plays = []
    for k in range(1, min(5, len(hand_cards)) + 1):
        for idx in combinations(range(len(hand_cards)), k):
            score, name = estimate_score([hand_cards[i] for i in idx], hands_info)
            plays.append((score, list(idx), name))
    plays.sort(key=lambda p: -p[0])
    return plays


def best_play(hand_cards, hands_info=None):
    """(score, indices, hand_name) of the best 1-5 card play."""
    plays = all_plays(hand_cards, hands_info)
    return plays[0] if plays else (-1, [], None)


def shortlist(plays, per_type):
    """Top `per_type` plays of each hand type (plays sorted best first)."""
    kept, counts = [], Counter()
    for play in plays:
        if counts[play[2]] < per_type:
            counts[play[2]] += 1
            kept.append(play)
    return kept


def current_blind_score(G):
    for blind in (G.get("blinds") or {}).values():
        if blind.get("status") == "CURRENT":
            return blind.get("score") or 0
    return 0


class HandPolicy:
    """Greedy hand play that chases flushes with discards.

    Plays the best available hand when it's a flush or better, or when it is on
    pace to beat the blind with the hands left. Otherwise discards cards that
    are off the most common suit (lowest first). With no discards left it just
    plays the best hand.
    """

    STRONG_HANDS = {"Flush", "Straight Flush", "Four of a Kind", "Full House",
                    "Five of a Kind", "Flush House", "Flush Five"}

    def __init__(self, chase_flush=True, scorer=None, per_type=3):
        """
        scorer:   optional callable(list of index lists) -> list of exact scores,
                  e.g. SimClient.score_plays. Without it, plays are ranked by
                  estimate_score, which ignores jokers.
        per_type: with a scorer, how many plays of each hand type to rescore
        """
        self.chase_flush = chase_flush
        self.scorer = scorer
        self.per_type = per_type

    def __call__(self, G):
        return self.choose(G)

    def choose(self, G):
        cards = list((G.get("hand") or {}).get("cards") or [])
        rnd = G.get("round") or {}
        hands_left = rnd.get("hands_left", 1)
        discards_left = rnd.get("discards_left", 0)
        need = max(current_blind_score(G) - (rnd.get("chips") or 0), 0)

        plays = all_plays(cards, G.get("hands"))
        if not plays:
            return ("play", {"cards": [0]})
        if self.scorer:
            plays = shortlist(plays, self.per_type)
            exact = self.scorer([p[1] for p in plays])
            plays = sorted(((e, idx, name) for e, (_, idx, name) in zip(exact, plays)),
                           key=lambda p: -p[0])
        score, idx, name = plays[0]
        on_pace = score * max(hands_left, 1) >= need
        if name in self.STRONG_HANDS or on_pace or discards_left <= 0:
            return ("play", {"cards": idx})

        return ("discard", {"cards": self._discard_choice(cards, idx)})

    def _discard_choice(self, cards, keep):
        by_rank = lambda i: RANK_VALUE.get(_value(cards[i])[0], 0)
        if self.chase_flush:
            suits = Counter(_value(c)[1] for c in cards if _value(c)[1])
            if suits:
                target = suits.most_common(1)[0][0]
                off = [i for i, c in enumerate(cards) if _value(c)[1] != target]
                if off:
                    return sorted(off, key=by_rank)[:5]
        rest = [i for i in range(len(cards)) if i not in keep] or list(range(len(cards)))
        return sorted(rest, key=by_rank)[:5]
