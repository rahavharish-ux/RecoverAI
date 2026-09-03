import { MODE_BADGE_STYLES } from '../../lib/theme'

/** Renders whichever label the backend sent verbatim — never re-derives or
 * guesses it, so a deterministic decision can never be styled or worded
 * to look like LLM output. The AI-indigo treatment is reserved for this
 * badge alone when agentMode is "llm" — it never appears elsewhere. */
export function ModeBadge({ agentMode, label }: { agentMode: string; label: string }) {
  return (
    <span
      className={`whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        MODE_BADGE_STYLES[agentMode] ?? MODE_BADGE_STYLES.deterministic
      }`}
    >
      {label}
    </span>
  )
}
