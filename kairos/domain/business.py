"""Per-business settings, stored in businesses.settings (JSONB).

Anything that differs between businesses (wording, currency, delivery rules)
belongs here, not in code.
"""

from typing import Any

from pydantic import BaseModel, ConfigDict


class BusinessSettings(BaseModel):
    model_config = ConfigDict(extra="allow")

    currency_label: str
    greeting: str | None = None
    # Free-form until delivery slot validation lands in Phase 2.
    delivery_rules: dict[str, Any] = {}
