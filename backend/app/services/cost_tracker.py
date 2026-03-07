"""Token and cost tracking.

Computes baseline (naive RAG) vs actual (pruned + compressed + routed) costs.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import settings


@dataclass(frozen=True)
class CostBreakdown:
    baseline_input_tokens: int
    actual_input_tokens: int
    actual_output_tokens: int
    tokens_saved: int
    baseline_cost_inr: float
    actual_cost_inr: float
    inr_saved: float
    avg_cost_reduction_pct: float


def _usd_cost_for(model: str, in_tokens: int, out_tokens: int) -> float:
    if settings.llm_provider != "openai":
        return 0.0

    # Costs are per 1M tokens.
    if model == settings.openai_model_large:
        return (in_tokens / 1_000_000) * settings.gpt4o_in_usd_per_1m + (out_tokens / 1_000_000) * settings.gpt4o_out_usd_per_1m
    if model == settings.openai_model_small:
        return (in_tokens / 1_000_000) * settings.gpt4omini_in_usd_per_1m + (out_tokens / 1_000_000) * settings.gpt4omini_out_usd_per_1m
    return 0.0


def compute_savings(
    baseline_input_tokens: int,
    actual_input_tokens: int,
    actual_output_tokens: int,
    actual_model: str,
    baseline_model: str,
) -> CostBreakdown:
    """Compute token + INR savings vs baseline."""

    baseline_usd = _usd_cost_for(baseline_model, baseline_input_tokens, out_tokens=actual_output_tokens)
    actual_usd = _usd_cost_for(actual_model, actual_input_tokens, out_tokens=actual_output_tokens)

    baseline_inr = baseline_usd * settings.usd_to_inr
    actual_inr = actual_usd * settings.usd_to_inr

    tokens_saved = max(0, baseline_input_tokens - actual_input_tokens)
    inr_saved = max(0.0, baseline_inr - actual_inr)

    reduction = 0.0
    if baseline_inr > 0:
        reduction = (inr_saved / baseline_inr) * 100.0

    return CostBreakdown(
        baseline_input_tokens=baseline_input_tokens,
        actual_input_tokens=actual_input_tokens,
        actual_output_tokens=actual_output_tokens,
        tokens_saved=tokens_saved,
        baseline_cost_inr=baseline_inr,
        actual_cost_inr=actual_inr,
        inr_saved=inr_saved,
        avg_cost_reduction_pct=reduction,
    )
