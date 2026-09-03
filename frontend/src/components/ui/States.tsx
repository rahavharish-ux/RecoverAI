/** The "thinking" state — a slow, deliberate pulse (not a spinner), used
 * whenever a view is waiting on a real backend response. Respects
 * prefers-reduced-motion globally (see src/index.css). */
export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2.5 py-6 text-sm text-muted">
      <span className="h-2 w-2 animate-pulse rounded-full bg-ai" />
      {label}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-danger/30 bg-danger/10 px-4 py-3 text-sm text-danger">
      {message}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <p className="py-6 text-sm text-faint">{message}</p>
}
