import type { ReactNode } from 'react'

/** The one pill shape used everywhere a status, risk level, or mode is
 * shown. Badge itself carries no color logic — the specific tone
 * (CASE_STATUS_STYLES, RISK_LEVEL_STYLES, etc. in lib/theme.ts) is
 * passed in as `className`, because the meaning of each tone is
 * screen-specific, but the shape and the "text is mandatory, not
 * optional" rule are not. `children` is required: a badge with no
 * readable text — color alone — isn't a badge here, it's a bug. Every
 * badge in this app is a real state word (OPEN, HIGH, Auto-approved),
 * which is exactly what keeps it legible with the color stripped out. */
export function Badge({ children, className = '' }: { children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center whitespace-nowrap rounded-full border px-2.5 py-0.5 text-xs font-medium ${className}`}>
      {children}
    </span>
  )
}
