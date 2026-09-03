"""Tests the LLM-backed provider's request/response handling and its
bounded tool-use loop entirely against a mocked HTTP transport — no
network call, no API key, ever, in this test file. Live behavior against
the real Anthropic API is documented as not exercised in this environment
(see the final report); what's verified here is that the provider builds
correct requests, handles well-formed and malformed responses correctly,
and never lets a bad response through as a usable decision."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from app.agent.anthropic_provider import AnthropicAgentProvider
from app.agent.provider import AgentProviderError
from app.agent.types import AvailableAction, DecisionContext, ToolContext


def make_context(**overrides) -> DecisionContext:
    defaults = dict(
        case_id=1,
        case_status="open",
        amount_at_risk_cents=4900,
        currency="usd",
        decline_code="card_declined",
        decline_class="soft",
        diagnosis_explanation="test",
        recovery_probability=0.7,
        confidence_band="high",
        model_version="v1",
        top_contributions=[],
        customer_plan_tier="standard",
        customer_tenure_days=200.0,
        customer_prior_recovery_rate=0.6,
        prior_failed_attempts_on_case=0,
        executed_retry_count=0,
        policy_version="policy-v1",
        available_actions=[
            AvailableAction("retry_payment", "eligible", "ok", 3400),
            AvailableAction("escalate", "eligible", "ok", -500),
        ],
        generated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return DecisionContext(**defaults)


def _api_message(content_blocks: list[dict]) -> dict:
    return {"id": "msg_test", "type": "message", "role": "assistant", "content": content_blocks, "model": "test"}


def _submit_decision_block(**fields) -> dict:
    payload = {
        "selected_action": "retry_payment",
        "reasoning_summary": "Transient processor error, retry is policy-eligible and highest value.",
        "confidence": 0.8,
        "requires_human_review": False,
        "risk_flags": [],
    }
    payload.update(fields)
    return {"type": "tool_use", "id": "call_1", "name": "submit_decision", "input": payload}


def _make_provider(handler, max_tool_calls: int = 6) -> AnthropicAgentProvider:
    transport = httpx.MockTransport(handler)
    return AnthropicAgentProvider(
        api_key="fake-test-key",
        model="test-model",
        api_base="https://fake.invalid",
        timeout_seconds=5.0,
        max_tool_calls=max_tool_calls,
        http_client=httpx.Client(transport=transport),
    )


NULL_TOOL_CONTEXT = ToolContext(db=None, case=None)  # unused when the model decides immediately


def test_immediate_submit_decision_is_parsed():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_api_message([_submit_decision_block()]))

    provider = _make_provider(handler)
    decision = provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)
    assert decision.selected_action == "retry_payment"
    assert decision.confidence == 0.8


def test_request_includes_the_system_prompt_and_tools():
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["headers"] = dict(request.headers)
        return httpx.Response(200, json=_api_message([_submit_decision_block()]))

    provider = _make_provider(handler)
    provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)

    assert "system" in captured["body"]
    tool_names = {t["name"] for t in captured["body"]["tools"]}
    assert "submit_decision" in tool_names
    assert "get_transaction" in tool_names
    assert captured["headers"]["x-api-key"] == "fake-test-key"


def test_selecting_an_action_outside_the_allowed_set_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_api_message([_submit_decision_block(selected_action="request_method_update")]))

    provider = _make_provider(handler)
    # available_actions in make_context() only includes retry_payment and escalate
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_missing_required_field_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        block = _submit_decision_block()
        del block["input"]["confidence"]
        return httpx.Response(200, json=_api_message([block]))

    provider = _make_provider(handler)
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_confidence_out_of_range_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_api_message([_submit_decision_block(confidence=1.5)]))

    provider = _make_provider(handler)
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_no_tool_use_in_response_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_api_message([{"type": "text", "text": "I refuse to use tools."}]))

    provider = _make_provider(handler)
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_http_error_status_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid api key"})

    provider = _make_provider(handler)
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_network_failure_raises():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    provider = _make_provider(handler)
    with pytest.raises(AgentProviderError):
        provider.generate_decision(make_context(), NULL_TOOL_CONTEXT)


def test_loop_exhaustion_without_a_final_decision_raises(session_factory, seeded_invoice):
    """A model that keeps calling tools and never submits must be forced to
    stop, not loop forever — this is the hard cap on reasoning cycles."""
    from app.domain.enums import AttemptSource, DeclineCode
    from app.models.cases import Case
    from app.models.core import Invoice
    from app.services import ingestion_service

    db = session_factory()
    try:
        invoice = db.get(Invoice, seeded_invoice["invoice_id"])
        result = ingestion_service.record_payment_attempt(
            db,
            invoice=invoice,
            payment_method_id=seeded_invoice["payment_method_id"],
            amount_cents=4900,
            currency="usd",
            decline_code=DeclineCode.CARD_DECLINED,
            source=AttemptSource.EXTERNAL,
        )
        case = db.get(Case, result.case.id)

        call_count = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            call_count["n"] += 1
            # Always asks to read the transaction again, never submits.
            return httpx.Response(
                200,
                json=_api_message(
                    [{"type": "tool_use", "id": f"call_{call_count['n']}", "name": "get_transaction", "input": {}}]
                ),
            )

        provider = _make_provider(handler, max_tool_calls=3)
        with pytest.raises(AgentProviderError, match="Exceeded"):
            provider.generate_decision(make_context(), ToolContext(db=db, case=case))
        assert call_count["n"] == 3
    finally:
        db.close()


def test_unexpected_tool_failure_does_not_crash_the_loop(session_factory, seeded_invoice, monkeypatch):
    """A tool handler raising something other than ToolError must still be
    absorbed as a tool_result, never propagate and crash the provider."""
    from app.agent import tools as tools_module
    from app.domain.enums import AttemptSource, DeclineCode
    from app.models.cases import Case
    from app.models.core import Invoice
    from app.services import ingestion_service

    def _broken_handler(ctx, payload):
        raise RuntimeError("simulated unexpected failure")

    monkeypatch.setitem(
        tools_module.TOOL_REGISTRY,
        "get_customer_history",
        tools_module.TOOL_REGISTRY["get_customer_history"].__class__(
            name="get_customer_history",
            description="broken for this test",
            input_model=tools_module.EmptyInput,
            output_model=tools_module.CustomerHistoryOut,
            handler=_broken_handler,
            is_write=False,
        ),
    )

    db = session_factory()
    try:
        invoice = db.get(Invoice, seeded_invoice["invoice_id"])
        result = ingestion_service.record_payment_attempt(
            db,
            invoice=invoice,
            payment_method_id=seeded_invoice["payment_method_id"],
            amount_cents=4900,
            currency="usd",
            decline_code=DeclineCode.CARD_DECLINED,
            source=AttemptSource.EXTERNAL,
        )
        case = db.get(Case, result.case.id)

        turns = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            turns["n"] += 1
            if turns["n"] == 1:
                return httpx.Response(
                    200,
                    json=_api_message(
                        [{"type": "tool_use", "id": "call_1", "name": "get_customer_history", "input": {}}]
                    ),
                )
            return httpx.Response(200, json=_api_message([_submit_decision_block()]))

        provider = _make_provider(handler, max_tool_calls=5)
        decision = provider.generate_decision(make_context(), ToolContext(db=db, case=case))
        assert decision.selected_action == "retry_payment"
        assert turns["n"] == 2  # the broken tool call didn't stop the loop
    finally:
        db.close()


def test_read_tool_call_is_executed_then_decision_follows(session_factory, seeded_invoice):
    from app.domain.enums import AttemptSource, DeclineCode
    from app.models.cases import Case
    from app.models.core import Invoice
    from app.services import ingestion_service

    db = session_factory()
    try:
        invoice = db.get(Invoice, seeded_invoice["invoice_id"])
        result = ingestion_service.record_payment_attempt(
            db,
            invoice=invoice,
            payment_method_id=seeded_invoice["payment_method_id"],
            amount_cents=4900,
            currency="usd",
            decline_code=DeclineCode.CARD_DECLINED,
            source=AttemptSource.EXTERNAL,
        )
        case = db.get(Case, result.case.id)

        turns = {"n": 0}

        def handler(request: httpx.Request) -> httpx.Response:
            turns["n"] += 1
            if turns["n"] == 1:
                return httpx.Response(
                    200,
                    json=_api_message(
                        [{"type": "tool_use", "id": "call_1", "name": "get_transaction", "input": {}}]
                    ),
                )
            body = json.loads(request.content)
            # the tool result from turn 1 must be present in the conversation
            assert any(m["role"] == "user" and isinstance(m["content"], list) for m in body["messages"][1:])
            return httpx.Response(200, json=_api_message([_submit_decision_block()]))

        provider = _make_provider(handler, max_tool_calls=5)
        decision = provider.generate_decision(make_context(), ToolContext(db=db, case=case))
        assert decision.selected_action == "retry_payment"
        assert turns["n"] == 2
    finally:
        db.close()
