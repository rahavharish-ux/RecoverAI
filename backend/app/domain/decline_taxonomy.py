"""Deterministic decline classification — the Diagnose stage.

No model, no LLM: a fixed table mapping a gateway decline code to (a) its
risk class, which the policy gate branches on, and (b) which action types
are even conceptually relevant to it. A card that's simply expired can
never be fixed by blindly retrying the same card, no matter how confident
a model might be that "retrying usually works" — so that's encoded here,
not left for a probability threshold to (maybe) discover.
"""

from dataclasses import dataclass

from app.domain.enums import ActionType, DeclineClass, DeclineCode


@dataclass(frozen=True)
class DeclineProfile:
    decline_class: DeclineClass
    relevant_actions: frozenset[ActionType]
    explanation: str


_PROFILES: dict[DeclineCode, DeclineProfile] = {
    DeclineCode.INSUFFICIENT_FUNDS: DeclineProfile(
        decline_class=DeclineClass.SOFT,
        relevant_actions=frozenset({ActionType.RETRY_PAYMENT, ActionType.ESCALATE}),
        explanation="The card was valid but the account did not have enough funds at "
        "the time of the charge. The card itself is not the problem, so a payment "
        "method update is not offered — a later retry may succeed once funds are available.",
    ),
    DeclineCode.CARD_DECLINED: DeclineProfile(
        decline_class=DeclineClass.SOFT,
        relevant_actions=frozenset(
            {ActionType.RETRY_PAYMENT, ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE}
        ),
        explanation="A generic issuer decline with no specific reason surfaced. Both a "
        "retry and a method update are plausible fixes, so both remain on the table.",
    ),
    DeclineCode.PROCESSOR_ERROR: DeclineProfile(
        decline_class=DeclineClass.SOFT,
        relevant_actions=frozenset({ActionType.RETRY_PAYMENT, ActionType.ESCALATE}),
        explanation="The failure originated in the payment processor, not the "
        "customer's card — a transient error most likely to clear on its own retry.",
    ),
    DeclineCode.EXPIRED_CARD: DeclineProfile(
        decline_class=DeclineClass.SOFT,
        relevant_actions=frozenset({ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE}),
        explanation="The card has expired. Retrying the same card cannot succeed by "
        "construction — only collecting an updated payment method can resolve this.",
    ),
    DeclineCode.INVALID_METHOD: DeclineProfile(
        decline_class=DeclineClass.HARD,
        relevant_actions=frozenset({ActionType.REQUEST_METHOD_UPDATE, ActionType.ESCALATE}),
        explanation="The payment method itself is no longer valid (e.g. cancelled or "
        "malformed). Retrying it is pointless; the customer must supply a new method.",
    ),
    DeclineCode.DO_NOT_HONOR: DeclineProfile(
        decline_class=DeclineClass.HARD,
        relevant_actions=frozenset({ActionType.ESCALATE}),
        explanation="The issuing bank declined the charge outright with no reason "
        "disclosed. This is treated as a hard decline: no self-service fix is "
        "attempted automatically.",
    ),
    DeclineCode.FRAUD_SUSPECTED: DeclineProfile(
        decline_class=DeclineClass.FRAUD,
        relevant_actions=frozenset({ActionType.ESCALATE}),
        explanation="The gateway flagged this attempt as a suspected fraud signal. "
        "No automated recovery action is ever taken on a fraud signal — it is "
        "routed to a human immediately.",
    ),
}


@dataclass(frozen=True)
class Diagnosis:
    decline_code: DeclineCode
    decline_class: DeclineClass
    relevant_actions: frozenset[ActionType]
    explanation: str


def diagnose(decline_code: DeclineCode) -> Diagnosis:
    profile = _PROFILES[decline_code]
    return Diagnosis(
        decline_code=decline_code,
        decline_class=profile.decline_class,
        relevant_actions=profile.relevant_actions,
        explanation=profile.explanation,
    )
