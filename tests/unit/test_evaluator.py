import random

import pytest
from treys import Card as TCard
from treys import Evaluator as TEvaluator

from poker_lab.domain.cards import card_to_str, parse_cards
from poker_lab.engine.evaluator import category_name, evaluate


def ev(text: str) -> int:
    return evaluate(parse_cards(text))


@pytest.mark.parametrize(
    "cards,cat",
    [
        ("AsKsQsJsTs", "straight_flush"),
        ("5h4h3h2hAh", "straight_flush"),
        ("9c9d9h9sAd", "quads"),
        ("KcKdKh2s2d", "full_house"),
        ("2c7c9cJcAc", "flush"),
        ("Ad2c3h4s5d", "straight"),
        ("9c9d9hAsKd", "trips"),
        ("9c9dAhAsKd", "two_pair"),
        ("9c9dAhQsKd", "pair"),
        ("2c7d9hJsAd", "high_card"),
    ],
)
def test_categories(cards: str, cat: str) -> None:
    assert category_name(ev(cards)) == cat


def test_ordering_known_cases() -> None:
    assert ev("Ad2c3h4s5d") < ev("2c3h4s5d6d")  # wheel < six-high
    assert ev("AsAdKcQh2d") > ev("AsAdKcJh9d")  # kicker
    assert ev("KcKdKh2s2d3c3d") == ev("KcKdKh3s3dQhJh")  # full house uses best pair
    assert ev("KcKdKhQsQd2c2d") > ev("KcKdKh3s3d")
    assert ev("AhAc2s2d3c3dKs") == ev("AhAc3s3dKs2c4d")  # two pair uses top two pairs + kicker
    assert ev("8s8d8h4c4d4s2c") == ev("8s8d8h4c4d")  # two trips -> full house
    assert ev("2h3h4h5h7h6c6d") > ev("2c3d4s5h6c")  # flush beats straight
    assert ev("AsKsQsJs9s9h9d") < ev("9s9h9d9cAh")  # flush < quads


def test_split_board_plays() -> None:
    board = "AsKdQhJcTs"
    assert ev(board + " 2c3d") == ev(board + " 4h5h")


def test_against_treys_random() -> None:
    rng = random.Random(1234)
    tev = TEvaluator()
    mismatches = 0
    for _ in range(6000):
        deck = list(range(52))
        rng.shuffle(deck)
        board = deck[:5]
        h1 = deck[5:7]
        h2 = deck[7:9]
        ours = (evaluate(board + h1) > evaluate(board + h2)) - (evaluate(board + h1) < evaluate(board + h2))
        tb = [TCard.new(card_to_str(c)) for c in board]
        t1 = tev.evaluate(tb, [TCard.new(card_to_str(c)) for c in h1])
        t2 = tev.evaluate(tb, [TCard.new(card_to_str(c)) for c in h2])
        theirs = (t1 < t2) - (t1 > t2)  # treys: lower is better
        if ours != theirs:
            mismatches += 1
    assert mismatches == 0


def test_against_treys_five_card_class_ranks() -> None:
    rng = random.Random(99)
    tev = TEvaluator()
    hands = []
    for _ in range(1500):
        cards = rng.sample(range(52), 5)
        hands.append((evaluate(cards), tev.evaluate([TCard.new(card_to_str(c)) for c in cards[:3]], [TCard.new(card_to_str(c)) for c in cards[3:]])))
    ours_sorted = sorted(range(len(hands)), key=lambda i: hands[i][0])
    # strictly consistent ordering: if ours says a < b then treys says a worse-or-equal
    for a, b in zip(ours_sorted, ours_sorted[1:], strict=False):
        if hands[a][0] < hands[b][0]:
            assert hands[a][1] > hands[b][1]
        else:
            assert hands[a][1] == hands[b][1]
