"""Retrieval & generation evaluation: rank metrics and LLM-as-judge scoring."""

import argparse
import json
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from src.config import settings
from src.retrieval import (
    LLM,
    OpenAICompatibleLLM,
    Query,
    RetrievalPipeline,
    RetrievedChunk,
    StubLLM,
)

JUDGE_PROMPT = """\
Question: {question}

Context:
{context}

Answer:
{answer}

Score the answer, on a scale of 0 to 5, for whether it is grounded in and
faithful to the context alone. Respond with exactly two lines:
SCORE: <0-5>
VERDICT: <grounded|hallucinated>
"""


class EvalCase(BaseModel):
    query: str = Field(min_length=1, description="Question to ask the pipeline")
    relevant_sources: list[str] = Field(
        min_length=1, description="Ground-truth relevant source file names"
    )


class RankingMetrics(BaseModel):
    reciprocal_rank: float = 0.0
    hit: bool = False
    precision: float = 0.0
    recall: float = 0.0


class CaseResult(BaseModel):
    case: EvalCase
    retrieved: list[RetrievedChunk]
    metrics: RankingMetrics


class RetrievalEvaluation(BaseModel):
    cases: list[CaseResult]
    mean_reciprocal_rank: float
    hit_rate: float
    mean_precision: float
    mean_recall: float


class Judgement(BaseModel):
    case: EvalCase
    answer: str
    score: int = Field(ge=0, le=5)
    grounded: bool
    explanation: str = Field(
        default="", description="Free-text rationale from the judge"
    )


def is_hit(retrieved: list[RetrievedChunk], relevant_sources: list[str]) -> bool:
    return any(chunk.source in relevant_sources for chunk in retrieved)


def reciprocal_rank(
    retrieved: list[RetrievedChunk], relevant_sources: list[str]
) -> float:
    for rank, chunk in enumerate(retrieved, start=1):
        if chunk.source in relevant_sources:
            return 1.0 / rank
    return 0.0


def precision_at_k(
    retrieved: list[RetrievedChunk], relevant_sources: list[str], k: int
) -> float:
    returned = retrieved[:k]
    if not returned:
        return 0.0
    return sum(chunk.source in relevant_sources for chunk in returned) / len(returned)


def recall_at_k(
    retrieved: list[RetrievedChunk], relevant_sources: list[str], k: int
) -> float:
    if not relevant_sources:
        return 0.0
    return sum(chunk.source in relevant_sources for chunk in retrieved[:k]) / len(
        relevant_sources
    )


def rank_metrics(
    retrieved: list[RetrievedChunk], relevant_sources: list[str], top_k: int = 5
) -> RankingMetrics:
    return RankingMetrics(
        reciprocal_rank=reciprocal_rank(retrieved, relevant_sources),
        hit=is_hit(retrieved, relevant_sources),
        precision=precision_at_k(retrieved, relevant_sources, top_k),
        recall=recall_at_k(retrieved, relevant_sources, top_k),
    )


def evaluate_case(
    pipeline: RetrievalPipeline, case: EvalCase, top_k: int = 5
) -> CaseResult:
    result = pipeline.search(Query(text=case.query, top_k=top_k))
    return CaseResult(
        case=case,
        retrieved=result.chunks,
        metrics=rank_metrics(result.chunks, case.relevant_sources, top_k),
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def evaluate_retrieval(
    pipeline: RetrievalPipeline,
    cases: list[EvalCase],
    top_k: int = 5,
) -> RetrievalEvaluation:
    case_results = [evaluate_case(pipeline, case, top_k) for case in cases]
    return RetrievalEvaluation(
        cases=case_results,
        mean_reciprocal_rank=_mean(
            [result.metrics.reciprocal_rank for result in case_results]
        ),
        hit_rate=_mean([result.metrics.hit for result in case_results]),
        mean_precision=_mean([result.metrics.precision for result in case_results]),
        mean_recall=_mean([result.metrics.recall for result in case_results]),
    )


class Judge(ABC):
    @abstractmethod
    def judge(self, case: EvalCase, answer: str, context: str) -> Judgement:
        """Return a groundedness judgement for `answer` against `context`."""


class StubJudge(Judge):
    """Deterministic fallback used when no LLM API key is configured."""

    def judge(self, case: EvalCase, answer: str, context: str) -> Judgement:
        return Judgement(
            case=case,
            answer=answer,
            score=0,
            grounded=False,
            explanation="[stub] No LLM configured (set LLM_API_KEY)",
        )


def _parse_judgement(text: str) -> tuple[int, bool]:
    score = 0
    grounded = False
    for line in text.splitlines():
        line = line.strip().lower()
        if line.startswith("score:"):
            value = line.split(":", 1)[1].strip()
            try:
                score = int(value)
            except ValueError:
                score = 0
        elif line.startswith("verdict:"):
            grounded = "grounded" in line.split(":", 1)[1]
    return min(max(score, 0), 5), grounded


class LLMJudge(Judge):
    """Judge answer groundedness against the retrieved context via an LLM rubric."""

    def __init__(self, llm: LLM | None = None) -> None:
        self._llm = llm or (
            OpenAICompatibleLLM() if settings.llm_api_key else StubLLM()
        )

    def close(self) -> None:
        if isinstance(self._llm, OpenAICompatibleLLM):
            self._llm.close()

    def judge(self, case: EvalCase, answer: str, context: str) -> Judgement:
        prompt = JUDGE_PROMPT.format(
            question=case.query, context=context, answer=answer
        )
        response = self._llm.complete(prompt)
        score, grounded = _parse_judgement(response)
        return Judgement(
            case=case,
            answer=answer,
            score=score,
            grounded=grounded,
            explanation=response.strip(),
        )


def evaluate_answers(
    pipeline: RetrievalPipeline,
    judge: Judge,
    cases: list[EvalCase],
    top_k: int = 5,
) -> list[Judgement]:
    judgements: list[Judgement] = []
    for case in cases:
        generation = pipeline.answer(Query(text=case.query, top_k=top_k))
        context = pipeline.build_context(generation.sources)
        judgements.append(judge.judge(case, generation.answer, context))
    return judgements


def load_cases(path: Path) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            cases.append(EvalCase.model_validate(json.loads(line)))
    return cases


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate the retrieval pipeline")
    parser.add_argument(
        "--cases", type=Path, required=True, help="JSONL file of EvalCase objects"
    )
    parser.add_argument("--top-k", type=int, default=5, choices=range(1, 21))
    args = parser.parse_args()

    cases = load_cases(args.cases)
    pipeline = RetrievalPipeline()
    try:
        evaluation = evaluate_retrieval(pipeline, cases, top_k=args.top_k)
        print(f"Evaluated {len(evaluation.cases)} case(s) at top-{args.top_k}")
        print(f"Mean reciprocal rank: {evaluation.mean_reciprocal_rank:.4f}")
        print(f"Hit rate: {evaluation.hit_rate:.4f}")
        print(f"Mean precision: {evaluation.mean_precision:.4f}")
        print(f"Mean recall: {evaluation.mean_recall:.4f}")
        for result in evaluation.cases:
            print(
                f"- {result.case.query!r}: MRR {result.metrics.reciprocal_rank:.4f}, "
                f"hit={result.metrics.hit}"
            )
    finally:
        pipeline.close()


if __name__ == "__main__":
    main()
