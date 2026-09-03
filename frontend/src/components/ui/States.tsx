export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-2 py-6 text-sm text-slate-500">
      <span className="h-3 w-3 animate-pulse rounded-full bg-violet-500/60" />
      {label}
    </div>
  )
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div role="alert" className="rounded-lg border border-rose-500/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-300">
      {message}
    </div>
  )
}

export function EmptyState({ message }: { message: string }) {
  return <p className="py-6 text-sm text-slate-500">{message}</p>
}
