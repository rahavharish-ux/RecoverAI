import type { ReactNode } from 'react'

export type View = 'dashboard' | 'cases' | 'case-intelligence' | 'agent-activity' | 'model-intelligence' | 'demo-center'

const NAV_ITEMS: { view: View; label: string }[] = [
  { view: 'dashboard', label: 'Dashboard' },
  { view: 'cases', label: 'Cases' },
  { view: 'case-intelligence', label: 'Case Intelligence' },
  { view: 'agent-activity', label: 'Agent Activity' },
  { view: 'model-intelligence', label: 'Model Intelligence' },
  { view: 'demo-center', label: 'Demo Center' },
]

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
    <div className="min-h-svh bg-slate-950 text-slate-100 lg:flex">
      <nav className="border-b border-slate-800 bg-slate-900/40 px-4 py-3 lg:w-56 lg:shrink-0 lg:border-b-0 lg:border-r lg:px-3 lg:py-6">
        <div className="mb-4 hidden lg:block lg:px-2">
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">RecoverAI</p>
        </div>
        <ul className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
          {NAV_ITEMS.map((item) => (
            <li key={item.view} className="shrink-0 lg:shrink">
              <button
                type="button"
                onClick={() => onNavigate(item.view)}
                aria-current={view === item.view ? 'page' : undefined}
                className={`w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-violet-500 ${
                  view === item.view
                    ? 'bg-violet-500/15 text-violet-300'
                    : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200'
                }`}
              >
                {item.label}
              </button>
            </li>
          ))}
        </ul>
      </nav>
      <main className="flex-1 px-4 py-6 lg:px-8 lg:py-8">
        <div className="mx-auto max-w-6xl">{children}</div>
      </main>
    </div>
  )
}
