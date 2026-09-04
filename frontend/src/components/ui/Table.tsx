import type { KeyboardEvent, ReactNode } from 'react'
import { META_LABEL_CLASS } from '../../lib/theme'

/** Table is deliberately bare — no border, no background, no card shape
 * of its own. Wrap it in <Card> where a table is one piece of supporting
 * content among several (Failure Intelligence, AI Recovery Decisions);
 * leave it bare where the table IS the screen (Recovery Cases). The
 * primitive doesn't decide that for you — the caller does, by whether it
 * reaches for <Card> or not. */
export function Table({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <div className="overflow-x-auto">
      <table className={`w-full text-left text-sm ${className}`}>{children}</table>
    </div>
  )
}

export function TableHead({ children }: { children: ReactNode }) {
  return (
    <thead>
      <tr className="border-b border-line">{children}</tr>
    </thead>
  )
}

type Align = 'left' | 'right' | 'center'

const ALIGN_CLASS: Record<Align, string> = {
  left: 'text-left',
  right: 'text-right',
  center: 'text-center',
}

export function TableHeaderCell({ children, align = 'left' }: { children: ReactNode; align?: Align }) {
  return <th className={`pb-2 pr-4 font-medium last:pr-0 ${META_LABEL_CLASS} ${ALIGN_CLASS[align]}`}>{children}</th>
}

export function TableBody({ children }: { children: ReactNode }) {
  return <tbody className="divide-y divide-line">{children}</tbody>
}

/** Row click/keyboard-activation semantics defined once — every table
 * that lets you open a case was re-implementing this identically. */
export function TableRow({
  children,
  onClick,
  ariaLabel,
  className = '',
}: {
  children: ReactNode
  onClick?: () => void
  ariaLabel?: string
  className?: string
}) {
  if (!onClick) {
    return <tr className={className}>{children}</tr>
  }
  const handleKeyDown = (e: KeyboardEvent<HTMLTableRowElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      onClick()
    }
  }
  return (
    <tr
      role="button"
      tabIndex={0}
      aria-label={ariaLabel}
      onClick={onClick}
      onKeyDown={handleKeyDown}
      className={`cursor-pointer transition-colors duration-150 hover:bg-surface-hover focus-visible:bg-surface-hover ${className}`}
    >
      {children}
    </tr>
  )
}

export function TableCell({
  children,
  align = 'left',
  className = '',
}: {
  children: ReactNode
  align?: Align
  className?: string
}) {
  const numeric = align === 'right' ? 'tabular-nums' : ''
  return <td className={`py-2.5 pr-4 last:pr-0 ${ALIGN_CLASS[align]} ${numeric} ${className}`}>{children}</td>
}
