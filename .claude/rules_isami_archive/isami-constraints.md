# ISAMI scientific constraints
- Task = spatial interpolation over the robot's measured positions, NOT temporal
  generalization to unseen routes. Leave-one-route-out (Régime B) is removed.
- Cross-validation: KFold *within each barrido* (hold out grid positions in a sweep).
- Metrics: RMSE, MAE, R², Pearson. Report raw R²_oof (ceiling) AND detrended R²
  (floor, pooled OOF residuals = primary spatial comparator).
- Known confound: Y-coordinate ≈ measurement order within a sweep (temporal drift).
  Treat high raw R² with caution; trust detrended R².
- Reference model: RandomForest (spatial reference). Deployment candidate: XGBoost.
- Kriging caveat: ordinary kriging captures mainly the linear trend; its detrended R²
  collapses — flag this, never present raw R² as spatial skill.
- Single source of truth for all constants: src/config.py.