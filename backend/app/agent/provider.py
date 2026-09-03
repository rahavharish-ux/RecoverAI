from abc import ABC, abstractmethod

from app.agent.types import DecisionContext, ProviderDecision, ToolContext


class AgentProviderError(Exception):
    """Raised when a provider fails to produce a usable decision — malformed
    output, a network/API failure, or a selected_action outside the allowed
    set. The caller (app/services/agent_service.py) catches this and falls
    back to the deterministic engine; it is never propagated as a 500."""


class AgentProvider(ABC):
    name: str
    mode: str  # "deterministic" | "llm" — see app.domain.enums.AgentMode

    @abstractmethod
    def generate_decision(self, context: DecisionContext, tool_context: ToolContext) -> ProviderDecision:
        """Must return a ProviderDecision whose selected_action is either
        None or one of context.action_types(). `tool_context` is provided
        so an LLM-backed provider can execute the agent's read tools
        (app/agent/tools.py) during its own reasoning; the deterministic
        engine ignores it entirely. The caller re-validates the result
        regardless of which provider produced it."""
