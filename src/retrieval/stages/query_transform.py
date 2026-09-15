"""Query transform stage: make raw user queries more effective for search."""

import re
from abc import ABC, abstractmethod

from src.config import settings
from src.retrieval.llm import LLM, OpenAICompatibleLLM
from src.retrieval.models import Query


class QueryTransformStage(ABC):
    """Applies query optimization (reword, expand, HyDE) before search."""

    @abstractmethod
    def transform(self, query: Query) -> list[str]:
        """Return one or more search-ready query texts for ``query``."""


class IdentityQueryTransform(QueryTransformStage):
    """Pass the query through unchanged (whitespace-stripped)."""

    def transform(self, query: Query) -> list[str]:
        return [query.text.strip()]


_BULLET = re.compile(r"^[\s\-\*\d.]+")


class ExpansionQueryTransform(QueryTransformStage):
    """Generate alternative phrasings with the LLM and search all of them."""

    PROMPT = (
        "Write {count} alternative phrasings of the following question that capture "
        "the same intent. Output one phrasing per line, with no numbering or bullets.\n"
        "Question: {question}"
    )

    def __init__(self, llm: LLM | None = None, num_variants: int = 2) -> None:
        self._llm = llm or (OpenAICompatibleLLM() if settings.llm_api_key else None)
        self._num_variants = max(1, num_variants)

    def transform(self, query: Query) -> list[str]:
        original = query.text.strip()
        if not isinstance(self._llm, OpenAICompatibleLLM):
            return [original]
        response = self._llm.complete(
            self.PROMPT.format(count=self._num_variants, question=original)
        )
        variants = [
            cleaned
            for line in response.splitlines()
            if (cleaned := _BULLET.sub("", line).strip())
        ]
        return [original, *variants[: self._num_variants]]


class HyDEQueryTransform(QueryTransformStage):
    """Hypothetical document embeddings.

    Drafts a plausible answer document via the LLM and searches with that
    hypothetical document embedded alongside the original question.
    """

    PROMPT = (
        "Write a short hypothetical document that directly answers the question "
        "below, in the style of a factual entry in a company knowledge base. "
        "Be concrete.\nQuestion: {question}"
    )

    def __init__(self, llm: LLM | None = None) -> None:
        self._llm = llm or (OpenAICompatibleLLM() if settings.llm_api_key else None)

    def transform(self, query: Query) -> list[str]:
        original = query.text.strip()
        if not isinstance(self._llm, OpenAICompatibleLLM):
            return [original]
        draft = self._llm.complete(self.PROMPT.format(question=original)).strip()
        if not draft:
            return [original]
        return [draft, original]


__all__ = [
    "ExpansionQueryTransform",
    "HyDEQueryTransform",
    "IdentityQueryTransform",
    "QueryTransformStage",
]