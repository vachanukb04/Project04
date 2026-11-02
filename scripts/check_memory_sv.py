#!/usr/bin/env python3
"""Static compilation only; does not execute the memory integration test."""
from pathlib import Path
import pyslang
from pyslang import ast,syntax
root=Path(__file__).resolve().parents[1]
c=ast.Compilation()
for name in (root/'sim/memory_engine.f').read_text().splitlines():
    c.addSyntaxTree(syntax.SyntaxTree.fromFile(str(root/name)))
diags=c.getAllDiagnostics()
if diags:
    print(pyslang.DiagnosticEngine.reportAll(c.sourceManager,diags))
    raise SystemExit(1)
print(f'PASS memory-engine static compilation: four files, zero diagnostics, pyslang {pyslang.__version__}')
print('Behavioral simulation remains a separate check.')
