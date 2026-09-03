import { DecisionsTable } from './dashboard/DecisionsTable'
import { EconomicsSection } from './dashboard/EconomicsSection'
import { FailureIntelligence } from './dashboard/FailureIntelligence'
import { KpiCards } from './dashboard/KpiCards'
import { ModelHealthCard } from './dashboard/ModelHealthCard'
import { PriorityQueue } from './dashboard/PriorityQueue'
import { RecoveryFunnel } from './dashboard/RecoveryFunnel'

export function Dashboard({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-400">RecoverAI</p>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-100">Agentic Revenue Recovery Intelligence</h1>
      </header>

      <KpiCards />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <RecoveryFunnel />
        </div>
        <ModelHealthCard />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <FailureIntelligence />
        <PriorityQueue onOpenCase={onOpenCase} />
      </div>

      <DecisionsTable onOpenCase={onOpenCase} />

      <EconomicsSection />
    </div>
  )
}
