"""
NPCI Maximum Presentation Attempt Limiter Guardrail.
Citing: docs/knowledge_base/rbi_npci_regulations.md §1.1 (NPCI Circular, Aug 2025).
"""


def check_attempt_cap(attempt_count: int) -> bool:
    """
    Evaluates whether the mandate cycle is legally permitted further debit presentation attempts.

    Regulatory Citation:
        rbi_npci_regulations.md §1.1 — NPCI Mandate Execution Limits (Effective Aug 2025).
        A mandate cycle allows a maximum of 4 presentation attempts (1 original + 3 retries).

    Args:
        attempt_count: Number of lifetime presentation attempts already executed in this cycle (1-4).

    Returns:
        bool: True if further presentation attempts are permissible (attempt_count < 4),
              False if the 4-attempt cap has been reached or exceeded (attempt_count >= 4).

    Raises:
        ValueError: If attempt_count is less than 1.
    """
    if attempt_count < 1:
        raise ValueError(f"Invalid attempt_count {attempt_count}. Must be at least 1.")

    # Invariant: k <= 4. At attempt_count >= 4, all retry presentation attempts are exhausted.
    return attempt_count < 4
