"""Seed Lead Scoring's local.db with the 5 profiles from Leadbizz run
cde44123e32e + synthetic enrichment rows. This lets us verify the
Leadbizz->Lead Scoring CSV enrichment end-to-end without waiting for the
LLM scheduler.

Idempotent: re-running deletes previously seeded rows first.
"""
import json
import sqlite3
import uuid
from datetime import datetime, timezone

CON = sqlite3.connect(r"C:\Users\Admin 1\Desktop\Lead scoring tool\local.db")
LEADBIZZ_RUN_TOKEN = "cde44123e32e"

# Match the Leadbizz run's scored items exactly.
PROFILES = [
    {"full_name": "Harsha Abegunasekara", "company": "Donely",
     "industry_match": "B2B SaaS — donor / alumni engagement platform for nonprofits",
     "company_stage": "Startup", "technical_founder": False,
     "notes": "Donely is an early-stage nonprofit-engagement platform. Donor and alumni workflows suggest a need for CRM-style tooling, but the profile lacks explicit outsourcing or hiring signals."},
    {"full_name": "Mateo Hernandez", "company": "Digital Foundation Group",
     "industry_match": "IT services / consulting for enterprise digital transformation",
     "company_stage": "Growth", "technical_founder": True,
     "notes": "Digital Foundation Group operates in enterprise IT services. Strong authority + founder-led technical team; mid-funnel fit for custom AI integration work."},
    {"full_name": "Zacharie Liman-Tinguiri", "company": "Stealth AI Startup",
     "industry_match": "AI / ML — stealth-mode consumer product",
     "company_stage": "Pre-launch", "technical_founder": True,
     "notes": "Stealth AI startup in pre-launch stage. Founder-led technical profile; intent signals weak but the company stage and AI focus align with custom-build ICP."},
    {"full_name": "Buck Buchanan", "company": "BioNative AI",
     "industry_match": "Biotechnology — AI-enabled protein / molecular design",
     "company_stage": "Startup", "technical_founder": True,
     "notes": "BioNative AI fits the AI-for-biotech sweet spot; founder has authority + technical depth. Likely in-house ML team, but custom scientific software tooling is plausible."},
    {"full_name": "Kai Li", "company": "Liba Space",
     "industry_match": "Hardware / space-tech — small-satellite platforms",
     "company_stage": "Startup", "technical_founder": True,
     "notes": "Liba Space operates in the small-satellite / space-tech vertical. Strong authority, technical founder; weak ICP fit unless the engagement includes embedded software."},
]


def seed():
    cur = CON.cursor()
    # Idempotency: drop any leads matching these names so re-runs work.
    names = [(p["full_name"],) for p in PROFILES]
    cur.execute(
        "SELECT id FROM leads WHERE full_name IN ({})".format(",".join("?" * len(names))),
        [n[0] for n in names],
    )
    existing_ids = [row[0] for row in cur.fetchall()]
    if existing_ids:
        cur.execute(
            "DELETE FROM lead_scores WHERE lead_id IN ({})".format(",".join("?" * len(existing_ids))),
            existing_ids,
        )
        cur.execute(
            "DELETE FROM leads WHERE id IN ({})".format(",".join("?" * len(existing_ids))),
            existing_ids,
        )

    now = datetime.now(timezone.utc).isoformat()
    for p in PROFILES:
        lead_id = str(uuid.uuid4())
        score_id = str(uuid.uuid4())
        source_key = f"name-company:{p['full_name'].lower().replace(' ', '-')}|{p['company'].lower().replace(' ', '-')}"
        cur.execute(
            """INSERT INTO leads
            (id, full_name, headline, current_position, current_company, country,
             about, open_to_work, raw_payload, source_key, created_at, linkedin_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (lead_id, p["full_name"], None, "Founder", p["company"], "United States",
             None, False, json.dumps({"seeded_from": LEADBIZZ_RUN_TOKEN}), source_key, now, None),
        )
        cur.execute(
            """INSERT INTO lead_scores
            (id, lead_id, authority_score, fit_score, intent_score, reachability_score,
             blended_score, tier, is_competitor, disqualify_reason, technical_founder,
             company_stage, industry_match, notes, scoring_model, scoring_config_version,
             scored_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (score_id, lead_id, 80, 70, 50, 60, 65.5, "Hot", False, None, p["technical_founder"],
             p["company_stage"], p["industry_match"], p["notes"], "claude-sonnet-4-6", "1.0.0", now),
        )

    CON.commit()
    print(f"Seeded {len(PROFILES)} Lead Scoring rows for run {LEADBIZZ_RUN_TOKEN}.")


if __name__ == "__main__":
    seed()
