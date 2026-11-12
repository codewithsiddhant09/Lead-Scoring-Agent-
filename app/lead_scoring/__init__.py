"""Multi-axis lead scoring for TechGropse.

Public surface:
    prefilter.rule_prefilter(lead)
    claude_client.score_leads_sync / score_leads_batch
    tiering.tier_for(...)
"""
from app.lead_scoring.config import ScoringConfig, load_scoring_config
from app.lead_scoring.models import (
    CommandEnvelope,
    LeadInput,
    LeadScoreRow,
    PrefilterResult,
    ScoringResult,
)
from app.lead_scoring.prefilter import rule_prefilter
from app.lead_scoring.tiering import tier_for, compute_blended_score

__all__ = [
    "ScoringConfig",
    "load_scoring_config",
    "LeadInput",
    "PrefilterResult",
    "ScoringResult",
    "LeadScoreRow",
    "CommandEnvelope",
    "rule_prefilter",
    "tier_for",
    "compute_blended_score",
]
