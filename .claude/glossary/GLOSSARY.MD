# GLOSSARY — ISAMI ubiquitous language

This file defines the shared vocabulary of the ISAMI thermal-ML project.
It contains **definitions only**. Behavioural rules, conventions and workflow
live in `CLAUDE.md` and in project memory — not here.

When a term appears in Spanish (Edy), French (code) and English (logic) with the
same meaning, the equivalence is listed so the term resolves to one concept.

---

## 1. Cross-language term map (ES / FR / EN)

| Concept | ES (Edy) | FR (code) | EN (logic) | Definition |
|---|---|---|---|---|
| Sweep | barrido | parcours / `id_parcours` | sweep | One complete pass of the mobile robot over all 120 grid positions. ~6 sweeps per dataset. The atomic unit inside which cross-validation is performed. |
| Position | posición | position | position | One of the 120 discrete cells of the grid, identified by `(x, y, z)`. |
| Measured value | valor real / medido | `y_reel` | measured / true value | The observed `temperature_mean` at a held-out position. |
| Predicted value | valor predicho | `y_pred` | predicted value | The model's estimate for a held-out position. |
| Model | modelo | `modele` | model | A regression estimator (XGBoost, RandomForest, …). |
| Out-of-fold | — | `oof` | OOF | A position's prediction produced while that position was in the validation fold (never used in its own training). |

---

## 2. Physical system

**Grid (grille)** — The measurement volume, `8 (X) × 5 (Y) × 3 (Z) = 120 positions`.
`GRID_TAG = '8x5x3'`. Implemented order is **X = 8, Y = 5, Z = 3**. (The colloquial
"5×8×3" refers to the same 120 positions but is not the implemented axis order.)

**WIDTH** — Size of the X axis = 8 (columns A–H, indices 0–7).

**LENGTH** — Size of the Y axis = 5 (rows, indices 0–4).

**HEIGHT** — Size of the Z axis = 3 (levels, indices 0–2).

**Sensor** — One onboard temperature sensor. `N_SENSORS = 254`: the number of sensor
columns averaged per row to produce a single `temperature_mean` (legacy value: 120).

**`temperature_mean` (TARGET_COL)** — The regression target: mean temperature at a
position for a given sweep.

**Mobile robot** — The platform that physically visits each grid position during a sweep.

---

## 3. Coordinates & geometry

**`x`, `y`, `z`** — Integer grid indices. `x ∈ 0..7`, `y ∈ 0..4`, `z ∈ 0..2`.

**`z_m`** — Physical height in metres, `z_m = (z + 1) × Z_SPACING`. Domain:
`z=0 → 0.5 m`, `z=1 → 1.0 m`, `z=2 → 1.5 m`. Used for all physical-distance computations.

**`Z_SPACING`** — Vertical spacing between Z levels = 0.5 m.

**Serpentine X-inversion** — During coordinate assignment, the X order is reversed on
odd-Y rows (boustrophedon path), reflecting how the robot physically sweeps back and forth.

**`pos_id`** — Position identifier, the tuple `(x, y, z)`. Unique per grid cell; used for
by-position grouping in cross-validation.

**Grid centres** — `CENTER_X = 3.5`, `CENTER_Y = 2.0`, `CENTER_Z = 1.0 m`. Reference point
for `dist_center`.

**`dist_edge_x`** — Distance to the nearest X boundary: `min(x, (WIDTH-1) - x)`. Zero at `x=0` and `x=7`.

**`dist_edge_y`** — Distance to the nearest Y boundary: `min(y, (LENGTH-1) - y)`. Zero at `y=0` and `y=4`.

**`dist_edge_z`** — Distance to the nearest Z boundary, in metres:
`min(z_m - Z_SPACING, HEIGHT × Z_SPACING - z_m)`. Zero at `z=0` (0.5 m) and `z=2` (1.5 m).

**`dist_center`** — Euclidean distance from a position to the grid centre, using `z_m`
for the Z axis: `sqrt((x-CENTER_X)² + (y-CENTER_Y)² + (z_m-CENTER_Z)²)`.

