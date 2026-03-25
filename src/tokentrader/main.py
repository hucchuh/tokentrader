from __future__ import annotations

import json
from dataclasses import asdict

from .engine import build_quote, execute
from .models import QualityTier, TaskOrder


def demo() -> dict:
    order = TaskOrder(
        task_type="code_generation",
        prompt_tokens=1500,
        max_latency_ms=1600,
        budget_credits=1.0,
        quality_tier=QualityTier.BALANCED,
    )
    quote = build_quote(order)
    first = quote.candidates[0] if quote.candidates else None
    execution = (
        execute(order, first.provider, first.model)
        if first
        else {"accepted": False, "message": "no candidates"}
    )
    return {
        "order": asdict(order),
        "candidates": [asdict(c) for c in quote.candidates],
        "execution": asdict(execution) if hasattr(execution, "accepted") else execution,
    }


if __name__ == "__main__":
    print(json.dumps(demo(), ensure_ascii=False, indent=2))
