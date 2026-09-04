import type { ReactNode } from 'react'
import { META_LABEL_CLASS } from '../../lib/theme'

type CardVariant = 'default' | 'raised'

const VARIANT_CLASS: Record<CardVariant, string> = {
  // Every ordinary card on a screen — quiet, on the `surface` step.
  default: 'border-line bg-surface p-4',
  // The ONE hero element per screen. Never stack more than one of these
  // on a page — that's the whole point of it being a variant instead of
  // a className escape hatch: there's exactly one way to say "this is
  // the thing that matters most right now," so it can't be improvised
  // per caller into three different-looking "important" boxes. A touch
  // more breathing room (24px vs. 16px) is the only other difference.
  raised: 'border-line-strong bg-surface-raised p-6',
}

export function Card({
  title,
  eyebrow,
  action,
  variant = 'default',
  children,
  className = '',
}: {
  title?: string
  eyebrow?: string
  action?: ReactNode
  variant?: CardVariant
  children: ReactNode
  className?: string
}) {
  return (
    <section className={`rounded-md border transition-colors duration-150 ${VARIANT_CLASS[variant]} ${className}`}>
      {(title ?? eyebrow) && (
        <div className="mb-3 flex items-center justify-between gap-3">
          <div>
            {eyebrow && <p className={META_LABEL_CLASS}>{eyebrow}</p>}
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  )
}
