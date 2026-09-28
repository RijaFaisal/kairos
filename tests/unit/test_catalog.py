import pytest

from kairos.domain.catalog import CatalogItem, MatchStatus, match_item, normalize
from tests.unit.catalogs import CLOTHING, FOOD


def matched_name(mention, catalog):
    result = match_item(mention, catalog)
    assert result.status is MatchStatus.matched, (mention, result)
    return result.item.name


@pytest.mark.parametrize(
    ("catalog", "mention", "expected"),
    [
        # exact name, any case
        (FOOD, "Chicken Dumplings", "Chicken Dumplings"),
        (CLOTHING, "silk dupatta", "Silk Dupatta"),
        # aliases
        (FOOD, "chkn dumplings", "Chicken Dumplings"),
        (CLOTHING, "kurta", "Cotton Kurta"),
        (CLOTHING, "3 piece", "Lawn Suit 3 Piece"),
        # Roman Urdu filler words
        (FOOD, "chicken wale", "Chicken Dumplings"),
        (CLOTHING, "shawl wali", "Khaddar Shawl"),
        # plural / singular
        (FOOD, "beef dumpling", "Beef Dumplings"),
        (CLOTHING, "kurtas", "Cotton Kurta"),
        # typos
        (FOOD, "chiken dumplings", "Chicken Dumplings"),
        (CLOTHING, "cotton kurtaa", "Cotton Kurta"),
        (CLOTHING, "dupata", "Silk Dupatta"),
        # punctuation
        (FOOD, "spring-rolls!!", "Veg Spring Rolls"),
    ],
)
def test_matches(catalog, mention, expected):
    assert matched_name(mention, catalog) == expected


def test_unavailable_items_still_match_so_the_caller_can_say_so():
    result = match_item("chutney", FOOD)
    assert result.status is MatchStatus.matched
    assert result.item.available is False


@pytest.mark.parametrize(
    ("catalog", "mention"),
    [
        (FOOD, "pizza"),
        (FOOD, "kurta"),         # clothing word against a food catalog
        (CLOTHING, "chicken"),   # food word against a clothing catalog
        (CLOTHING, ""),
        (CLOTHING, "please"),    # nothing left after removing filler
    ],
)
def test_not_found(catalog, mention):
    assert match_item(mention, catalog).status is MatchStatus.not_found


def test_word_shared_by_several_items_is_ambiguous():
    result = match_item("dumplings", FOOD)
    assert result.status is MatchStatus.ambiguous
    assert {i.name for i in result.candidates} == {"Chicken Dumplings", "Beef Dumplings"}


def test_ambiguous_in_clothing_catalog():
    fabric = CatalogItem(id=105, name="Cotton Fabric", price=1000, unit="metre")
    result = match_item("cotton", CLOTHING + [fabric])
    assert result.status is MatchStatus.ambiguous


def test_empty_catalog():
    assert match_item("anything", []).status is MatchStatus.not_found


def test_normalize_keeps_digits_so_sizes_stay_distinct():
    assert normalize("Size 42") != normalize("Size 44")
