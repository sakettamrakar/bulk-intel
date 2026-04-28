#!/usr/bin/env python3
"""
Submit Phase 1 Round 1 tasks to Jules API using correct Google API format.

Based on: https://developers.google.com/julius/api
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JULES_API_KEY = os.getenv("JULES_API_KEY")
JULES_API_BASE = "https://jules.googleapis.com/v1alpha"

if not JULES_API_KEY:
    print("[ERROR] JULES_API_KEY not found in .env file")
    exit(1)

HEADERS = {
    "X-Goog-Api-Key": JULES_API_KEY,
    "Content-Type": "application/json",
}

# Phase 1 Round 1 tasks
ROUND_1_TASKS = [
    {
        "id": "T-101",
        "title": "Decompose operating_cost_pct into platform x category fee table",
        "prompt": """Implement task T-101: Decompose operating_cost_pct into platform x category fee table

OBJECTIVE:
Replace flat operating_cost_pct (0.25) with structured PLATFORM_FEES lookup keyed on
(platform, category). Real Amazon fees in India vary 5-30% by category.

DETAILED SPEC:
See file: docs/wbs/phase-1/T-101-platform-fee-table.md

KEY CHANGES REQUIRED:
- config/settings.py: add PLATFORM_FEES dict with Amazon, Flipkart, Meesho, B2B platforms
- intelligence/profit.py: replace flat fee lookup with _resolve_platform_fee_pct helper
- output/reporter.py: add platform_fee_pct column to output
- tests/test_cost_engine.py: create new test file

ACCEPTANCE CRITERIA:
- PLATFORM_FEES dict exposes 3+ platforms x 10+ categories
- Settings dataclass includes platform_fees, default_platform, fallback_operating_cost_pct, ancillary_revenue_fee_pct
- operating_cost_pct removed from PROFIT_ASSUMPTIONS
- Output CSV gains platform_fee_pct column (per row)
- Pipeline runs end-to-end without error
- On real manifest, BUY-basket ROI improves meaningfully

TEST CASES:
- test_platform_fee_lookup_uses_table_value: amazon/electronics should return 0.085
- test_platform_fee_falls_back_to_platform_default: unknown category falls back to platform default
- test_platform_fee_falls_back_to_global_default: unknown platform uses FALLBACK_OPERATING_COST_PCT
- test_default_platform_used_when_column_missing: rows without platform column use DEFAULT_PLATFORM
- test_apparel_costs_more_than_kitchen: fee variance affects profit calculation

DOCUMENTATION:
- Update README.md config table (replace operating_cost_pct with PLATFORM_FEES)
- Update README.md section 3 data flow step 6 (profitability calculation)
- Update intelligence/profit.py docstring to list platform_fee_pct column
- Add inline comments in config/settings.py with sources and verification dates

GITHUB BRANCH: feat/t-101-platform-fee-table
""",
        "effort_hours": 6,
    },
    {
        "id": "T-102",
        "title": "Add inspection cost for not_tested / unknown",
        "prompt": """Implement task T-102: Add inspection cost for not_tested / unknown

OBJECTIVE:
Add inspection cost model for items with not_tested or unknown condition status.
Critical for cost accuracy on liquidation lots.

DETAILED SPEC:
See file: docs/wbs/phase-1/T-102-inspection-cost.md

KEY CHANGES REQUIRED:
- config/settings.py: add INSPECTION_COST_BY_CONDITION dict
- intelligence/profit.py: add inspection_cost calculation per condition
- output/reporter.py: add inspection_cost column

ACCEPTANCE CRITERIA:
- INSPECTION_COST_BY_CONDITION dict in config with rates per condition
- Inspection cost applied for not_tested and unknown conditions
- Output CSV includes inspection_cost column
- All condition statuses handled (tested, not_tested, unknown)
- Fallback handling for unrecognized conditions

TEST CASES:
- test_inspection_cost_applied_for_unknown
- test_inspection_cost_applied_for_not_tested
- test_no_inspection_cost_for_tested_items
- test_inspection_cost_affects_profit_calculation

DOCUMENTATION:
- Update README.md config table with INSPECTION_COST_BY_CONDITION
- Update intelligence/profit.py docstring

GITHUB BRANCH: feat/t-102-inspection-cost
""",
        "effort_hours": 3,
    },
    {
        "id": "T-103",
        "title": "Add category-aware transport cost (weight tiers)",
        "prompt": """Implement task T-103: Add category-aware transport cost (weight tiers)

OBJECTIVE:
Implement category-aware transport cost with weight-based tiers instead of flat rate.
Transport can be 5-15% of revenue depending on weight and destination.

DETAILED SPEC:
See file: docs/wbs/phase-1/T-103-transport-cost.md

KEY CHANGES REQUIRED:
- config/settings.py: add TRANSPORT_COST_BY_CATEGORY_WEIGHT dict with weight tiers
- intelligence/profit.py: add transport_cost lookup per row based on category + weight
- output/reporter.py: add transport_cost column

ACCEPTANCE CRITERIA:
- TRANSPORT_COST_BY_CATEGORY_WEIGHT dict with category x weight tier matrix
- Weight tiers properly defined for each category
- Transport cost applied per row based on category and item weight
- Output includes transport_cost column
- Fallback for unknown categories
- Zero transport for digital/weightless goods

TEST CASES:
- test_transport_cost_by_weight_tier
- test_transport_cost_by_category
- test_transport_fallback_for_unknown_category
- test_transport_cost_affects_profit
- test_zero_transport_for_digital_goods

DOCUMENTATION:
- Update README.md config table
- Update intelligence/profit.py docstring

