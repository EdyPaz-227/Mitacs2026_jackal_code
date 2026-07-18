---
name: ml-code-review
description: Use before committing changes to any src/ ML module. Checks for data leakage, incorrect CV design, missing dual-R² reporting, scaler misuse, and ISAMI scientific invariants.
---

# ML code review checklist

Run this skill on any src/ diff before committing.

1. **Leakage**: scaler fit on train only? Any future/label-correlated column in FEATURE_COLS?
2. **CV design**: KFold within each `id_parcours`? No global random split? No leave-one-route-out?
3. **Metrics**: output reports RMSE, MAE, R²_oof (raw), R²_detrend (pooled OOF), and Pearson?
4. **Scaler invariant**: trees skip scaler; distance/linear models use `Pipeline(StandardScaler + model)`.
5. **Excluded columns**: `t_sec` and `direction_encode` absent from features?
6. **Serpentine correction**: on odd `y`, `x = (WIDTH-1) - x`?
7. **z vs z_m**: distances use `z_m`, not `z`?
8. **Language**: prints French with # EN:; identifiers English; no Spanish?
9. **Colorblind**: no color-only encoding?
10. Report findings as Critical / Warning / Suggestion with file:line and a concrete fix.
