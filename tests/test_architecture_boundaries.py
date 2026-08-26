import ast
from pathlib import Path

def get_imports(file_path: Path) -> set[str]:
    """Parses a Python file and returns all imported module names."""
    if not file_path.exists():
        return set()
    with open(file_path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), filename=str(file_path))

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    return imports

def test_guardrails_import_boundaries():
    """
    Guardrails (Stage 2) must never import from simulation (Stage 6).
    """
    project_root = Path(__file__).parent.parent
    guardrails_dir = project_root / "src" / "guardrails"
    
    for py_file in guardrails_dir.glob("**/*.py"):
        imports = get_imports(py_file)
        for imp in imports:
            assert not imp.startswith("src.simulation"), \
                f"Architecture violation: {py_file.name} imports {imp} from simulation layer."

def test_decision_import_boundaries():
    """
    Decision/Production (Stage 4) must never import from simulation (Stage 6)
    to prevent circular answer-key sharing. (Constraints A4, A8)
    """
    project_root = Path(__file__).parent.parent
    decision_dir = project_root / "src" / "decision"
    diagnosis_dir = project_root / "src" / "diagnosis"
    ml_dir = project_root / "src" / "ml"
    
    for layer_dir in [decision_dir, diagnosis_dir, ml_dir]:
        if not layer_dir.exists():
            continue
        for py_file in layer_dir.glob("**/*.py"):
            imports = get_imports(py_file)
            for imp in imports:
                assert not imp.startswith("src.simulation"), \
                    f"Architecture violation: {py_file.name} in {layer_dir.name} imports {imp} from simulation layer."

def test_diagnosis_import_boundaries():
    """
    Diagnosis layer (Stage 3) must remain isolated: it must not import from
    decision, guardrails, execution, or simulation layers.
    """
    project_root = Path(__file__).parent.parent
    diagnosis_dir = project_root / "src" / "diagnosis"
    
    banned_prefixes = ("src.simulation", "src.decision", "src.guardrails", "src.execution")
    for py_file in diagnosis_dir.glob("**/*.py"):
        imports = get_imports(py_file)
        for imp in imports:
            for banned in banned_prefixes:
                assert not imp.startswith(banned), \
                    f"Architecture violation: {py_file.name} in diagnosis layer imports {imp}."

def test_simulation_import_boundaries():
    """
    Simulation must not import from decision to avoid tight coupling 
    where simulator learns from the model it evaluates.
    """
    project_root = Path(__file__).parent.parent
    simulation_dir = project_root / "src" / "simulation"
    
    for py_file in simulation_dir.glob("**/*.py"):
        imports = get_imports(py_file)
        for imp in imports:
            assert not imp.startswith("src.decision"), \
                f"Architecture violation: {py_file.name} imports {imp} from decision layer."
