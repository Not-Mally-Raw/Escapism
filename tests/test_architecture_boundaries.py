"""
Static Architecture Boundary & Physical Import Enforcement Tests.
Verifies that deterministic guardrails maintain 100% isolation from probabilistic
decision layers, configuration priors, and simulation models.
"""

import ast
from pathlib import Path
import pytest

GUARDRAILS_DIR = Path(__file__).parent.parent / "src" / "guardrails"

# Forbidden import root packages for the guardrails layer
FORBIDDEN_IMPORT_PREFIXES = (
    "src.simulation",
    "src.core.config",
    "src.decision",
    "src.diagnostic",
)


def get_imports_from_file(file_path: Path) -> list[str]:
    """Parses a Python file and returns all imported module names."""
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


def test_guardrails_import_boundaries():
    """
    Exhaustively checks every file in src/guardrails/ to assert physical separation:
    - NO imports from src.simulation.*
    - NO imports from src.core.config.*
    - NO imports from src.decision.*
    """
    guardrail_files = list(GUARDRAILS_DIR.glob("*.py"))
    assert len(guardrail_files) >= 6, f"Expected at least 6 guardrail files, found {len(guardrail_files)}"

    for file_path in guardrail_files:
        imports = get_imports_from_file(file_path)
        for imp in imports:
            for forbidden in FORBIDDEN_IMPORT_PREFIXES:
                assert not imp.startswith(forbidden), (
                    f"Architecture Violation in {file_path.name}: "
                    f"Guardrail layer must not import from '{imp}'"
                )
