import itertools
from datetime import UTC, datetime

import pytest

from kairos.domain.enums import Actor, OrderStatus as S
from kairos.domain.orders import (
    FORWARD,
    InvalidTransition,
    allowed_next,
    can_transition,
    start_order,
    transition,
)
from kairos.domain.pricing import quote
from tests.unit.catalogs import CLOTHING, FOOD

HAPPY_PATH = [S.draft, S.awaiting_confirmation, S.confirmed, S.preparing,
              S.out_for_delivery, S.delivered]
T0 = datetime(2026, 1, 1, tzinfo=UTC)


def new_order(catalog=FOOD):
    return start_order(business_id=1, customer_id=1, order_no=14,
                       quote=quote([(catalog[0], 2)]), actor=Actor.bot, at=T0)


@pytest.mark.parametrize("catalog", [FOOD, CLOTHING])
def test_start_order_is_draft_with_items_and_creation_event(catalog):
    order = new_order(catalog)
    assert order.status is S.draft
    assert order.total == catalog[0].price * 2
    assert [(i.catalog_item_id, i.quantity, i.line_total) for i in order.items] == [
        (catalog[0].id, 2, catalog[0].price * 2)
    ]
    [event] = order.events
    assert (event.from_status, event.to_status, event.actor) == (None, S.draft, Actor.bot)


def test_full_happy_path_records_every_step():
    order = new_order()
    for status in HAPPY_PATH[1:]:
        transition(order, status, Actor.owner)
    assert order.status is S.delivered
    assert [(e.from_status, e.to_status) for e in order.events[1:]] == list(
        itertools.pairwise(HAPPY_PATH)
    )


@pytest.mark.parametrize("status", HAPPY_PATH[:-1])
def test_can_cancel_from_any_state_before_delivered(status):
    assert can_transition(status, S.cancelled)


@pytest.mark.parametrize("status", [S.delivered, S.cancelled])
def test_terminal_states_allow_nothing(status):
    assert allowed_next(status) == frozenset()


def test_every_disallowed_pair_is_rejected():
    for from_status, to_status in itertools.product(S, S):
        expected = to_status == FORWARD.get(from_status) or (
            to_status is S.cancelled and from_status not in (S.delivered, S.cancelled)
        )
        assert can_transition(from_status, to_status) is expected, (from_status, to_status)


@pytest.mark.parametrize(
    ("path", "bad"),
    [
        ([], S.confirmed),                                  # skip awaiting_confirmation
        ([], S.delivered),                                  # jump to the end
        ([S.awaiting_confirmation], S.draft),               # no going back
        ([S.awaiting_confirmation, S.confirmed], S.confirmed),  # no self-transition
        ([S.cancelled], S.draft),                           # cancelled is final
        (HAPPY_PATH[1:], S.cancelled),                      # delivered can't be cancelled
    ],
)
def test_invalid_transition_raises_and_changes_nothing(path, bad):
    order = new_order()
    for status in path:
        transition(order, status, Actor.bot)
    status_before, events_before = order.status, len(order.events)
    with pytest.raises(InvalidTransition):
        transition(order, bad, Actor.customer)
    assert order.status is status_before
    assert len(order.events) == events_before


def test_transition_records_actor_and_time():
    order = new_order()
    at = datetime(2026, 1, 2, 10, 30, tzinfo=UTC)
    event = transition(order, S.cancelled, Actor.customer, at=at)
    assert (event.from_status, event.to_status, event.actor, event.at) == (
        S.draft, S.cancelled, Actor.customer, at
    )
    assert order.updated_at == at
