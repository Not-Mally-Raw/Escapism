import pytest
from src.simulation.models import SimulationRecord
from src.simulation.batch_generator import generate_batch, ALL_CODES, MALFORMED_CODES

def test_schema_validation_zero_errors():
    """Confirms every generated record validates against the Pydantic schema."""
    batch = generate_batch(50, seed=1)
    for record in batch:
        json_str = record.model_dump_json()
        parsed = SimulationRecord.model_validate_json(json_str)
        assert parsed.state.case_id == record.state.case_id

def test_failure_code_distribution():
    """Confirms all known codes and malformed codes appear in a large enough batch."""
    batch = generate_batch(500, seed=2)
    codes_seen = set(r.state.failure_code for r in batch)
    
    for code in ALL_CODES:
        assert code in codes_seen, f"Expected {code} to be generated"
        
    for m_code in MALFORMED_CODES:
        assert m_code in codes_seen, f"Expected {m_code} to be generated"

def test_batch_determinism():
    """Confirms same random seed produces the exact same batch."""
    batch1 = generate_batch(100, seed=42)
    batch2 = generate_batch(100, seed=42)
    
    for r1, r2 in zip(batch1, batch2):
        assert r1.state.case_id == r2.state.case_id
        assert r1.state.failure_code == r2.state.failure_code
        assert r1.state.amount_inr == r2.state.amount_inr
        assert r1.ground_truth_recoverable == r2.ground_truth_recoverable


def test_causal_batch_generation_contract():
    """
    R3 Contract Verification:
    - potential_outcome_noop = Bernoulli(mu_0(state))
    - potential_outcome[action] = Bernoulli(clip(mu_0(state) + tau(state, action), 0, 1))
    - observed_outcome = potential_outcome[observed_action]
    - ground_truth_recoverable = potential_outcome_noop
    """
    from src.simulation.batch_generator import generate_causal_batch, NOOP_ACTION

    causal_batch = generate_causal_batch(200, seed=42)
    assert len(causal_batch) == 200

    for r in causal_batch:
        assert r.potential_outcomes is not None
        assert NOOP_ACTION in r.potential_outcomes
        assert r.ground_truth_recoverable == r.potential_outcomes[NOOP_ACTION]
        assert r.observed_outcome == r.potential_outcomes[r.observed_action]
        assert isinstance(r.ground_truth_recoverable, bool)
        assert isinstance(r.observed_outcome, bool)


def test_logged_propensity_positivity_floor():
    """
    R3 Positivity & Common Support Verification:
    Asserts that every logged action has propensity pi(a | S) >= 0.05 to prevent IPS explosion.
    """
    from src.simulation.batch_generator import generate_causal_batch

    causal_batch = generate_causal_batch(500, seed=123)
    for r in causal_batch:
        assert r.propensity >= 0.05, f"Positivity violation: {r.propensity} < 0.05 for action {r.observed_action}"
        assert r.propensity <= 1.0

