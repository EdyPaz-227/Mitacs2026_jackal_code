---
name: paper-method-extractor
description: Use when reading an academic paper (Geng 2022 or similar) to extract a method for implementation. Produces a structured extraction document with inputs, outputs, equations, and caveats.
---

# Paper method extraction

When extracting a method from a paper:

1. Read the Methods section first; note section and equation numbers.
2. Extract into a structured document:
   - **Inputs**: data consumed (variable names, shapes, types).
   - **Algorithm steps**: numbered, one step per equation or procedure.
   - **Outputs**: what the method produces.
   - **Hyperparameters**: defaults and search ranges if given.
   - **Evaluation metrics**: as defined in the paper.
   - **Caveats / assumptions**: stationarity, grid regularity, sensor density, etc.
3. Map paper variables to ISAMI equivalents (e.g., paper "position" → `pos_id`;
   "measurement" → `temperature_mean`).
4. Flag any gap between paper assumptions and ISAMI setup (serpentine route, 3 floors,
   ~6 sweeps, ~820 rows).
5. Output as Markdown only — do not write src/ code in this step.
