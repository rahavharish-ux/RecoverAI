from functools import lru_cache

from app.core.config import get_settings
from app.integrations.payment_gateway import PaymentGatewayPort, PaymentSimulatorAdapter


@lru_cache
def get_payment_gateway() -> PaymentGatewayPort:
    settings = get_settings()
    return PaymentSimulatorAdapter(
        success_rates=settings.simulator_retry_success_rates,
        seed=settings.simulator_random_seed,
    )
