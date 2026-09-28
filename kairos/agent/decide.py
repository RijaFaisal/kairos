"""Phase 1 decision step: Extraction + catalog -> what to do. Pure Python.

The LLM's output is treated as a claim about what the customer said; every
product, quantity and price is checked or computed here.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from kairos.agent.schemas import Extraction
from kairos.domain.catalog import CatalogItem, MatchStatus, match_item
from kairos.domain.pricing import Quote, quote

MIN_CONFIDENCE = 0.5


@dataclass(frozen=True)
class CreateOrder:
    quote: Quote
    delivery_address: str | None
    delivery_time: str | None
    payment_method: str | None


@dataclass(frozen=True)
class AskQuantity:
    names: tuple[str, ...]


@dataclass(frozen=True)
class NotFound:
    mentions: tuple[str, ...]


@dataclass(frozen=True)
class Ambiguous:
    mention: str
    options: tuple[CatalogItem, ...]


@dataclass(frozen=True)
class Unavailable:
    names: tuple[str, ...]


@dataclass(frozen=True)
class Reply:
    """A reply with no order change: greeting, catalog, not_understood, received."""
    kind: str


Decision = CreateOrder | AskQuantity | NotFound | Ambiguous | Unavailable | Reply


def decide(extraction: Extraction, catalog: Sequence[CatalogItem]) -> Decision:
    if extraction.confidence < MIN_CONFIDENCE:
        return Reply("not_understood")
    match extraction.intent:
        case "greeting" if not extraction.items:
            return Reply("greeting")
        case "ask_catalog":
            return Reply("catalog")
        case "new_order":
            return _new_order(extraction, catalog)
        case "other":
            return Reply("not_understood")
        case _:
            # modify / confirm / cancel / status / complaint: handled in Phase 2.
            return Reply("received")


def _new_order(extraction: Extraction, catalog: Sequence[CatalogItem]) -> Decision:
    wanted = [m for m in extraction.items if m.action != "remove"]
    if not wanted:
        return Reply("not_understood")

    resolved: list[tuple[CatalogItem, int | None]] = []
    not_found: list[str] = []
    for mention in wanted:
        result = match_item(mention.name, catalog)
        if result.status is MatchStatus.ambiguous:
            return Ambiguous(mention.name, result.candidates)
        if result.status is MatchStatus.not_found:
            not_found.append(mention.name)
            continue
        resolved.append((result.item, mention.quantity))

    if not_found:
        return NotFound(tuple(not_found))
    unavailable = [item.name for item, _ in resolved if not item.available]
    if unavailable:
        return Unavailable(tuple(unavailable))
    missing_qty = [item.name for item, qty in resolved if qty is None or qty < 1]
    if missing_qty:
        return AskQuantity(tuple(missing_qty))

    return CreateOrder(
        quote=quote([(item, qty) for item, qty in resolved]),
        delivery_address=extraction.delivery_address,
        delivery_time=extraction.delivery_time,
        payment_method=extraction.payment_method,
    )
