import type { ReactNode } from 'react'

export function Card({
  title,
  eyebrow,
  action,
  children,
  className = '',
}: {
  title?: string
  eyebrow?: string
  action?: ReactNode
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-xl border border-slate-800 bg-slate-900/60 p-5 ${className}`}>
      {(title ?? eyebrow) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            {eyebrow && <p className="text-xs uppercase tracking-wide text-slate-500">{eyebrow}</p>}
            {title && <h2 className="text-sm font-semibold text-slate-200">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
