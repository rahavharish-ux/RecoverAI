import { DecisionsTable } from './dashboard/DecisionsTable'
import { EconomicsSection } from './dashboard/EconomicsSection'
import { FailureIntelligence } from './dashboard/FailureIntelligence'
import { KpiCards } from './dashboard/KpiCards'
import { ModelHealthCard } from './dashboard/ModelHealthCard'
import { PriorityQueue } from './dashboard/PriorityQueue'
import { RecoveryFunnel } from './dashboard/RecoveryFunnel'
import { RevenueAtRiskHero } from './dashboard/RevenueAtRiskHero'

export function Dashboard({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-ink sm:text-3xl">Overview</h1>
        <p className="mt-1 text-sm text-muted">Detect-to-Measure pipeline status across every open recovery case.</p>
      </header>

      <RevenueAtRiskHero />

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