GITHUB BRANCH: feat/t-103-transport-cost
""",
        "effort_hours": 5,
    },
    {
        "id": "T-106",
        "title": "Hard gate: low match_confidence downgrades BUY to REVIEW",
        "prompt": """Implement task T-106: Hard gate - low match_confidence downgrades BUY to REVIEW

OBJECTIVE:
Implement pricing confidence gate that downgrades low-confidence price matches from
BUY to REVIEW recommendation. Prevents committing capital on uncertain pricing.

DETAILED SPEC:
See file: docs/wbs/phase-1/T-106-uncertain-price-gate.md

KEY CHANGES REQUIRED:
- config/settings.py: add CONFIDENCE_THRESHOLD_FOR_BUY constant
- intelligence/scoring.py: add confidence gate logic to downgrade recommendations
- output/reporter.py: add confidence_gate_applied flag column

ACCEPTANCE CRITERIA:
- CONFIDENCE_THRESHOLD_FOR_BUY constant defined in config
- Items below threshold automatically downgraded from BUY to REVIEW
- Output includes confidence_gate_applied boolean column
- Audit trail shows original vs downgraded recommendation
- No false negatives (all low-confidence items caught)

TEST CASES:
- test_high_confidence_items_keep_buy_rating
- test_low_confidence_items_downgraded_to_review
- test_confidence_threshold_applies_to_all_platforms
- test_confidence_gate_prevents_loss_scenarios

DOCUMENTATION:
- Update README.md config table
- Update intelligence/scoring.py docstring

GITHUB BRANCH: feat/t-106-uncertain-price-gate
""",
        "effort_hours": 2,
    },
]


def list_sources():
    """List available sources (GitHub repos)."""
    print("[INFO] Fetching available sources...")
    try:
        response = requests.get(
            f"{JULES_API_BASE}/sources",
            headers=HEADERS,
            timeout=10,
        )
        response.raise_for_status()
        sources = response.json().get("sources", [])

        if sources:
            print(f"[OK] Found {len(sources)} source(s):")
            for source in sources:
                print(f"     - {source.get('name', source.get('displayName', 'unknown'))}")
            return sources
        else:
            print("[WARN] No sources found. You may need to install Jules GitHub app on your repo.")
            return []
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] Failed to list sources: {e}")
        return []


def create_session(task: dict, source_name: str = None) -> dict:
    """Create a Jules session for a task."""

    # Build session payload
    payload = {
        "title": f"{task['id']}: {task['title']}",
        "prompt": task["prompt"],
        "automationMode": "AUTO_CREATE_PR",
        "requirePlanApproval": False,
    }

    # Add source if available
    if source_name:
        payload["sourceContext"] = {
            "source": source_name,
            "githubRepoContext": {
                "startingBranch": "main"
            }
        }

    try:
        print(f"   Creating session for {task['id']}...")
        response = requests.post(
            f"{JULES_API_BASE}/sessions",
            json=payload,
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        session_data = response.json()

        return {
            "success": True,
            "task_id": task["id"],
            "session_id": session_data.get("name", "").split("/")[-1],
            "session_name": session_data.get("name"),
            "web_uri": session_data.get("webUri"),
            "status": session_data.get("state"),
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "task_id": task["id"],
            "error": str(e),
        }


def main():
    """Main entry point."""
    print("[INFO] Jules API Task Submission - Phase 1 Round 1")
    print(f"[INFO] API Base: {JULES_API_BASE}")
    print(f"[INFO] Tasks: {len(ROUND_1_TASKS)}")
    print()

    # Step 1: List available sources
    print("[STEP 1] Checking available sources...")
    sources = list_sources()
    print()

    source_name = None
    if sources:
        # Find bulk-intel source
        bulk_intel_source = None
        for source in sources:
            source_name_val = source.get("name", "")
            if "bulk-intel" in source_name_val.lower():
                bulk_intel_source = source_name_val
                break

        if bulk_intel_source:
            source_name = bulk_intel_source
            print(f"[OK] Found bulk-intel source: {source_name}")
        else:
            print("[ERROR] bulk-intel source not found in available sources")
            print("[AVAILABLE SOURCES:]")
            for source in sources:
                print(f"  - {source.get('name')}")
            exit(1)
    else:
        print("[WARN] No sources available. Attempting session creation without source.")
    print()

    # Step 2: Create sessions for each task
    print("[STEP 2] Creating Jules sessions...")
    results = []

    for i, task in enumerate(ROUND_1_TASKS, 1):
        print(f"\n[{i}/{len(ROUND_1_TASKS)}] {task['id']}: {task['title']}")
        result = create_session(task, source_name)
        results.append(result)

        if result["success"]:
            print(f"[OK] Session created")
            print(f"     ID: {result['session_id']}")
            print(f"     Status: {result['status']}")
            if result.get("web_uri"):
                print(f"     URL: {result['web_uri']}")
        else:
            print(f"[FAIL] {result['error']}")

    print()
    print("=" * 70)

    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\n[SUMMARY] {successful}/{len(ROUND_1_TASKS)} sessions created successfully\n")

    # Save results
    results_file = Path("./logs/jules_session_submission.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)

    with open(results_file, "w") as f:
        json.dump({
            "timestamp": str(Path.cwd()),
            "phase": 1,
            "round": 1,
            "tasks_submitted": len(ROUND_1_TASKS),
            "successful": successful,
            "source": source_name,
            "results": results,
        }, f, indent=2)

    print(f"[SAVED] Results: {results_file}")
    print()

    if successful == len(ROUND_1_TASKS):
        print("[SUCCESS] All Phase 1 Round 1 tasks submitted to Jules!")
        print("[NEXT] Monitor sessions at https://jules.google/sessions")
        return 0
    else:
        print(f"[ERROR] {len(ROUND_1_TASKS) - successful} task(s) failed")
        return 1


if __name__ == "__main__":
    exit(main())
