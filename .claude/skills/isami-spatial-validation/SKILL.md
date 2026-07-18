---
name: isami-spatial-validation
description: Use when creating, editing, or reviewing any spatial cross-validation or evaluation code for ISAMI temperature interpolation. Encodes KFold-within-barrido, dual R² reporting, pooled OOF residuals, and the golden-master regression guard. Trigger on validation_spatiale, metriques, CV design, R² detrend, or OOF work.
---

# ISAMI spatial validation

When working on evaluation / validation code:
1. CV is KFold **within each barrido** (hold out grid positions inside a sweep).
   Never leave-one-route-out / Régime B.
2. Produce out-of-fold predictions per model into `oof_avec_pos` with columns:
   `modele, y_reel, y_pred, id_parcours`.
3. Per model compute: RMSE, MAE, R²_oof (raw), R²_detrend (pooled OOF residuals),
   Pearson. R²_detrend is the primary spatial comparator.
4. Report dual R²: raw (ceiling) and detrended (floor), both honestly.
5. Validate vs the golden master: np.allclose on RMSE_oof (hard tol 1e-9;
   soft 0.005 for R²_detrend) before declaring done.
6. Respect .claude/rules/ (language; cividis / RdYlBu_r; never colour-only).