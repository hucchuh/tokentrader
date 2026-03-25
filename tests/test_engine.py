from tokentrader.engine import build_quote, execute
from tokentrader.models import QualityTier, TaskOrder


def test_quote_ranks_candidates() -> None:
    order = TaskOrder(
        task_type="analysis",
        prompt_tokens=1200,
        max_latency_ms=1600,
        budget_credits=1.0,
        quality_tier=QualityTier.BALANCED,
    )

    quote = build_quote(order)
    assert quote.candidates
    assert quote.candidates[0].score >= quote.candidates[-1].score


def test_execute_rejects_when_budget_too_low() -> None:
    order = TaskOrder(
        task_type="reasoning",
        prompt_tokens=6000,
        max_latency_ms=1500,
        budget_credits=0.05,
        quality_tier=QualityTier.PREMIUM,
    )

    result = execute(order, provider="provider_c", model="premium-llm-x")
    assert result.accepted is False
    assert "rejected" in result.message