**`FEATURE_COLS`** — The exact feature set fed to models:
`['x', 'y', 'z_m', 'dist_edge_x', 'dist_edge_y', 'dist_edge_z', 'dist_center']`.

---

## 4. Carried-but-never-used variables

**`t_sec`** — Time in seconds. Present in the dataframe for traceability but **never** a model feature.

**`direction_encode`** — Encoded sweep direction. Present in the dataframe but **never** a model feature.

---

## 5. Temperature bounds

**`T_MIN_PHYSICAL`, `T_MAX_PHYSICAL`** — Physical validity range, `-50 °C` to `200 °C`.
A reading outside this range marks a dead sensor and becomes `NaN`.

**`T_ROOM_MIN`, `T_ROOM_MAX`** — Realistic room range, `15 °C` to `35 °C`. Used for
**visualisation scaling only**, not for cleaning.

---

## 6. Validation vocabulary

**Spatial interpolation** — The scientific deliverable: predicting temperature at
held-out *positions within a single sweep*. This is the only target of the project.

**Temporal generalisation** — Predicting across time / across sweeps. Explicitly
**out of scope** as a deliverable.

**Per-barrido KFold** — The accepted validation scheme: KFold cross-validation performed
strictly within each sweep, so train and test positions always belong to the same sweep.

**Leave-one-parcours-out / Régimen B** — The validation scheme that holds out an entire
sweep at a time. **Explicitly rejected** for this project.

**KFold** — Splitting positions of one sweep into `N_FOLDS = 5` folds; each fold is
predicted once while the others train.

**`SEED_CV`** — Random state for the KFold split = 0 (controls split reproducibility).

**`SEED_MODEL`** — Random state for the models = 42 (controls model reproducibility).
Intentionally distinct from `SEED_CV`.

**Data leakage (temporal autocorrelation)** — The effect by which random train/test
splitting yields near-perfect R² because consecutive-in-time rows are correlated. The
reason random splitting is invalid and per-snapshot spatial holdout is used instead.

**Selective scaling** — Applying feature scaling, via a `Pipeline`, only to
scale-sensitive models (KNN, SVR, GPR, Ridge). Tree-based models are never scaled.
Scaling is fit inside the training fold to avoid leakage.

**Detrend / Convention B** — A linear detrend applied per sweep using the row index as
the predictor; residuals from every sweep are concatenated and a single R² is computed
on them. This is the basis of `R²_detrend`.

---

## 7. Metrics

**RMSE** — Root mean squared error of `y_pred` vs `y_reel`.

**MAE** — Mean absolute error of `y_pred` vs `y_reel`.

**R²** — Coefficient of determination of `y_pred` vs `y_reel`.

**Pearson** — Pearson correlation between `y_pred` and `y_reel`. Saturates (≥ 0.99) across
all models, therefore non-discriminating; reported but not used to rank models.

**`R²_oof`** — R² computed on the raw, pooled out-of-fold predictions. The **ceiling**
metric; includes any linear spatial trend.

**`R²_detrend` (Convention B)** — R² computed on the detrended OOF residuals (see Detrend /
Convention B). The **floor** metric and the **primary comparator** between models, because
it measures genuine spatial structure rather than linear trend.

---

## 8. Models

**XGBoost** — Gradient-boosted trees; the primary model. Parameters in `XGB_PARAMS`.

**RandomForest** — Bagged decision trees.

**ExtraTrees** — Extremely randomised trees.

**HistGradientBoostingRegressor** — Histogram-based gradient boosting.

**KNN** — k-nearest-neighbours regressor (scale-sensitive).

**SVR** — Support vector regressor (scale-sensitive).

**GaussianProcessRegressor (GPR)** — Gaussian-process regression (scale-sensitive).

**Ridge / LinearRegression** — Linear baselines (scale-sensitive).

**KrigingOK** — Ordinary Kriging interpolation.

**Regression Kriging** — Regression model combined with kriging of its residuals.

**Tree ensembles** — Collective term for RandomForest, ExtraTrees and XGBoost; they
dominate on `R²_detrend`.

**KrigingOK collapse** — The observed pattern where KrigingOK has high `R²_oof` but very
low `R²_detrend`, indicating it captured only the linear spatial trend, not real structure.

