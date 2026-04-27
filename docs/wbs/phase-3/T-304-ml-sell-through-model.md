# T-304 — ML sell-through model (replaces static condition factor)

| Field | Value |
|---|---|
| Phase | 3 (P2) |
| Effort | 24 hours |
| Depends on | T-205 (backtest harness), T-302 (velocity store) |
| Blocks | — |
| Status | Not started |

---

## Context

`condition.sellable_factor` is a 7-bucket static prior. Reality has wide
variance even within a bucket: a `not_tested` Pigeon mixer at ₹500 floor on a
₹2,500 MRP behaves very differently from a `not_tested` Crystal toaster at
₹400 floor on a ₹1,200 MRP. A model trained on real outcomes can do
materially better than a static map.

This task trains and deploys a sell-through regression model behind the same
`Settings` interface so the rest of the pipeline doesn't change.

## Files to create / modify

- `intelligence/sell_through_model.py` — model wrapper.
- `tools/train_sell_through.py` — training script.
- `data/models/sell_through_v1.pkl` (or equivalent) — trained artefact.
- `intelligence/profit.py` — load model lazily, fall back to static prior on miss.
- `tests/test_sell_through_model.py`.
- `requirements.txt` — add `scikit-learn`.
- `README.md`.

## Specification

### Model class signature

```python
@dataclass(frozen=True)
class SellThroughModel:
    """Wraps a fitted sklearn model + feature pipeline.

    Predicts ``sell_through_30d ∈ [0, 1]`` per row.  Always also returns
    a confidence ∈ [0, 1] derived from prediction-interval width.
    """
    pipeline: object
    feature_cols: list[str]

    def predict(self, df: pd.DataFrame) -> pd.DataFrame:
        """Return a DataFrame with ``sell_through_pred`` and ``sell_through_conf``."""
```

### Features

Minimum feature set:
- `category` (one-hot)
- `condition_normalized` (one-hot)
- `brand_known` (bool)
- `discount_percentage`
- `price_band` (LOW/MID/HIGH)
- `mrp` (log-scaled)
- `floor_to_mrp_ratio`
- `category_demand_score`
- `category_liquidity_score`
- `amazon_bsr` (log-scaled, when available; else median imputation)
- `quantity` (log-scaled)

### Model

Start with `sklearn.ensemble.GradientBoostingRegressor` or `LightGBM` if
available. Train on outcomes accumulated by T-205 (`realised_units_sold /
expected_units_sold` as the target). Persist with joblib.

### `intelligence/profit.py` integration

```python
sell_through_model = self._maybe_load_sell_through_model()
if sell_through_model is not None:
    pred_df = sell_through_model.predict(out)
    velocity_estimate = pred_df["sell_through_pred"].clip(0, 1)
    velocity_confidence = pred_df["sell_through_conf"]
    # Blend with static prior by confidence (same as T-302)
else:
    velocity_estimate, velocity_confidence = self._resolve_velocity(out)  # T-302 fallback
```

The model is loaded lazily and silently fallback to T-302's velocity store /
static prior if the artefact is absent or fails to load.

### Training script

```
usage: python -m tools.train_sell_through --history data/historical/*.csv --out data/models/sell_through_v1.pkl

Reads historical outcome CSVs, joins to manifests via sku, builds the feature
matrix, trains the model with k-fold CV, prints metrics, persists artefact.
```

## Acceptance criteria

- [ ] `intelligence/sell_through_model.py` ships with the wrapper class.
- [ ] `tools/train_sell_through.py` produces a `.pkl` from realistic synthetic data shipped in `data/historical/`.
- [ ] Pipeline loads the model lazily and falls back gracefully.
- [ ] CSV gains `sell_through_pred` and `sell_through_conf` columns when the model is loaded.
- [ ] Backtest report (T-205) shows roi_correlation ≥ 0.65 with the model loaded vs ≤ 0.45 without (proves the model adds signal). Tune feature set until met.
- [ ] Pipeline still passes all existing tests when the model artefact is absent.

## Test requirements

1. `test_pipeline_works_without_model_artifact` — delete the .pkl, run pipeline, succeeds with static prior.
2. `test_model_predict_in_range` — predictions for any row are in [0, 1].
3. `test_training_script_runs_on_synthetic_data` — invoke training with the example outcomes; assert artefact written.
4. `test_model_loaded_when_present` — pipeline detects and uses the artefact when present.

## Documentation requirements

- [ ] `README.md` § 6 (extension points): "How to retrain the sell-through model".
- [ ] `tools/train_sell_through.py` docstring + CLI `--help`.
- [ ] `intelligence/sell_through_model.py` documents the feature contract.

## Out of scope

- Online / streaming retraining.
- Multi-target models (sell-through and return rate jointly).
- Deep-learning models — gradient boosting is more than enough for tabular liquidation data.

## Risks & considerations

- Models trained on small data (< 1,000 outcomes) overfit. Document the
  minimum data threshold + crash-safely refuse to load if training data is
  too thin.
- Drift: the model goes stale as marketplace dynamics shift. T-305 outcomes
  feedback should trigger periodic retraining; document the cadence.
