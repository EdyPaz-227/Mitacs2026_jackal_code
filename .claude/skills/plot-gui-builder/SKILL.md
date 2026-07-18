---
name: plot-gui-builder
description: Use when building or modifying an interactive visualization widget (ipywidgets, matplotlib, Panel) for ISAMI thermal field exploration. Enforces colorblind palette, French labels, and no src/ API breakage.
---

# Interactive plot builder

When building a GUI widget:

1. Check `src/visualisations.py` for existing functions; wrap them rather than duplicating logic.
2. Use `cividis` for thermal fields, `RdYlBu_r` for error maps; add markers or numeric
   annotations — never encode data by color alone.
3. Widget labels, dropdown options, and plot titles in French.
4. Accept pre-computed DataFrames as arguments; never load data or run models inside widget code.
5. Test in a notebook cell before integrating; confirm the widget renders without errors.
6. New public functions added to `visualisations.py` must follow its existing positional-df,
   keyword-options signature style.
