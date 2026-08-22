import pytest
from src.core.models import MandateStateRecord
from src.simulation.batch_generator import generate_batch, ALL_CODES, MALFORMED_CODES

def test_schema_validation_zero_errors():
    """Confirms every generated record validates against the Pydantic schema."""
    batch = generate_batch(50, seed=1)
    for record in batch:
        json_str = record.model_dump_json()
        # This will raise ValidationError if invalid
        parsed = MandateStateRecord.model_validate_json(json_str)
        assert parsed.case_id == record.case_id

def test_failure_code_distribution():
    """Confirms all known codes and malformed codes appear in a large enough batch."""
    batch = generate_batch(500, seed=2)
    codes_seen = set(r.failure_code for r in batch)
    
    for code in ALL_CODES:
        assert code in codes_seen, f"Expected {code} to be generated"
        
    for m_code in MALFORMED_CODES:
        assert m_code in codes_seen, f"Expected {m_code} to be generated"

def test_batch_determinism():
    """Confirms same random seed produces the exact same batch."""
    batch1 = generate_batch(100, seed=42)
    batch2 = generate_batch(100, seed=42)
    
    for r1, r2 in zip(batch1, batch2):
        assert r1.case_id == r2.case_id
        assert r1.failure_code == r2.failure_code
        assert r1.amount_inr == r2.amount_inr
        assert r1.ground_truth_recoverable == r2.ground_truth_recoverable
