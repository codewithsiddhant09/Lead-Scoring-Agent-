"""Unit tests for tier_for() boundary behavior."""
from __future__ import annotations

from app.lead_scoring.config import ScoringConfig
from app.lead_scoring.models import PrefilterResult, Tier
from app.lead_scoring.tiering import compute_blended_score, tier_for


def _cfg() -> ScoringConfig:
    return ScoringConfig(
        version="test",
        weights={"authority": 0.30, "fit": 0.30, "intent": 0.25, "reachability": 0.15},
        tiers={"hot_min": 65, "hot_lean_min": 55, "warm_min": 45},
        fit_floor=30,
        disqualified_tier="Cold",
        outreach={
            "auto_dispatch_tiers": ["Hot", "Hot-leaning Warm"],
            "manual_review_tiers": ["Warm"],
            "never_outreach_tiers": ["Cold"],
            "never_outreach_competitor": True,
        },
    )


def test_exact_hot_threshold_is_hot():
    cfg = _cfg()
    # 65.0 exactly
    tier, reason = tier_for(65.0, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.HOT
    assert reason is None


def test_just_below_hot_is_hot_leaning_warm():
    cfg = _cfg()
    tier, _ = tier_for(64.9, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.HOT_LEANING_WARM


def test_exact_hot_lean_threshold():
    cfg = _cfg()
    tier, _ = tier_for(55.0, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.HOT_LEANING_WARM


def test_just_below_hot_lean_is_warm():
    cfg = _cfg()
    tier, _ = tier_for(54.9, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.WARM


def test_exact_warm_threshold():
    cfg = _cfg()
    tier, _ = tier_for(45.0, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.WARM


def test_below_warm_is_cold():
    cfg = _cfg()
    tier, _ = tier_for(44.9, fit=50, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.COLD


def test_fit_floor_overrides_high_authority():
    """Real bug found in manual testing: a fractional consultant with great email + high
    authority but zero industry fit should not slip into Hot."""
    cfg = _cfg()
    blended = 70.0  # would be Hot
    tier, reason = tier_for(blended, fit=29, pre=PrefilterResult(disqualified=False), cfg=cfg)
    assert tier == Tier.COLD
    assert reason is not None
    assert "fit floor" in reason


def test_disqualify_overrides_blended():
    cfg = _cfg()
    pre = PrefilterResult(disqualified=True, reason="competitor flagged by LLM", skip_llm=False)
    tier, reason = tier_for(80.0, fit=90, pre=pre, cfg=cfg)
    assert tier == Tier.COLD
    assert "competitor" in (reason or "")


def test_blended_score_arithmetic():
    cfg = _cfg()
    blended = compute_blended_score(authority=80, fit=70, intent=60, reachability=50, cfg=cfg)
    # 0.30*80 + 0.30*70 + 0.25*60 + 0.15*50 = 24 + 21 + 15 + 7.5 = 67.5
    assert blended == 67.5
