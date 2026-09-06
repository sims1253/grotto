"""Grotto: a perceptually engineered adaptive coding colour system.

Layers: L1 semantics (spec/roles.yaml, spec/distance-matrix.yaml), L2 the
environmental transform (src/grotto/model.py + spec/environments.yaml), L3
editor bindings (spec/mappings/, src/grotto/vscode.py, src/grotto/zed.py).
Evaluation tooling
(colour maths, contrast, CVD, spectral, reports, specimens) sits beside the
layers and depends only on L1/L2.  No palette is finalised; see DESIGN.md.
"""
