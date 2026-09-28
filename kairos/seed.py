"""Load a business and its catalog from a YAML file.

    python -m kairos.seed seeds/demo_business.yaml

Idempotent: the business is matched on wa_phone_number_id and catalog items on
name, so re-running updates in place. Items missing from the file are left alone.
"""

import asyncio
import sys
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel
from sqlalchemy.dialects.postgresql import insert

from kairos.config import get_settings, normalize_phone
from kairos.db.models import Business, CatalogItem
from kairos.db.session import get_sessionmaker
from kairos.domain.business import BusinessSettings


class BusinessSeed(BaseModel):
    name: str
    wa_phone_number_id: str | None = None
    timezone: str = "Asia/Karachi"
    owner_phones: list[str] = []
    settings: BusinessSettings


class CatalogItemSeed(BaseModel):
    name: str
    aliases: list[str] = []
    price: int
    unit: str
    available: bool = True
    category: str | None = None


class SeedFile(BaseModel):
    business: BusinessSeed
    catalog: list[CatalogItemSeed]


def load_seed(path: Path) -> SeedFile:
    return SeedFile.model_validate(yaml.safe_load(path.read_text()))


async def apply_seed(seed: SeedFile) -> int:
    b = seed.business
    phone_number_id = b.wa_phone_number_id or get_settings().wa_phone_number_id
    if not phone_number_id:
        raise SystemExit("wa_phone_number_id missing from the seed file and WA_PHONE_NUMBER_ID unset")

    values: dict[str, Any] = {
        "name": b.name,
        "timezone": b.timezone,
        "owner_phones": [normalize_phone(p) for p in b.owner_phones],
        "settings": b.settings.model_dump(),
    }
    async with get_sessionmaker()() as session:
        business_id = await session.scalar(
            insert(Business)
            .values(wa_phone_number_id=phone_number_id, **values)
            .on_conflict_do_update(index_elements=[Business.wa_phone_number_id], set_=values)
            .returning(Business.id)
        )
        for item in seed.catalog:
            data = item.model_dump()
            await session.execute(
                insert(CatalogItem)
                .values(business_id=business_id, **data)
                .on_conflict_do_update(index_elements=[CatalogItem.business_id, CatalogItem.name],
                                       set_=data)
            )
        await session.commit()
    return business_id


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m kairos.seed <file.yaml>")
    seed = load_seed(Path(sys.argv[1]))
    business_id = asyncio.run(apply_seed(seed))
    print(f"seeded business {business_id} ({seed.business.name}) with {len(seed.catalog)} catalog items")


if __name__ == "__main__":
    main()
