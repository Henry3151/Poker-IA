"""Tournament configuration (validated with pydantic)."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator, model_validator


class BlindLevel(BaseModel):
    small_blind: int = Field(gt=0)
    big_blind: int = Field(gt=0)
    ante: int = Field(default=0, ge=0)

    @model_validator(mode="after")
    def _sb_le_bb(self) -> BlindLevel:
        if self.small_blind > self.big_blind:
            raise ValueError("small blind must not exceed big blind")
        return self


DEFAULT_LEVELS = [
    BlindLevel(small_blind=25, big_blind=50),
    BlindLevel(small_blind=50, big_blind=100),
    BlindLevel(small_blind=75, big_blind=150, ante=15),
    BlindLevel(small_blind=100, big_blind=200, ante=25),
    BlindLevel(small_blind=150, big_blind=300, ante=40),
    BlindLevel(small_blind=200, big_blind=400, ante=50),
    BlindLevel(small_blind=300, big_blind=600, ante=75),
    BlindLevel(small_blind=400, big_blind=800, ante=100),
    BlindLevel(small_blind=600, big_blind=1200, ante=150),
    BlindLevel(small_blind=800, big_blind=1600, ante=200),
    BlindLevel(small_blind=1000, big_blind=2000, ante=300),
    BlindLevel(small_blind=1500, big_blind=3000, ante=400),
    BlindLevel(small_blind=2000, big_blind=4000, ante=500),
    BlindLevel(small_blind=3000, big_blind=6000, ante=750),
    BlindLevel(small_blind=5000, big_blind=10000, ante=1000),
]


class TournamentConfig(BaseModel):
    name: str = "local-mtt"
    table_size: int = Field(default=6, ge=2, le=10)
    starting_stack: int = Field(default=5000, gt=0)
    hands_per_level: int = Field(default=12, gt=0, description="hands played per table before blinds go up")
    levels: list[BlindLevel] = Field(default_factory=lambda: list(DEFAULT_LEVELS))
    buy_in: int = Field(default=100, ge=0, description="simulated buy-in units (no real money)")
    payout_percentages: list[float] = Field(default_factory=lambda: [50.0, 30.0, 20.0])
    latency_budget_ms: float = Field(default=2000.0, gt=0)
    max_rounds: int = Field(default=50_000, gt=0)

    @field_validator("payout_percentages")
    @classmethod
    def _payouts(cls, v: list[float]) -> list[float]:
        if not v or abs(sum(v) - 100.0) > 1e-6 or any(p < 0 for p in v):
            raise ValueError("payout percentages must be non-negative and sum to 100")
        if any(b > a for a, b in zip(v, v[1:], strict=False)):
            raise ValueError("payout percentages must be non-increasing")
        return v

    @field_validator("levels")
    @classmethod
    def _levels(cls, v: list[BlindLevel]) -> list[BlindLevel]:
        if not v:
            raise ValueError("at least one blind level required")
        return v


def compute_payouts(prize_pool: int, percentages: list[float], entrants: int) -> list[int]:
    """Integer payouts per place (index 0 = 1st). Rounding remainder goes to 1st place."""
    paid = percentages[: max(1, min(len(percentages), entrants))]
    scale = 100.0 / sum(paid)
    amounts = [int(prize_pool * p * scale / 100.0) for p in paid]
    amounts[0] += prize_pool - sum(amounts)
    return amounts
