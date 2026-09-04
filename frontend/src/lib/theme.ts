/** Centralized semantic-state → style mappings, reused everywhere a case
 * status, risk level, decision status, or agent mode is rendered — so the
 * meaning of a color stays consistent across every view rather than being
 * redecided per component. See src/index.css for the underlying tokens
 * and DESIGN.md for the reasoning. */

export const BADGE_BASE = "rounded-full border px-2.5 py-0.5 text-xs font-medium"

/** The shared "quiet label above something" treatment: 12px/500/
 * text-faint, sentence case, normal tracking — deliberately quieter than
 * an H2 (14px/600) and no longer uppercase-tracked. Used for both Table
 * column headers and Card eyebrows: a table header labels data, a card
 * eyebrow labels a section, but they're the same typographic role and
 * were previously the same undifferentiated ALL-CAPS treatment applied
 * to four unrelated content types (see DESIGN.md). This is the one place
 * that treatment survives, deliberately reduced to these two uses. */
export const META_LABEL_CLASS = "text-xs font-medium text-faint"

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

export const DECISION_STATUS_TEXT: Record<string, string> = {
  auto_approved: "text-brand",
  executed: "text-success",
  human_review: "text-danger",
  rejected: "text-danger",
  escalated: "text-danger",
}

/** LLM vs. deterministic is signaled by the label text alone (rendered
 * verbatim from the backend, e.g. "Agentic AI Decision Engine" vs.
 * "Deterministic Decision Engine") — never by a dedicated hue. The only
 * difference here is weight: the LLM badge reads with slightly more
 * emphasis (it's the less predictable path, worth a second look), not a
 * different color family. There is no "AI purple" in this system. */
export const MODE_BADGE_STYLES: Record<string, string> = {
  llm: "border-line-strong bg-surface-2 text-ink font-semibold",
  deterministic: "border-line-strong bg-surface-2 text-muted",
}

export const CONFIDENCE_BAND_STYLES: Record<string, string> = {
  high: "text-success",
  medium: "text-warning",
  low: "text-muted",
}

/** Neutral badge for classification/meta tags that aren't a money or
 * decision state (e.g. Demo Center's scenario category tags). Money
 * states get color; everything else — including "pending," which is the
 * absence of an assigned state — stays quiet and neutral, distinguished
 * by text alone. */
export const NEUTRAL_TAG_STYLES = "border-line-strong bg-surface-2 text-muted"

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
