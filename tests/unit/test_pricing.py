import pytest

from kairos.domain.catalog import CatalogItem
from kairos.domain.pricing import PricingError, price_line, quote
from tests.unit.catalogs import CLOTHING, FOOD

chicken, beef, rolls, chutney = FOOD
kurta, lawn, dupatta, shawl = CLOTHING


def test_single_line():
    line = price_line(chicken, 3)
    assert (line.unit_price, line.line_total) == (650, 1950)


def test_food_basket_total():
    q = quote([(chicken, 2), (rolls, 1)])
    assert [l.line_total for l in q.lines] == [1300, 400]
    assert q.total == 1700


def test_clothing_basket_total():
    q = quote([(lawn, 1), (dupatta, 2), (shawl, 1)])
    assert q.total == 6800 + 4400 + 4500


def test_same_item_twice_is_merged():
    q = quote([(kurta, 1), (dupatta, 1), (kurta, 2)])
    assert [(l.item.name, l.quantity) for l in q.lines] == [("Cotton Kurta", 3), ("Silk Dupatta", 1)]
    assert q.total == 3 * 3500 + 2200


def test_totals_are_integers():
    q = quote([(beef, 7)])
    assert isinstance(q.total, int) and q.total == 5250


def test_empty_basket():
    assert quote([]).total == 0


@pytest.mark.parametrize("qty", [0, -1])
def test_quantity_must_be_positive(qty):
    with pytest.raises(PricingError):
        price_line(kurta, qty)


@pytest.mark.parametrize("qty", [1.5, "2", None, True])
def test_quantity_must_be_whole_number(qty):
    with pytest.raises(PricingError):
        price_line(chicken, qty)


def test_bad_quantity_is_not_hidden_by_merging():
    with pytest.raises(PricingError):
        quote([(kurta, -1), (kurta, 3)])


def test_unavailable_item_cannot_be_priced():
    with pytest.raises(PricingError):
        quote([(chicken, 1), (chutney, 1)])


def test_price_comes_from_catalog_item():
    discounted = CatalogItem(id=1, name="Chicken Dumplings", price=500, unit="plate of 8")
    assert quote([(discounted, 2)]).total == 1000
