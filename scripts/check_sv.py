#!/usr/bin/env python3
"""Parse, type-check and elaborate the SystemVerilog files; does not simulate."""
import sys
from pathlib import Path

try:
    import pyslang
    from pyslang import ast, syntax
except ImportError:
    raise SystemExit("Install optional static-check dependencies: pip install -r requirements-check.txt")

ROOT = Path(__file__).resolve().parents[1]
compilation = ast.Compilation()
files = [line.strip() for line in (ROOT / "sim/arithmetic.f").read_text().splitlines() if line.strip()]
for source in files:
    compilation.addSyntaxTree(syntax.SyntaxTree.fromFile(str(ROOT / source)))
diagnostics = compilation.getAllDiagnostics()
if diagnostics:
    print(pyslang.DiagnosticEngine.reportAll(compilation.sourceManager, diagnostics))
    sys.exit(1)
print(f"PASS static SystemVerilog compilation: {len(files)} files, zero diagnostics, pyslang {pyslang.__version__}")
print("This checks parsing, types and elaboration. It is not a behavioral simulation.")
