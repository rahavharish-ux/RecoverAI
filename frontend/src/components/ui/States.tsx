export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 py-6 text-sm text-muted">
      <span className="h-2 w-2 animate-pulse rounded-full bg-brand" />
      {label}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-md border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
      {message}
    </div>
  )
}

interface EmptyStateAction {
  label: string
  onClick?: () => void
}

/** `action` is required, not optional — an empty state that's just a
 * sentence tells someone nothing happened without telling them what to
 * do about it. If there's a real handler (`onClick`), it renders as a
 * small button; if the next step lives on another screen this component
 * has no navigation handle to reach (e.g. "run a scenario from the Demo
 * Center"), it still renders as a distinct, clearly-marked next-step
 * line — never silently dropped. */
export function EmptyState({ message, action }: { message: string; action: EmptyStateAction }) {
  return (
    <div className="py-6 text-center text-sm">
      <p className="text-faint">{message}</p>
      {action.onClick ? (
        <button
          type="button"
          onClick={action.onClick}
          className="mt-3 rounded-md border border-line-strong px-3 py-1.5 text-xs font-medium text-ink transition-colors duration-150 hover:bg-surface-hover"
        >
          {action.label}
        </button>
      ) : (
        <p className="mt-1.5 text-xs font-medium text-brand">{action.label}</p>
      )}
    </div>
  )
}

/** A card-shaped loading placeholder — matches Card's own padding/border
 * so the layout doesn't jump when real content replaces it. `lines`
 * controls how many content rows it implies; never a spinner. */
export function CardSkeleton({ lines = 3 }: { lines?: number }) {
  return (
    <div className="animate-pulse space-y-3" role="status" aria-label="Loading">
      <div className="h-3 w-24 rounded bg-surface-2" />
      <div className="h-4 w-40 rounded bg-surface-2" />
      <div className="space-y-2 pt-1">
        {Array.from({ length: lines }).map((_, i) => (
          <div key={i} className="h-3 rounded bg-surface-2" style={{ width: `${85 - i * 12}%` }} />
        ))}
      </div>
    </div>
  )
}

/** A table-shaped loading placeholder — real rows and columns, sized
 * like the real table's header + body, not a generic bar. */
export function TableSkeleton({ rows = 5, columns = 4 }: { rows?: number; columns?: number }) {
  return (
    <div className="animate-pulse" role="status" aria-label="Loading">
      <div className="flex gap-4 border-b border-line pb-2">
        {Array.from({ length: columns }).map((_, c) => (
          <div key={c} className="h-3 flex-1 rounded bg-surface-2" />
        ))}
      </div>
      <div className="divide-y divide-line">
        {Array.from({ length: rows }).map((_, r) => (
          <div key={r} className="flex gap-4 py-3">
            {Array.from({ length: columns }).map((_, c) => (
              <div key={c} className="h-3 flex-1 rounded bg-surface-2" style={{ opacity: 1 - c * 0.12 }} />
            ))}
          </div>
        ))}
      </div>
    </div>
  )
}
