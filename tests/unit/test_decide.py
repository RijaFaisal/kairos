"""Phase 1 decision step: the LLM's extraction is checked and priced in code."""

from kairos.agent.decide import (
    Ambiguous,
    AskQuantity,
    CreateOrder,
    NotFound,
    Reply,
    Unavailable,
    decide,
)
from kairos.agent.schemas import Extraction, ItemMention
from tests.unit.catalogs import CLOTHING, FOOD


def ext(intent="new_order", items=(), confidence=0.9, **kw):
    return Extraction(intent=intent, items=[ItemMention(**i) for i in items],
                      language="roman_ur", confidence=confidence, **kw)


def test_food_order_is_priced_by_code():
    d = decide(ext(items=[{"name": "chicken wale", "quantity": 2},
                          {"name": "rolls", "quantity": 1}]), FOOD)
    assert isinstance(d, CreateOrder)
    assert d.quote.total == 2 * 650 + 400


def test_clothing_order_is_priced_by_code():
    d = decide(ext(items=[{"name": "kurta", "quantity": 1}, {"name": "dupata", "quantity": 2}],
                   delivery_address="House 5, DHA"), CLOTHING)
    assert isinstance(d, CreateOrder)
    assert d.quote.total == 3500 + 2 * 2200
    assert d.delivery_address == "House 5, DHA"


def test_missing_quantity_is_asked_not_guessed():
    d = decide(ext(items=[{"name": "shawl"}]), CLOTHING)
    assert d == AskQuantity(("Khaddar Shawl",))


def test_zero_quantity_is_asked():
    assert isinstance(decide(ext(items=[{"name": "beef", "quantity": 0}]), FOOD), AskQuantity)


def test_unknown_item():
    d = decide(ext(items=[{"name": "kurta", "quantity": 1}]), FOOD)
    assert d == NotFound(("kurta",))


def test_ambiguous_item():
    assert isinstance(decide(ext(items=[{"name": "dumplings", "quantity": 2}]), FOOD), Ambiguous)


def test_unavailable_item():
    d = decide(ext(items=[{"name": "chutney", "quantity": 1}]), FOOD)
    assert d == Unavailable(("Mint Chutney",))


def test_low_confidence_is_not_acted_on():
    d = decide(ext(items=[{"name": "kurta", "quantity": 1}], confidence=0.2), CLOTHING)
    assert d == Reply("not_understood")


def test_non_order_intents():
    assert decide(ext(intent="greeting"), FOOD) == Reply("greeting")
    assert decide(ext(intent="ask_catalog"), CLOTHING) == Reply("catalog")
    assert decide(ext(intent="complaint"), FOOD) == Reply("received")
