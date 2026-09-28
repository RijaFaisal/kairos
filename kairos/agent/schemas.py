"""Structured output the LLM must return (ARCHITECTURE.md section 5.2)."""

from typing import Literal

from pydantic import BaseModel, Field


class ItemMention(BaseModel):
    name: str = Field(description="The item exactly as the customer wrote it, without the quantity.")
    quantity: int | None = Field(
        default=None, description="How many, if the customer said. Null if not stated."
    )
    action: Literal["add", "remove", "set"] = Field(
        default="add",
        description="add: wants (more of) it. remove: drop it. set: change to exactly this quantity.",
    )


class Extraction(BaseModel):
    intent: Literal["new_order", "modify_order", "confirm", "cancel",
                    "ask_catalog", "ask_status", "complaint", "greeting", "other"]
    items: list[ItemMention] = Field(default_factory=list)
    delivery_address: str | None = None
    delivery_time: str | None = Field(default=None, description="Raw text; parsed by code.")
    payment_method: Literal["cash", "online"] | None = None
    language: Literal["en", "ur", "roman_ur", "mixed"]
    confidence: float = Field(ge=0.0, le=1.0)
