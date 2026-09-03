import type { ReactNode } from 'react'

export type View = 'dashboard' | 'cases' | 'case-intelligence' | 'agent-activity' | 'model-intelligence' | 'demo-center'

const PRIMARY_NAV: { view: View; label: string; icon: ReactNode }[] = [
  { view: 'dashboard', label: 'Overview', icon: <IconGrid /> },
  { view: 'cases', label: 'Recovery Cases', icon: <IconLayers /> },
  { view: 'case-intelligence', label: 'Case Intelligence', icon: <IconSearch /> },
  { view: 'agent-activity', label: 'Agent Activity', icon: <IconPulse /> },
  { view: 'model-intelligence', label: 'Model Intelligence', icon: <IconChip /> },
]

const UTILITY_NAV: { view: View; label: string; icon: ReactNode }[] = [
  { view: 'demo-center', label: 'Demo Center', icon: <IconPlay /> },
]

function NavButton({
  item,
  active,
  onNavigate,
}: {
  item: { view: View; label: string; icon: ReactNode }
  active: boolean
  onNavigate: (view: View) => void
}) {
  return (
    <li className="shrink-0 lg:shrink">
      <button
        type="button"
        onClick={() => onNavigate(item.view)}
        aria-current={active ? 'page' : undefined}
        className={`flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm font-medium transition-colors duration-150 ${
          active ? 'bg-brand/10 text-brand' : 'text-muted hover:bg-surface-hover hover:text-ink'
        }`}
      >
        <span className={active ? 'text-brand' : 'text-faint'}>{item.icon}</span>
        <span className="truncate">{item.label}</span>
      </button>
    </li>
  )
}

export function Shell({
  view,
  onNavigate,
  children,
}: {
  view: View
  onNavigate: (view: View) => void
  children: ReactNode
}) {
  return (
    <div className="min-h-svh bg-canvas text-ink lg:flex">
      <nav className="flex flex-col border-b border-line bg-surface px-4 py-3 lg:h-svh lg:w-60 lg:shrink-0 lg:border-b-0 lg:border-r lg:px-3 lg:py-5">
        <div className="mb-5 hidden items-center gap-2 px-2 lg:flex">
          <RecoverAIGlyph />
          <div>
            <p className="text-sm font-bold leading-none tracking-tight text-ink">RECOVERAI</p>
            <p className="mt-1 text-[10px] font-medium uppercase leading-none tracking-[0.14em] text-faint">
              Revenue Intelligence
            </p>
          </div>
        </div>

        <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
          {PRIMARY_NAV.map((item) => (
            <NavButton key={item.view} item={item} active={view === item.view} onNavigate={onNavigate} />
          ))}
        </ul>

        <div className="hidden lg:mt-4 lg:block lg:border-t lg:border-line lg:pt-4">
          <ul className="flex flex-col gap-1">
            {UTILITY_NAV.map((item) => (
              <NavButton key={item.view} item={item} active={view === item.view} onNavigate={onNavigate} />
            ))}
          </ul>
        </div>

        <div className="hidden lg:mt-auto lg:block lg:pt-5">
          <div className="flex items-center gap-2 rounded-md border border-line bg-surface-2 px-3 py-2">
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-pulse rounded-full bg-warning" />
            </span>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-ink">Sandbox Environment</p>
              <p className="truncate text-[10px] text-faint">Simulated data · no live payments</p>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile: utility nav stays reachable below the primary row */}
      <ul className="flex gap-1 border-b border-line bg-surface px-4 py-2 lg:hidden">
        {UTILITY_NAV.map((item) => (
          <NavButton key={item.view} item={item} active={view === item.view} onNavigate={onNavigate} />
        ))}
      </ul>

      <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  )
}

/** A simple, distinct RecoverAI mark — a signal/pulse motif referencing
 * "detect a failure, recover it," not any third-party brand's glyph. */
function RecoverAIGlyph() {
  return (
    <svg width="22" height="22" viewBox="0 0 22 22" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="20" height="20" rx="6" className="fill-brand/15 stroke-brand/40" strokeWidth="1" />
      <path
        d="M5.5 12.5L8.5 9.5L10.5 12L16.5 6"
        stroke="currentColor"
        className="text-brand"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <path d="M13.5 6H16.5V9" stroke="currentColor" className="text-brand" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function IconGrid() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="1.5" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9" y="1.5" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <rect x="1.5" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <rect x="9" y="9" width="5.5" height="5.5" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  )
}

function IconLayers() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path d="M8 1.5L14.5 5L8 8.5L1.5 5L8 1.5Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      <path d="M1.5 8.5L8 12L14.5 8.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M1.5 11.5L8 15L14.5 11.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function IconSearch() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="7" cy="7" r="5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M10.8 10.8L14.5 14.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function IconPulse() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M1 8.5H4.5L6 4.5L9.5 12.5L11 8.5H15"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

function IconChip() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <rect x="4" y="4" width="8" height="8" rx="1.2" stroke="currentColor" strokeWidth="1.3" />
      <path d="M6.5 1.5V4M9.5 1.5V4M6.5 12V14.5M9.5 12V14.5M1.5 6.5H4M1.5 9.5H4M12 6.5H14.5M12 9.5H14.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" />
    </svg>
  )
}

function IconPlay() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.3" />
      <path d="M6.7 5.5L10.5 8L6.7 10.5V5.5Z" fill="currentColor" />
    </svg>
  )
}
