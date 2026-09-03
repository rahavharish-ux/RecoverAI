/** Centralized semantic-state → style mappings, reused everywhere a case
 * status, risk level, decision status, or agent mode is rendered — so the
 * meaning of a color stays consistent across every view rather than being
 * redecided per component. See src/index.css for the underlying tokens. */

export const BADGE_BASE = "rounded-full border px-2.5 py-0.5 text-xs font-medium"

export const CASE_STATUS_STYLES: Record<string, string> = {
  open: "border-brand/30 bg-brand/10 text-brand",
  escalated: "border-danger/30 bg-danger/10 text-danger",
  resolved: "border-success/30 bg-success/10 text-success",
}

export const RISK_LEVEL_STYLES: Record<string, string> = {
  low: "border-line-strong bg-surface-2 text-muted",
  medium: "border-warning/30 bg-warning/10 text-warning",
  high: "border-danger/30 bg-danger/10 text-danger",
}

export const DECISION_STATUS_STYLES: Record<string, string> = {
  auto_approved: "border-brand/30 bg-brand/10 text-brand",
  executed: "border-success/30 bg-success/10 text-success",
  human_review: "border-danger/30 bg-danger/10 text-danger",
  rejected: "border-danger/30 bg-danger/10 text-danger",
  escalated: "border-danger/30 bg-danger/10 text-danger",
}

/** Same semantics as DECISION_STATUS_STYLES, text color only — for plain
 * table cells that don't need the full badge chrome. */
export const DECISION_STATUS_TEXT: Record<string, string> = {
  auto_approved: "text-brand",
  executed: "text-success",
  human_review: "text-danger",
  rejected: "text-danger",
  escalated: "text-danger",
}

export const MODE_BADGE_STYLES: Record<string, string> = {
  llm: "border-ai/30 bg-ai/10 text-ai",
  deterministic: "border-line-strong bg-surface-2 text-muted",
}

export const CONFIDENCE_BAND_STYLES: Record<string, string> = {
  high: "text-success",
  medium: "text-warning",
  low: "text-muted",
}

/** Fraud and hard-blocking conditions read as danger (red); everything
 * else that merely elevates a case for review reads as caution (amber) —
 * matching "red for fraud/HITL/blocking, amber for at-risk/warnings". */
const BLOCKING_RISK_FLAGS = new Set([
  "fraud_signal",
  "no_allowed_actions",
  "max_decisions_reached",
  "invalid_provider_selection",
])

export function riskFlagTone(flag: string): "danger" | "warning" {
  return BLOCKING_RISK_FLAGS.has(flag) ? "danger" : "warning"
}

export const RISK_FLAG_STYLES: Record<"danger" | "warning", string> = {
  danger: "border-danger/30 bg-danger/10 text-danger",
  warning: "border-warning/30 bg-warning/10 text-warning",
}
