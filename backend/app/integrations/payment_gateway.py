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


class DemoFixtureGatewayAdapter(PaymentGatewayPort):
    """A demo-only wrapper around a real `PaymentGatewayPort`. Used
    exclusively by the Demo Center orchestration (see
    app/services/demo_service.py) to guarantee a deterministic, clearly
    labeled outcome for ONE illustrative scenario ("Successful Recovery").

    This class is never returned by `app/api/deps.py::get_payment_gateway`
    — the dependency every production/API code path uses — so it changes
    nothing about real traffic or the configured success-rate behavior.
    When `forced_result` is None (every non-demo-fixture call, including
    every other Demo Center scenario), every call passes straight through
    to the wrapped real gateway unchanged."""

    def __init__(self, real_gateway: PaymentGatewayPort, forced_result: GatewayResult | None = None) -> None:
        self._real_gateway = real_gateway
        self._forced_result = forced_result

    def retry_charge(self, *, decline_code: DeclineCode, amount_cents: int, currency: str) -> GatewayResult:
        if self._forced_result is not None:
            return self._forced_result
        return self._real_gateway.retry_charge(decline_code=decline_code, amount_cents=amount_cents, currency=currency)
