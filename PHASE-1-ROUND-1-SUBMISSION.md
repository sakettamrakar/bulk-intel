# Phase 1 Round 1 Task Submission

**Submitted:** 2026-04-27  
**Phase:** 1 (P0 — Cost-engine truth)  
**Round:** 1 (Parallel execution)  
**Status:** Ready for Jules submission

---

## Tasks Ready for Parallel Execution

| Task | Title | Effort | Dependencies | Status |
|------|-------|--------|--------------|--------|
| **T-101** | Platform fee table (platform x category) | 6h | None | READY |
| **T-102** | Inspection cost for unknown items | 3h | None | READY |
| **T-103** | Category-aware transport cost (weight tiers) | 5h | None | READY |
| **T-106** | Price confidence gate (BUY -> REVIEW) | 2h | None | READY |

**Total Effort:** 16 hours  
**Critical Path:** T-101 (6h) → T-104 (5h, depends on T-101) → T-105 (2h, all prior)

---

## Submission Details

### 1. Task Manifest
Complete task manifest with specifications, acceptance criteria, and test cases:
- **File:** `phase-1-round-1-manifest.json`
- **Format:** JSON with full task details
- **Ready to import into Jules**

### 2. Individual Task Files
Detailed specification documents (self-contained):
- `docs/wbs/phase-1/T-101-platform-fee-table.md` (6h)
- `docs/wbs/phase-1/T-102-inspection-cost.md` (3h)
- `docs/wbs/phase-1/T-103-transport-cost.md` (5h)
- `docs/wbs/phase-1/T-106-uncertain-price-gate.md` (2h)

### 3. How to Submit to Jules

#### Option A: Direct API Submission
If Jules API endpoint is configured:
```bash
# Set up the Jules API endpoint
export JULES_API_URL=<your-jules-api-endpoint>

# Submit using the prepared script
python send_tasks_to_jules.py
```

#### Option B: Import Manifest
If Jules supports JSON import:
```bash
# Import the complete manifest
curl -X POST https://<jules-endpoint>/v1/import \
  -H "Authorization: Bearer $JULES_API_KEY" \
  -H "Content-Type: application/json" \
  -d @phase-1-round-1-manifest.json
```

#### Option C: Manual Import
1. Log into Jules dashboard
2. Navigate to project: `bulk-intel`
3. Create new round: `Phase 1 - Round 1`
4. Import `phase-1-round-1-manifest.json`
5. Assign tasks to engineers
6. Set execution mode: **Parallel** (no dependencies between tasks)

---

## Key Points

**Why These 4 Tasks in Round 1?**
- No inter-task dependencies
- Can execute in parallel (total wall-clock time ≈ 6h = longest single task)
- All are P0 blockers for cost-engine accuracy
- Collectively unblock downstream rounds

**What Happens Next?**

After Round 1 completes:
1. **Round 2:** T-104 (return-rate model) — depends on T-101
2. **Round 3:** T-105 (cost decomposition output) — depends on all prior

**Phase 1 Exit Criteria:**
- Every BUY recommendation has auditable per-row cost breakdown
- CSV + JSON outputs include all cost component columns
- Backtest on real manifest reproduces plausible ROI

---

## Prepared Artifacts

1. **phase-1-round-1-manifest.json** — Complete task manifest with all specs
2. **send_tasks_to_jules.py** — Automated submission script (requires JULES_API_URL)
3. **phase-1/T-*.md files** — Detailed task specifications (existing)
4. **This document** — Submission summary and instructions

---

## Next Steps

1. **Configure Jules API endpoint** (if not already set)
   ```bash
   export JULES_API_URL=<your-jules-api-url>
   ```

2. **Submit tasks to Jules** using one of the methods above

3. **Assign tasks** to engineers with clear start dates

4. **Monitor execution** — all 4 tasks should run in parallel

5. **Track completion** — update `docs/wbs/README.md` status board when each task ships

---

## Notes for Jules Operators

- **Execution model:** All 4 tasks are independent; schedule simultaneously
- **Resource requirement:** 1 engineer per task or 1 engineer rotating (16h total work)
- **Quality gate:** 80%+ test coverage required per CLAUDE.md
- **Documentation:** Each task updates code + docs in the same commit
- **Smoke test:** Pipeline validation on `data/e8c203803afa10d11e3844dd57636779.xlsx`
- **Status tracking:** Update PR description with new BUY/REVIEW/SKIP distribution

---

Generated: 2026-04-27
