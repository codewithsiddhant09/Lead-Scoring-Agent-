"""Config loader for scoring_config.yaml — keeps weights/thresholds out of code."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator


class Weights(BaseModel):
    authority: float
    fit: float
    intent: float
    reachability: float

    @field_validator("*")
    @classmethod
    def _non_negative(cls, v: float) -> float:
        if v < 0:
            raise ValueError("weights must be non-negative")
        return v

    def total(self) -> float:
        return self.authority + self.fit + self.intent + self.reachability


class Tiers(BaseModel):
    hot_min: float
    hot_lean_min: float
    warm_min: float


class AuthorityMultipliers(BaseModel):
    general_management: float = 1.0
    technical_leadership: float = 0.85
    ops_director: float = 0.80
    revenue_leadership: float = 0.50
    individual_contributor: float = 0.20


class OutreachPolicy(BaseModel):
    auto_dispatch_tiers: list[str]
    manual_review_tiers: list[str]
    never_outreach_tiers: list[str]
    never_outreach_competitor: bool = True


class ModelConfig(BaseModel):
    name: str = "claude-sonnet-4-6"
    max_tokens: int = 600
    temperature: float = 0.0
    batch_size_threshold: int = 20


class RetryPolicy(BaseModel):
    max_attempts: int = 4
    initial_backoff_seconds: float = 1.0
    max_backoff_seconds: float = 16.0


class ScoringConfig(BaseModel):
    version: str = Field(default="1.0.0")
    weights: Weights
    tiers: Tiers
    fit_floor: float = 30.0
    disqualified_tier: str = "Cold"
    authority_multipliers: AuthorityMultipliers = AuthorityMultipliers()
    outreach: OutreachPolicy
    model: ModelConfig = ModelConfig()
    retry: RetryPolicy = RetryPolicy()

    def validate_weights(self) -> None:
        """Hard fail in code if weights don't sum to ~1.0 — caught at startup."""
        total = round(self.weights.total(), 3)
        if abs(total - 1.0) > 0.01:
            raise ValueError(
                f"scoring_config weights must sum to 1.0 (got {total}); check scoring_config.yaml"
            )


@lru_cache(maxsize=1)
def load_scoring_config(path: str = "scoring_config.yaml") -> ScoringConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"scoring_config.yaml not found at {p.resolve()}. "
            "Copy scoring_config.yaml into the working directory."
        )
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    cfg = ScoringConfig(**raw)
    cfg.validate_weights()
    return cfg


def reload_scoring_config(path: str = "scoring_config.yaml") -> ScoringConfig:
    """Clear the cache and reload — used by the calibration hot-reload endpoint."""
    load_scoring_config.cache_clear()
    return load_scoring_config(path)
