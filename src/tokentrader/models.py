from dataclasses import dataclass
from enum import Enum


class QualityTier(str, Enum):
    ECONOMY = "economy"
    BALANCED = "balanced"
    PREMIUM = "premium"


@dataclass(slots=True)
class TaskOrder:
    task_type: str
    prompt_tokens: int
    max_latency_ms: int
    budget_credits: float
    quality_tier: QualityTier = QualityTier.BALANCED


@dataclass(slots=True)
class SupplyOffer:
    provider: str
    model: str
    price_per_1k_tokens: float
    quality_score: float
    reliability_score: float
    avg_latency_ms: int
    available_tokens: int


@dataclass(slots=True)
class QuoteItem:
    provider: str
    model: str
    estimated_cost_credits: float
    score: float


@dataclass(slots=True)
class QuoteResponse:
    order: TaskOrder
    candidates: list[QuoteItem]


@dataclass(slots=True)
class ExecuteRequest:
    order: TaskOrder
    provider: str
    model: str


@dataclass(slots=True)
class ExecuteResponse:
    accepted: bool
    execution_id: str
    charged_credits: float
    message: str
