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
    <section
      className={`rounded-lg border border-line bg-surface p-5 transition-colors duration-150 ${className}`}
    >
      {(title ?? eyebrow) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            {eyebrow && <p className="text-[11px] font-medium uppercase tracking-wide text-faint">{eyebrow}</p>}
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
