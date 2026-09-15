"""Retrieval pipeline: orchestrates query_transform -> search -> rerank -> context_assembly -> generate.

The pipeline is a controller that pushes data through each pluggable stage,
managing dependencies across the retrieval lifecycle. The defaults preserve the
classic search()/answer() behaviour over a plain pgvector cosine retrieval.
"""

from collections.abc import Sequence

from src.config import settings
from src.db.session import SessionLocal
from src.ingestion import ChromaEmbedder, Embedder
from src.retrieval.llm import LLM, OpenAICompatibleLLM, StubLLM
from src.retrieval.models import (
    GenerationResult,
    Query,
    RetrievalResult,
    RetrievedChunk,
)
from src.retrieval.stages.context_assembly import (
    ContextAssemblyStage,
    StandardContextAssembly,
)
from src.retrieval.stages.query_transform import (
    IdentityQueryTransform,
    QueryTransformStage,
)
from src.retrieval.stages.rerank import IdentityReranker, RerankStage
from src.retrieval.stages.search import DefaultSearchStage, SearchStage
from src.retrieval.strategies.filters import FilterBundle, build_filters
from src.retrieval.strategies.vector_search import VectorSearchStrategy


class RetrievalPipeline:
    """Controller for the retrieval lifecycle.

    Stages, in execution order:

    1. ``query_transform`` -- normalize / expand / HyDE the raw user query.
    2. ``search``          -- fetch candidates via one or more strategies.
    3. ``rerank``          -- score and re-order candidates, prune weak matches.
    4. ``context_assembly``-- build the labelled, budgeted LLM context.
    5. ``generate``        -- produce the final answer from the context.
    """

    def __init__(
        self,
        embedder: Embedder | None = None,
        llm: LLM | None = None,
        db_session=None,
        *,
        query_transform: QueryTransformStage | None = None,
        search_stage: SearchStage | None = None,
        reranker: RerankStage | None = None,
        context_assembly: ContextAssemblyStage | None = None,
    ) -> None:
        self._embedder = embedder or ChromaEmbedder()
        self._llm = llm or (
            OpenAICompatibleLLM() if settings.llm_api_key else StubLLM()
        )
        self.model = getattr(self._llm, "model", "stub")

        self._owns_session = db_session is None
        self._session = db_session or SessionLocal()

        self._query_transform = query_transform or IdentityQueryTransform()
        self._search_stage = search_stage or DefaultSearchStage(
            [VectorSearchStrategy(embedder=self._embedder, session=self._session)]
        )
        self._reranker = reranker or IdentityReranker()
        self._context_assembly = context_assembly or StandardContextAssembly()

        self._owned_llms = [
            component._llm
            for component in (self._query_transform, self._reranker)
            if isinstance(getattr(component, "_llm", None), OpenAICompatibleLLM)
        ]

    # --- stage 1-3: retrieval --------------------------------------------------------------

    def search(
        self, query: Query, *, filters: FilterBundle | None = None
    ) -> RetrievalResult:
        """Run query_transform -> search -> rerank and return the ranked chunks."""
        query_filters = filters or build_filters(query)
        queries = self._query_transform.transform(query)
        chunks = self._search_stage.search(queries, query.top_k, query_filters)
        result = RetrievalResult(query=query.text, chunks=chunks[: query.top_k])
        return self._reranker.rerank(result)

    # --- stage 4: context assembly ----------------------------------------------------------

    def build_context(
        self,
        result: RetrievalResult | Sequence[RetrievedChunk],
        *,
        max_tokens: int | None = None,
    ) -> str:
        """Assemble retrieved chunks into labelled context blocks.

        Accepts either a ``RetrievalResult`` or a bare sequence of
        ``RetrievedChunk`` (used by answer evaluation).
        """
        assembly = getattr(self, "_context_assembly", None) or StandardContextAssembly()
        if isinstance(result, RetrievalResult):
            return assembly.assemble(result, max_tokens=max_tokens)
        wrapped = RetrievalResult(query="", chunks=list(result))
        return assembly.assemble(wrapped, max_tokens=max_tokens)

    def build_prompt(self, result: RetrievalResult) -> str:
        """Format the final LLM prompt from the assembled context."""
        return (
            f"Context:\n{self.build_context(result)}\n\n"
            f"Question: {result.query}\nAnswer:"
        )

    # --- stage 5: generation ----------------------------------------------------------------

    def generate(self, prompt: str) -> str:
        """Generate the answer for a prompt via the configured LLM."""
        return self._llm.complete(prompt)

    def answer(self, query: Query) -> GenerationResult:
        """Run the full pipeline: search -> context -> generate."""
        result = self.search(query)
        prompt = self.build_prompt(result)
        answer = self.generate(prompt)
        return GenerationResult(
            answer=answer, sources=result.chunks, model=self.model
        )

    def close(self) -> None:
        """Release owned HTTP clients and the session (if the pipeline created it)."""
        if isinstance(self._llm, OpenAICompatibleLLM):
            self._llm.close()
        for llm in self._owned_llms:
            llm.close()
        if self._owns_session:
            self._session.close()


__all__ = ["RetrievalPipeline"]