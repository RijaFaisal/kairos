"""Match what a customer typed to an item in a business's catalog.

Pure Python: the catalog is passed in, nothing here knows about any particular
business or product type.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from enum import StrEnum

# Words that carry no product meaning in English / Roman Urdu order messages,
# e.g. "2 large wale", "ek plate ka", "some of the".
FILLER_WORDS = frozenset(
    {
        "a", "an", "the", "some", "of", "please", "pls", "plz",
        "wala", "wale", "wali", "walay", "waly", "walen",
        "ka", "ki", "ke", "ko", "aur", "and", "bhi",
    }
)

FUZZY_THRESHOLD = 0.8
FUZZY_MARGIN = 0.1


@dataclass(frozen=True)
class CatalogItem:
    id: int
    name: str
    price: int  # whole units of the business's currency
    unit: str
    aliases: tuple[str, ...] = ()
    available: bool = True
    category: str | None = None


class MatchStatus(StrEnum):
    matched = "matched"
    ambiguous = "ambiguous"
    not_found = "not_found"


@dataclass(frozen=True)
class MatchResult:
    status: MatchStatus
    item: CatalogItem | None = None
    candidates: tuple[CatalogItem, ...] = field(default=())


def normalize(text: str) -> str:
    text = re.sub(r"[^\w\s]", " ", text.lower())
    tokens = [_singular(t) for t in text.split() if t not in FILLER_WORDS]
    return " ".join(tokens)


def _singular(token: str) -> str:
    # Crude, but applied to both sides of every comparison so it only has to be
    # consistent, not linguistically correct.
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _names(item: CatalogItem) -> list[str]:
    return [n for n in (normalize(x) for x in (item.name, *item.aliases)) if n]


def match_item(mention: str, catalog: Sequence[CatalogItem]) -> MatchResult:
    """Resolve one item mention against the catalog.

    Order of checks: exact name/alias, then "all the words the customer used
    appear in one item's name", then fuzzy similarity. A match is only returned
    when exactly one item qualifies; otherwise the caller should ask.
    """
    wanted = normalize(mention)
    if not wanted:
        return MatchResult(MatchStatus.not_found)

    exact = [item for item in catalog if wanted in _names(item)]
    if exact:
        return _single(exact)

    wanted_tokens = set(wanted.split())
    contained = [
        item for item in catalog if any(wanted_tokens <= set(n.split()) for n in _names(item))
    ]
    if contained:
        return _single(contained)

    scored = sorted(
        ((max(SequenceMatcher(None, wanted, n).ratio() for n in _names(item)), item)
         for item in catalog if _names(item)),
        key=lambda pair: pair[0],
        reverse=True,
    )
    if not scored or scored[0][0] < FUZZY_THRESHOLD:
        return MatchResult(MatchStatus.not_found)
    best_score, best = scored[0]
    close = [item for score, item in scored if best_score - score < FUZZY_MARGIN]
    if len(close) > 1:
        return MatchResult(MatchStatus.ambiguous, candidates=tuple(close))
    return MatchResult(MatchStatus.matched, item=best)


def _single(items: list[CatalogItem]) -> MatchResult:
    if len(items) == 1:
        return MatchResult(MatchStatus.matched, item=items[0])
    return MatchResult(MatchStatus.ambiguous, candidates=tuple(items))
