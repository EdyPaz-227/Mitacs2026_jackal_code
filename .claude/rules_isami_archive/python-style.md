# Python style (ISAMI)
- Minimal, readable changes. Preserve existing structure and Chaima's conventions.
- Do not rename already-integrated identifiers.
- No new dependencies without asking.
- No PCA unless dimensionality is shown to be a real problem; prefer original,
  interpretable features.
- Every module extraction must pass the golden-master regression (np.allclose RMSE_oof).
- Small functions; English docstring; French print() with # EN: inline.
-Comment almost every line to explain what does it do, shortly