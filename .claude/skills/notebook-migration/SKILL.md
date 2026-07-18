---
name: notebook-migration
description: Use when extracting logic from codigo_de_chaima_3_fase6_lite.py into a new or existing src/ module. Enforces minimal change, golden-master guard, and ISAMI naming conventions.
---

# Notebook → src migration

When migrating a notebook cell or block:

1. Read the target cell(s) in the reference notebook first; understand expected state variables.
2. Identify the minimal public function needed — one extraction per task.
3. Translate Spanish/French identifiers to English; preserve already-integrated ones:
   `modele`, `y_reel`, `y_pred`, `id_parcours`.
4. Follow .claude/rules/ (English code, French prints with # EN:, English docstrings).
5. After writing the function, run `py src/<module>.py` to verify the self-test passes.
6. Golden-master guard: if the extraction touches a hard metric (RMSE/MAE/R²/Pearson),
   run `py src/test_end_to_end.py` and confirm np.allclose at 1e-9.
7. Never migrate `t_sec` or `direction_encode` into FEATURE_COLS.
8. End with: files changed, self-test result, golden-master status.