---

## 9. Code architecture vocabulary

**`config.py`** — Constants and paths only. No business logic, no `datetime.now()` at import.

**`chargement_donnees.py`** — Data loading and cleaning; produces the base cleaned dataframe.

**`features_spatiales.py`** — Pure geometric feature computation (Section 3 features + `pos_id`).

**`validation_spatiale.py`** — Per-sweep cross-validation and OOF assembly.

**`metriques.py`** — Metric computation (RMSE, MAE, R², Pearson, `R²_oof`, `R²_detrend`).

**`modeles.py`** — Model definitions and the selective-scaling pipelines.

**`visualisations.py`** — Plotting (heatmaps, profiles, scatters, rankings).

**`exportation.py`** — Centralised output via `ExportRun`.

**`ExportRun`** — Object representing one export run: one folder, one timestamp, all outputs
(`.csv`, `.txt`, `.png`, `.json`).

**`create_run(label)`** — Factory that creates `resultados/{timestamp}[_label]/` and writes
`run_info.json`.

**`resultados/{timestamp}/`** — The single output folder for one run.

**`run_info.json`** — Per-run reproducibility record (grid, features, target, seeds).

**`TS_FORMAT`** — Timestamp format `"%Y_%m_%d_%H_%M_%S"`.

**`GRID_TAG`** — String `'8x5x3'` embedded in output filenames.

**Golden master / golden reference** — The authoritative numeric output (from Chaima's
notebook) that migrated modules must reproduce.

**Golden-master regression test** — Verification that migrated code matches the golden
master via `np.allclose` at `1e-9` tolerance on RMSE, MAE, R² and Pearson.

**Monolithic notebook** — Chaima's original single-notebook implementation; source of the
golden master.

---

## 10. Visualisation vocabulary

**Daltonism compliance** — Constraint that colour is never the sole information channel;
it is always paired with markers, hatches, numeric annotations and black borders.

**`CMAP_FIELD`** — Colormap `cividis`, used for thermal fields (predicted / measured).

**`CMAP_ERROR`** — Colormap `RdYlBu_r`, used for error maps centred at 0.

**`PALETTE_NAME`** — Seaborn palette `"colorblind"` for categorical series.

**`MARKERS`, `HATCHES`** — Marker and hatch lists used to encode series without relying on colour.

---

## 11. Dataframe column names

The exact column strings used across the pipeline.

| Column | Meaning |
|---|---|
| `id_parcours` | Sweep identifier (FR). |
| `modele` | Model name (FR). |
| `x`, `y`, `z` | Integer grid indices. |
| `z_m` | Physical height in metres. |
| `temperature_mean` | Regression target. |
| `y_reel` | Measured value at a position (FR "réel"). |
| `y_pred` | Predicted value at a position. |
| `dist_edge_x`, `dist_edge_y`, `dist_edge_z` | Distances to nearest boundaries. |
| `dist_center` | Distance to grid centre. |
| `pos_id` | `(x, y, z)` position tuple. |
| `t_sec` | Time in seconds (carried, not a feature). |
| `direction_encode` | Sweep direction (carried, not a feature). |
| `R2`, `RMSE` | Per-sweep metric values. |
| `R2_oof`, `MAE_oof`, `RMSE_oof`, `Pearson_oof` | Pooled OOF metrics. |
| `R2_detrend_oof` | Detrended OOF R² (Convention B). |
| `RMSE_fold_std` | Standard deviation of RMSE across folds. |

---

## 12. Project phases

**Phase A** — Building orchestration notebooks that use the migrated `src/` modules to
produce reproducible baseline results.

**Phase B** — Deliberate bug fixes that intentionally shift numbers and require regenerating
the golden reference (includes a loose HS-channel filter and a temperature-range title mismatch).

**Phase C** — Optional fixed-sensor columns as features for real-field deployment (future data).

**Phase D** — Project README and Mitacs technical report.

**Phase E** — Parallel internship threads: SLAM/Nav2 research and paper review.

---

## 13. Roles

**Edy** — Project author (Mitacs Globalink intern).

**Chaima** — Colleague; author of the original monolithic notebook that serves as the
golden-master regression target.
