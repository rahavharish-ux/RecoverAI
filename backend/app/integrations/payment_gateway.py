"""The payment gateway boundary. `PaymentGatewayPort` is the contract a real
processor sandbox would implement later; `PaymentSimulatorAdapter` is the
only implementation in Phase 1, and every result it produces is tagged
`is_simulated=True` end to end.

The configured success rates are illustrative sandbox parameters (see
core/config.py) — they are not measurements, not validated against any real
population, and not a claim about how often recovery actually works. They
exist so the deterministic pipeline has something to execute against; a
model earns the right to influence a decision later, in Phase 2, only by
beating a baseline on held-out data (see the approved blueprint, §13/§17).
"""

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.domain.enums import DeclineCode


@dataclass(frozen=True)
class GatewayResult:
    succeeded: bool
    decline_code: DeclineCode | None
    is_simulated: bool = True


class PaymentGatewayPort(ABC):
    """Everything above this boundary must only ever depend on this
    interface, never on the simulator directly — swapping in a real sandbox
    later is an adapter change, not a rewrite."""

    @abstractmethod
    def retry_charge(self, *, decline_code: DeclineCode, amount_cents: int, currency: str) -> GatewayResult:
        """Attempt to collect payment again for a previously failed attempt.
        On failure, the same decline_code is returned — the underlying
        reason for the original decline hasn't changed just because a retry
        was attempted."""


class PaymentSimulatorAdapter(PaymentGatewayPort):
    def __init__(self, success_rates: dict[str, float], seed: int | None = None) -> None:
        self._success_rates = success_rates
        self._random = random.Random(seed)

    def retry_charge(self, *, decline_code: DeclineCode, amount_cents: int, currency: str) -> GatewayResult:
        success_rate = self._success_rates.get(decline_code.value, 0.0)
        succeeded = self._random.random() < success_rate
        return GatewayResult(succeeded=succeeded, decline_code=None if succeeded else decline_code)
