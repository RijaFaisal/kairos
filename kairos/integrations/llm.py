"""LLM access. The model only ever returns an Extraction; it is never shown
prices and never asked to decide anything."""

import logging

import anthropic

from kairos.agent.prompts.extraction import EXTRACTION_SYSTEM, catalog_block
from kairos.agent.schemas import Extraction
from kairos.config import Settings
from kairos.domain.catalog import CatalogItem

log = logging.getLogger(__name__)


class ExtractionFailed(RuntimeError):
    pass


class LLMClient:
    def __init__(self, settings: Settings):
        if settings.llm_provider != "anthropic":
            raise RuntimeError(f"LLM_PROVIDER={settings.llm_provider!r} is not supported yet")
        if not settings.llm_model or not settings.llm_api_key:
            raise RuntimeError("LLM_MODEL and LLM_API_KEY must be set")
        self._model = settings.llm_model
        self._client = anthropic.AsyncAnthropic(api_key=settings.llm_api_key)

    async def extract(self, text: str, catalog: list[CatalogItem]) -> Extraction:
        system = f"{EXTRACTION_SYSTEM}\n{catalog_block([(i.name, i.unit) for i in catalog])}"
        response = await self._client.messages.parse(
            model=self._model,
            max_tokens=2048,
            system=system,
            messages=[{"role": "user", "content": text}],
            output_format=Extraction,
        )
        if response.stop_reason == "refusal" or response.parsed_output is None:
            log.warning("extraction returned no output (stop_reason=%s, request_id=%s)",
                        response.stop_reason, response._request_id)
            raise ExtractionFailed(response.stop_reason or "no output")
        return response.parsed_output

    async def close(self) -> None:
        await self._client.close()
