"""
Customer Channel Consent Guardrail.
Citing: docs/research/market_context.md §3.4 (self-imposed best practice,
not derived from NPCI/RBI regulation).

Consent-revocation is a hard mask on the feasible action set, structurally
identical to the other six guardrails. If a customer has opted out of a
communication channel, that channel's action is removed from the feasible
set. If consent status is UNKNOWN, the channel is blocked (fail-closed),
consistent with every other guardrail's missing-information default.

Enforcement level: 🟡 BEST_PRACTICE (self-imposed).
"""

from src.core.types import ConsentStatus


# Maps ActionType names to the consent channel key they require.
# Only actions that involve outbound customer communication are gated.
ACTION_TO_CHANNEL: dict[str, str] = {
    "WHATSAPP_NUDGE": "WHATSAPP",
    "SMS_NUDGE": "SMS",
    "PAYMENT_LINK": "PAYMENT_LINK",
}


def is_channel_permitted(
    channel_consent: dict[str, ConsentStatus],
    channel: str,
) -> bool:
    """
    Checks whether a specific communication channel is permitted based on
    the customer's consent state.

    Fail-closed: if the channel key is missing from the consent dict, or if
    the status is UNKNOWN or OPTED_OUT, the channel is blocked.

    Args:
        channel_consent: Mapping of channel names to ConsentStatus values.
        channel: The channel to check (e.g., "WHATSAPP", "SMS", "PAYMENT_LINK").

    Returns:
        bool: True only if the customer has explicitly OPTED_IN for this channel.
    """
    status = channel_consent.get(channel, ConsentStatus.UNKNOWN)
    return status == ConsentStatus.OPTED_IN
