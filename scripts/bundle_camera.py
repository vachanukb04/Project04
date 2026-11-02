#!/usr/bin/env python3
"""Bundle abstract camera-stream RTL for ChipVerify; no webcam access here."""
import argparse
from pathlib import Path
import pyslang
from pyslang import ast,syntax
r=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
files={'design.sv':'rtl/p04_camera_capture.sv','testbench.sv':'tb/tb_p04_camera_capture.sv'}
c=ast.Compilation()
for output,source in files.items():
    content=(r/source).read_text();p=r/'sim/chipverify_camera'/output;p.parent.mkdir(parents=True,exist_ok=True)
    if a.check:
        if not p.exists() or p.read_text()!=content:raise SystemExit(f'Stale {p}')
    else:p.write_text(content)
    c.addSyntaxTree(syntax.SyntaxTree.fromFile(str(r/source)))
d=c.getAllDiagnostics()
if d:print(pyslang.DiagnosticEngine.reportAll(c.sourceManager,d));raise SystemExit(1)
print('PASS camera-stream static compilation: two files, zero diagnostics; behavioral simulation pending')
