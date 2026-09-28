"""Phase 1 reply text, filled from facts decided in code.

Wording here is generic; anything specific to a business (its name, greeting,
currency label) comes from BusinessSettings. From Phase 2 the LLM writes replies.
"""

from collections.abc import Sequence

from kairos.domain.business import BusinessSettings
from kairos.domain.catalog import CatalogItem
from kairos.domain.pricing import Quote

TEXT = {
    "en": {
        "greeting": "Hi! Welcome to {business}. What would you like to order?",
        "order_header": "Your order #{order_no}:",
        "total": "Total: {amount}",
        "confirm_prompt": "Reply YES to confirm.",
        "ask_quantity": "How many would you like of: {items}?",
        "not_found": "Sorry, I couldn't find: {items}. Ask us for the list to see what we have.",
        "ambiguous": "Which one did you mean for \"{mention}\": {options}?",
        "unavailable": "Sorry, {items} is not available right now.",
        "catalog_header": "Here's what we have:",
        "text_only": "Sorry, I can only read text messages for now. Please type your order.",
        "not_understood": "Sorry, I didn't understand. Please tell me what you'd like to order.",
        "received": "Thanks, we've received your message. The {business} team will get back to you.",
    },
    "roman_ur": {
        "greeting": "Assalam o Alaikum! {business} mein khush aamdeed. Aap kya order karna chahenge?",
        "order_header": "Aap ka order #{order_no}:",
        "total": "Total: {amount}",
        "confirm_prompt": "Confirm karne ke liye YES likhein.",
        "ask_quantity": "Yeh kitne chahiye: {items}?",
        "not_found": "Maaf kijiye, yeh nahi mila: {items}. Hamari list mangwa kar dekh lein.",
        "ambiguous": "\"{mention}\" se aap ki muraad kaunsa hai: {options}?",
        "unavailable": "Maaf kijiye, {items} abhi available nahi hai.",
        "catalog_header": "Hamare paas yeh hai:",
        "text_only": "Maaf kijiye, abhi sirf text message parh sakte hain. Apna order likh kar bhejein.",
        "not_understood": "Maaf kijiye, samajh nahi aaya. Bataiye aap kya order karna chahenge?",
        "received": "Shukriya, aap ka message mil gaya hai. {business} ki team jald aap se rabta karegi.",
    },
}


class Replies:
    def __init__(self, business_name: str, settings: BusinessSettings, language: str | None):
        # Urdu script and mixed messages get Roman Urdu until the LLM writes replies.
        self._t = TEXT["en"] if language in (None, "en") else TEXT["roman_ur"]
        self._business = business_name
        self._settings = settings

    def _money(self, amount: int) -> str:
        return f"{self._settings.currency_label} {amount:,}"

    def greeting(self) -> str:
        return self._settings.greeting or self._t["greeting"].format(business=self._business)

    def order_summary(self, order_no: int, quote: Quote) -> str:
        lines = [self._t["order_header"].format(order_no=order_no)]
        lines += [
            f"- {line.quantity} x {line.item.name} ({line.item.unit}) = {self._money(line.line_total)}"
            for line in quote.lines
        ]
        lines += [self._t["total"].format(amount=self._money(quote.total)), self._t["confirm_prompt"]]
        return "\n".join(lines)

    def ask_quantity(self, names: Sequence[str]) -> str:
        return self._t["ask_quantity"].format(items=", ".join(names))

    def not_found(self, mentions: Sequence[str]) -> str:
        return self._t["not_found"].format(items=", ".join(mentions))

    def ambiguous(self, mention: str, options: Sequence[CatalogItem]) -> str:
        return self._t["ambiguous"].format(mention=mention, options=", ".join(o.name for o in options))

    def unavailable(self, names: Sequence[str]) -> str:
        return self._t["unavailable"].format(items=", ".join(names))

    def catalog(self, items: Sequence[CatalogItem]) -> str:
        lines = [self._t["catalog_header"]]
        lines += [f"- {i.name} ({i.unit}): {self._money(i.price)}" for i in items if i.available]
        return "\n".join(lines)

    def text_only(self) -> str:
        return self._t["text_only"]

    def not_understood(self) -> str:
        return self._t["not_understood"]

    def received(self) -> str:
        return self._t["received"].format(business=self._business)
