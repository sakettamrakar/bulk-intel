# Jules Task Submission Package - Phase 1 Round 1

**Status:** Ready for submission  
**Date:** 2026-04-27  
**Tasks:** 4 (all parallelizable)  
**Total Effort:** 16 hours

---

## Summary

All Phase 1 Round 1 tasks have been analyzed, dependency-mapped, and prepared for submission to Jules. These 4 tasks have **zero interdependencies** and can execute in **parallel**.

---

## Tasks Ready for Jules

### 1. T-101: Platform Fee Table (6 hours)

**Source File:** `docs/wbs/phase-1/T-101-platform-fee-table.md`

**Jules Prompt:**
```
Implement task T-101: Decompose operating_cost_pct into platform x category fee table

OBJECTIVE:
Replace flat operating_cost_pct (0.25) with structured PLATFORM_FEES lookup keyed on 
(platform, category). Real Amazon fees in India vary 5-30% by category.

KEY CHANGES REQUIRED:
- config/settings.py - add PLATFORM_FEES dict with 3+ platforms x 10+ categories
- intelligence/profit.py - replace flat fee with table lookup
- output/reporter.py - surface platform_fee_pct column
- tests/test_cost_engine.py - new test file

ACCEPTANCE CRITERIA:
- PLATFORM_FEES dict with Amazon, Flipkart, Meesho, B2B platforms
- Settings dataclass exposes 4 new fields with defaults
- operating_cost_pct removed from PROFIT_ASSUMPTIONS
- Output CSV includes platform_fee_pct column
- Pipeline runs end-to-end without error
- BUY-basket ROI changes meaningfully on real manifest

GITHUB BRANCH: feat/t-101-platform-fee-table
```

---

### 2. T-102: Inspection Cost (3 hours)

**Source File:** `docs/wbs/phase-1/T-102-inspection-cost.md`

**Jules Prompt:**
```
Implement task T-102: Add inspection cost for not_tested / unknown

OBJECTIVE:
Add inspection cost model for items with not_tested or unknown condition status.
Critical for cost accuracy on liquidation lots.

KEY CHANGES REQUIRED:
- config/settings.py - add INSPECTION_COST_BY_CONDITION
- intelligence/profit.py - add inspection cost calculation
- output/reporter.py - surface inspection_cost column

ACCEPTANCE CRITERIA:
- INSPECTION_COST_BY_CONDITION dict added to config
- Inspection cost applied per condition status
- Output includes inspection_cost column
- All condition statuses handled (tested, not_tested, unknown)

GITHUB BRANCH: feat/t-102-inspection-cost
```

---

### 3. T-103: Transport Cost (5 hours)

**Source File:** `docs/wbs/phase-1/T-103-transport-cost.md`

**Jules Prompt:**
```
Implement task T-103: Add category-aware transport cost (weight tiers)

OBJECTIVE:
Implement category-aware transport cost with weight-based tiers instead of flat rate.
Transport can be 5-15% of revenue depending on weight and destination.

KEY CHANGES REQUIRED:
- config/settings.py - add TRANSPORT_COST_BY_CATEGORY_WEIGHT
- intelligence/profit.py - add weight-tier transport cost lookup
- output/reporter.py - surface transport_cost column

ACCEPTANCE CRITERIA:
- Transport cost dict with category x weight tiers
- Weight tiers defined for each category
- Transport cost applied per row based on category and weight
- Output includes transport_cost column
- Fallback for unknown categories

GITHUB BRANCH: feat/t-103-transport-cost
```

---

### 4. T-106: Price Confidence Gate (2 hours)

**Source File:** `docs/wbs/phase-1/T-106-uncertain-price-gate.md`

**Jules Prompt:**
```
Implement task T-106: Hard gate - low match_confidence downgrades BUY to REVIEW

OBJECTIVE:
Implement pricing confidence gate that downgrades low-confidence price matches from 
BUY to REVIEW recommendation. Prevents committing capital on uncertain pricing.

KEY CHANGES REQUIRED:
- config/settings.py - add CONFIDENCE_THRESHOLD_FOR_BUY
- intelligence/scoring.py - add confidence gate logic
- output/reporter.py - surface confidence_gate_applied flag

ACCEPTANCE CRITERIA:
- CONFIDENCE_THRESHOLD_FOR_BUY constant defined
- Items below threshold automatically downgraded to REVIEW
- Output includes confidence_gate_applied column
- Audit trail of downgraded recommendations

GITHUB BRANCH: feat/t-106-uncertain-price-gate
```

---

## Submission Methods

### Method 1: Jules Dashboard (Recommended)

1. Go to https://jules.google
2. Log in with your Google account
3. Create a new project session for `bulk-intel`
4. For each task above:
   - Click "New Task" or "+ Create"
   - Paste the Jules Prompt from above
   - Set **Automation Mode:** `AUTO_CREATE_PR`
   - Set **Starting Branch:** `main`
   - Set **Source:** `sources/github/saketam/bulk-intel`
5. All 4 tasks will run in **parallel** (no dependencies)

### Method 2: API Call

If you have the correct Jules API endpoint URL, use:

```bash
export JULES_API_KEY="your-api-key-here"
export JULES_API_URL="<your-correct-endpoint>"

python send_tasks_to_julius.py
```

### Method 3: GitHub Integration

If Jules is integrated with your GitHub repo:
1. Create 4 GitHub issues (one per task)
2. Add label `jules` or `auto-assign-jules`
3. Include the Jules Prompt in the issue body
4. Jules should pick them up automatically

---

## Key Information for Jules

**Repository:** `saketam/bulk-intel`  
**Starting Branch:** `main`  
**Automation Mode:** `AUTO_CREATE_PR`  
**Approval Mode:** `Auto-approve plans`

**Constraints for all tasks:**
- All changes must pass `pytest` (80%+ coverage required)
- Must include documentation in the same commit
- Must test on real manifest: `data/e8c203803afa10d11e3844dd57636779.xlsx`
- PR description should include BUY/REVIEW/SKIP distribution

---

## Phase 1 Workflow

```
Round 1 (PARALLEL): T-101, T-102, T-103, T-106  (16 hours wall-clock ≈ 6h longest)
    ↓
Round 2: T-104 (depends on T-101) (5 hours)
    ↓
Round 3: T-105 (depends on all prior) (2 hours)
    ↓
Phase 1 Complete
```

---

## Next Steps After Submission

1. **Monitor Jules sessions** — All 4 tasks should show as "In Progress"
2. **Track PRs** — Each task will create a feature branch and PR
3. **Update status board** — `docs/wbs/README.md` status board
4. **Review PRs** — Verify acceptance criteria, test coverage, documentation
5. **Merge** — Once approved, merge to main
6. **Start Round 2** — T-104 becomes available once T-101 merges

---

## File References

- **Task Details:** `docs/wbs/phase-1/T-*.md` (detailed specifications)
- **Manifest:** `phase-1-round-1-manifest.json` (structured data)
- **Submission Script:** `send_tasks_to_julius.py` (automated API submission)
- **WBS Status:** `docs/wbs/README.md` (overall tracking)

---

## Questions?

- Check individual task files (`docs/wbs/phase-1/T-*.md`) for complete specifications
- See `PHASE-1-ROUND-1-SUBMISSION.md` for detailed submission instructions
- Review `phase-1-round-1-manifest.json` for structured task data

---

**Status:** READY FOR SUBMISSION ✅
