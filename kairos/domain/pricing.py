"""Prices and totals. Always computed here, never by the LLM."""

from collections.abc import Sequence
from dataclasses import dataclass

from kairos.domain.catalog import CatalogItem


class PricingError(ValueError):
    pass


@dataclass(frozen=True)
class PricedLine:
    item: CatalogItem
    quantity: int
    unit_price: int
    line_total: int


@dataclass(frozen=True)
class Quote:
    lines: tuple[PricedLine, ...]
    total: int


def _check_quantity(quantity: int) -> None:
    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise PricingError(f"quantity must be a whole number, got {quantity!r}")
    if quantity < 1:
        raise PricingError(f"quantity must be at least 1, got {quantity}")


def price_line(item: CatalogItem, quantity: int) -> PricedLine:
    _check_quantity(quantity)
    if not item.available:
        raise PricingError(f"{item.name} is not available")
    return PricedLine(item=item, quantity=quantity, unit_price=item.price,
                      line_total=item.price * quantity)


def quote(lines: Sequence[tuple[CatalogItem, int]]) -> Quote:
    """Price a basket of (item, quantity). The same item twice is merged."""
    merged: dict[int, tuple[CatalogItem, int]] = {}
    for item, quantity in lines:
        _check_quantity(quantity)
        if item.id in merged:
            quantity = merged[item.id][1] + quantity
        merged[item.id] = (item, quantity)
    priced = tuple(price_line(item, qty) for item, qty in merged.values())
    return Quote(lines=priced, total=sum(line.line_total for line in priced))
