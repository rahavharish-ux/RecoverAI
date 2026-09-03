from app.domain.enums import DeclineCode
from app.integrations.payment_gateway import PaymentSimulatorAdapter


def test_deterministic_with_a_fixed_seed():
    a = PaymentSimulatorAdapter({"card_declined": 0.5}, seed=42)
    b = PaymentSimulatorAdapter({"card_declined": 0.5}, seed=42)
    outcomes_a = [
        a.retry_charge(decline_code=DeclineCode.CARD_DECLINED, amount_cents=1000, currency="usd").succeeded
        for _ in range(30)
    ]
    outcomes_b = [
        b.retry_charge(decline_code=DeclineCode.CARD_DECLINED, amount_cents=1000, currency="usd").succeeded
        for _ in range(30)
    ]
    assert outcomes_a == outcomes_b


def test_zero_success_rate_never_succeeds():
    sim = PaymentSimulatorAdapter({"card_declined": 0.0}, seed=1)
    for _ in range(50):
        result = sim.retry_charge(decline_code=DeclineCode.CARD_DECLINED, amount_cents=1000, currency="usd")
        assert result.succeeded is False
        assert result.decline_code == DeclineCode.CARD_DECLINED


def test_full_success_rate_always_succeeds():
    sim = PaymentSimulatorAdapter({"card_declined": 1.0}, seed=1)
    for _ in range(50):
        result = sim.retry_charge(decline_code=DeclineCode.CARD_DECLINED, amount_cents=1000, currency="usd")
        assert result.succeeded is True
        assert result.decline_code is None


def test_unconfigured_decline_code_defaults_to_never_succeeding():
    sim = PaymentSimulatorAdapter({}, seed=1)
    result = sim.retry_charge(decline_code=DeclineCode.PROCESSOR_ERROR, amount_cents=1000, currency="usd")
    assert result.succeeded is False


def test_result_is_always_tagged_simulated():
    sim = PaymentSimulatorAdapter({"card_declined": 1.0}, seed=1)
    result = sim.retry_charge(decline_code=DeclineCode.CARD_DECLINED, amount_cents=1000, currency="usd")
    assert result.is_simulated is True
