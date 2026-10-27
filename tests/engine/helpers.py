from poker_lab.domain.cards import parse_cards


def make_deck(holes: list[str], board: str = "") -> list[int]:
    """Deck that deals the given hole cards (seat order) then burn/flop/burn/turn/burn/river."""
    hole_cards = [c for h in holes for c in parse_cards(h)]
    board_cards = parse_cards(board) if board else []
    used = set(hole_cards) | set(board_cards)
    rest = [c for c in range(52) if c not in used]
    deck = list(hole_cards)
    seq: list[int] = []
    if board_cards:
        seq = [rest.pop(), *board_cards[:3], rest.pop(), board_cards[3], rest.pop(), board_cards[4]]
    deck += seq + rest
    assert sorted(deck) == list(range(52))
    return deck
