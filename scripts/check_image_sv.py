#!/usr/bin/env python3
"""Static compilation of the real-image convolution suite, not behavioral simulation."""
from pathlib import Path
import pyslang
from pyslang import ast,syntax
root=Path(__file__).resolve().parents[1];c=ast.Compilation()
for name in (root/'sim/image_nn.f').read_text().splitlines():
    c.addSyntaxTree(syntax.SyntaxTree.fromFile(str(root/name)))
d=c.getAllDiagnostics()
if d:
    print(pyslang.DiagnosticEngine.reportAll(c.sourceManager,d));raise SystemExit(1)
print(f'PASS image NN static compilation: five files, zero diagnostics, pyslang {pyslang.__version__}')
