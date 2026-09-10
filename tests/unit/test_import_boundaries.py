from __future__ import annotations

import ast
import importlib
import pkgutil
import subprocess
import sys
from pathlib import Path

import xprot.core

FORBIDDEN_IMPORTS = {"click", "fastapi", "uvicorn", "starlette"}
FORBIDDEN_PREFIXES = ("xprot.app", "xprot.cli", "xprot.gui")

CORE_DIR = Path(xprot.core.__file__).parent


def _core_modules() -> list[str]:
    return [f"xprot.core.{m.name}" for m in pkgutil.iter_modules([str(CORE_DIR)])]


def test_core_source_has_no_forbidden_imports() -> None:
    offenders: list[str] = []
    for path in sorted(CORE_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for name in names:
                root = name.split(".")[0]
                if root in FORBIDDEN_IMPORTS or name.startswith(FORBIDDEN_PREFIXES):
                    offenders.append(f"{path.name}: {name}")
    assert offenders == []


def test_importing_core_does_not_pull_frameworks() -> None:
    modules = _core_modules()
    assert modules, "expected to discover xprot.core submodules"
    script = (
        "import sys;"
        f"[__import__(m) for m in {modules!r}];"
        f"bad = sorted(set(sys.modules) & {FORBIDDEN_IMPORTS!r});"
        "print(','.join(bad))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == ""


def test_every_core_module_imports() -> None:
    for module in _core_modules():
        importlib.import_module(module)
