from rates_risk.book import CashTreasury, Future, Swap, Swaption


def test_book_has_exactly_forty_positions(book):
    assert len(book) == 40


def test_book_has_one_swaption(book):
    swaptions = [p for p in book if isinstance(p, Swaption)]
    assert len(swaptions) == 1


def test_book_covers_all_four_product_types(book):
    types = {type(p) for p in book}
    assert types == {CashTreasury, Future, Swap, Swaption}


def test_position_ids_are_unique(book):
    ids = [p.position_id for p in book]
    assert len(ids) == len(set(ids))


def test_cash_treasury_count_and_future_count(book):
    assert sum(isinstance(p, CashTreasury) for p in book) == 16
    assert sum(isinstance(p, Future) for p in book) == 12
    assert sum(isinstance(p, Swap) for p in book) == 11
