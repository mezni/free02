"""Context assembly stage: turn retrieved chunks into the final LLM context."""

from abc import ABC, abstractmethod

from src.retrieval.models import RetrievalResult, RetrievedChunk

_CHARS_PER_TOKEN = 4


def _dedupe(chunks: list[RetrievedChunk]) -> list[RetrievedChunk]:
    seen: set[tuple[str, int, str]] = set()
    result: list[RetrievedChunk] = []
    for chunk in chunks:
        key = (chunk.source, chunk.index, chunk.metadata.get("version_tag", ""))
        if key not in seen:
            seen.add(key)
            result.append(chunk)
    return result


class ContextAssemblyStage(ABC):
    """Formats retrieved snippets into the prompt context window."""

    @abstractmethod
    def assemble(
        self, result: RetrievalResult, *, max_tokens: int | None = None
    ) -> str:
        """Return the labelled, deduplicated context block text."""


class StandardContextAssembly(ContextAssemblyStage):
    """Label sources, inject metadata, deduplicate, and cap the token budget.

    Blocks use the ``[n] (source: <path>)`` format. When ``max_tokens`` is set,
    trailing chunks are dropped (and the final chunk truncated) to stay inside
    the budget using a ``chars_per_token`` approximation.
    """

    def __init__(
        self,
        *,
        chars_per_token: int = _CHARS_PER_TOKEN,
        include_metadata: bool = True,
        max_chunks: int | None = None,
    ) -> None:
        self._chars_per_token = chars_per_token
        self._include_metadata = include_metadata
        self._max_chunks = max_chunks

    def assemble(
        self, result: RetrievalResult, *, max_tokens: int | None = None
    ) -> str:
        chunks = _dedupe(result.chunks)
        if self._max_chunks is not None:
            chunks = chunks[: self._max_chunks]
        budget = (
            max_tokens * self._chars_per_token if max_tokens else float("inf")
        )

        blocks: list[str] = []
        used = 0
        for i, chunk in enumerate(chunks):
            header = f"[{i + 1}]{self._label(chunk)}"
            body = chunk.text
            if used + len(header) + 1 + len(body) > budget:
                remaining = budget - used
                body = body[: max(0, remaining - len(header) - 1)]
                if not body:
                    break
            block = f"{header}\n{body}"
            blocks.append(block)
            used += len(block)
            if used >= budget:
                break
        return "\n\n".join(blocks)

    def _label(self, chunk: RetrievedChunk) -> str:
        if not self._include_metadata:
            return ""
        label = f" (source: {chunk.source})"
        title = chunk.metadata.get("title")
        if title:
            label += f" ({title})"
        return label


__all__ = ["ContextAssemblyStage", "StandardContextAssembly"]