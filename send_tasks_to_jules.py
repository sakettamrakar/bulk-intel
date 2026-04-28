#!/usr/bin/env python3
"""
Send Phase 1 Round 1 tasks to Jules API.

Tasks that can run in parallel:
- T-101: Platform fee table (6h) - no dependencies
- T-102: Inspection cost (3h) - no dependencies
- T-103: Transport cost (5h) - no dependencies
- T-106: Price confidence gate (2h) - no dependencies
"""

import os
import json
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

JULES_API_KEY = os.getenv("JULES_API_KEY")
JULES_API_URL = os.getenv("JULES_API_URL", "https://jules.googleapis.com/v1alpha")

# Phase 1 Round 1 tasks (no dependencies, can run in parallel)
ROUND_1_TASKS = [
    {
        "id": "T-101",
        "title": "Decompose `operating_cost_pct` into platform × category fee table",
        "phase": 1,
        "round": 1,
        "effort_hours": 6,
        "depends_on": [],
        "file_path": "docs/wbs/phase-1/T-101-platform-fee-table.md",
        "priority": "P0",
        "description": "Replace flat operating_cost_pct (0.25) with structured PLATFORM_FEES lookup keyed on (platform, category). Real fees vary 5-30% by category.",
    },
    {
        "id": "T-102",
        "title": "Add inspection cost for `not_tested` / `unknown`",
        "phase": 1,
        "round": 1,
        "effort_hours": 3,
        "depends_on": [],
        "file_path": "docs/wbs/phase-1/T-102-inspection-cost.md",
        "priority": "P0",
        "description": "Add inspection cost model for items with unknown or not_tested condition status.",
    },
    {
        "id": "T-103",
        "title": "Add category-aware transport cost (weight tiers)",
        "phase": 1,
        "round": 1,
        "effort_hours": 5,
        "depends_on": [],
        "file_path": "docs/wbs/phase-1/T-103-transport-cost.md",
        "priority": "P0",
        "description": "Implement category-aware transport cost with weight-based tiers instead of flat rate.",
    },
    {
        "id": "T-106",
        "title": "Hard gate: low `match_confidence` downgrades BUY → REVIEW",
        "phase": 1,
        "round": 1,
        "effort_hours": 2,
        "depends_on": [],
        "file_path": "docs/wbs/phase-1/T-106-uncertain-price-gate.md",
        "priority": "P0",
        "description": "Implement pricing confidence gate that downgrades low-confidence matches from BUY to REVIEW.",
    },
]


def send_task_to_jules(task: dict) -> dict:
    """Create a Jules session for a single task with automated PR creation."""
    headers = {
        "X-Goog-Api-Key": JULES_API_KEY,
        "Content-Type": "application/json",
    }

    # Clean up title for branch name
    clean_title = task['title'].lower().replace(" ", "-").replace("`", "").replace("/", "-")

    # Format task as a detailed prompt for Jules
    task_prompt = f"""
Implement task {task['id']}: {task['title']}

OBJECTIVE:
{task['description']}

EFFORT ESTIMATE: {task['effort_hours']} hours

SPECIFICATION & FILES TO MODIFY:
See {task['file_path']} for complete details.

KEY CHANGES REQUIRED:
{chr(10).join(f"- {change}" for change in task.get("key_changes", ["Check task file for details"]))}

ACCEPTANCE CRITERIA:
{chr(10).join(f"- {criterion}" for criterion in task.get("acceptance_criteria", ["Check task file for details"]))}

TEST CASES:
{chr(10).join(f"- {test}" for test in task.get("test_cases", ["See task file"]))}

DOCUMENTATION REQUIREMENTS:
- Update README.md with configuration changes
- Update module docstrings for new/modified functions
- Add/update function type hints and docstrings
- Add regression tests as specified

GITHUB BRANCH: feat/{task['id'].lower()}-{clean_title}

CONSTRAINTS:
- All changes must pass pytest (80%+ coverage required)
- Must include documentation in the same commit
- Must test on real manifest before submitting PR
    """

    # Create a new session for this task
    session_endpoint = f"{JULES_API_URL}/sessions"
    session_payload = {
        "prompt": task_prompt,
        "title": f"{task['id']}: {task['title']}",
        "sourceContext": {
            "source": "sources/github/saketam/bulk-intel",
            "githubRepoContext": {
                "startingBranch": "main"
            }
        },
        "automationMode": "AUTO_CREATE_PR",
        "requirePlanApproval": False
    }

    try:
        response = requests.post(
            session_endpoint,
            json=session_payload,
            headers=headers,
            timeout=15,
        )
        response.raise_for_status()
        response_data = response.json()
        session_id = response_data.get("name", "").split("/")[-1]

        return {
            "success": True,
            "task_id": task["id"],
            "status_code": response.status_code,
            "session_id": session_id,
            "session_url": response_data.get("webUri", f"https://jules.google/sessions/{session_id}"),
            "response": response_data,
        }
    except requests.exceptions.RequestException as e:
        return {
            "success": False,
            "task_id": task["id"],
            "error": str(e),
        }


def main():
    """Main entry point."""
    if not JULES_API_KEY:
        print("[ERROR] JULES_API_KEY not found in .env file")
        return 1

    print(f"[INFO] Sending Phase 1 Round 1 tasks to Jules API")
    print(f"[INFO] API URL: {JULES_API_URL}")
    print(f"[INFO] Tasks: {len(ROUND_1_TASKS)}")
    print()

    results = []
    for i, task in enumerate(ROUND_1_TASKS):
        task_title = task['title'].encode('utf-8', errors='replace').decode('utf-8')
        print(f"[SUBMIT] ({i+1}/{len(ROUND_1_TASKS)}) {task['id']}: {task_title}")
        result = send_task_to_jules(task)
        results.append(result)

        if result["success"]:
            print(f"[OK] Session created (HTTP {result['status_code']})")
            print(f"[SESSION] ID: {result['session_id']}")
            if result.get('session_url'):
                print(f"[URL] {result['session_url']}")
        else:
            print(f"[FAIL] Failed: {result['error']}")
        print()

    # Summary
    successful = sum(1 for r in results if r["success"])
    print(f"\n[SUMMARY] {successful}/{len(ROUND_1_TASKS)} tasks sent successfully")

    # Save results for reference
    results_file = Path("./logs/jules_task_submission.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)
    with open(results_file, "w") as f:
        json.dump({
            "timestamp": str(Path.cwd()),
            "phase": 1,
            "round": 1,
            "tasks_submitted": len(ROUND_1_TASKS),
            "successful": successful,
            "results": results,
        }, f, indent=2)

    print(f"[SAVED] Results saved to {results_file}")

    return 0 if successful == len(ROUND_1_TASKS) else 1


if __name__ == "__main__":
    exit(main())
