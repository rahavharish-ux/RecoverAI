const MODE_BADGE_STYLES: Record<string, string> = {
  llm: 'bg-violet-500/15 text-violet-300 border-violet-500/30',
  deterministic: 'bg-slate-500/15 text-slate-300 border-slate-500/30',
}

/** Renders whichever label the backend sent verbatim — never re-derives or
 * guesses it, so a deterministic decision can never be styled or worded
 * to look like LLM output. */
export function ModeBadge({ agentMode, label }: { agentMode: string; label: string }) {
  return (
    <span className={`rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap ${MODE_BADGE_STYLES[agentMode] ?? MODE_BADGE_STYLES.deterministic}`}>
      {label}
    </span>
  )
}
