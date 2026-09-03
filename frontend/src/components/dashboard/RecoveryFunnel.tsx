import { getRecoveryFunnel } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

const STAGE_LABELS: Record<string, string> = {
  failed_payment: 'Detect',
  diagnosed: 'Diagnose',
  predicted: 'Predict',
  policy_eligible: 'Policy Eligible',
  agent_decision: 'Decide',
  recovery_action: 'Act',
  recovered: 'Measure — Recovered',
}

export function RecoveryFunnel() {
  const { data, loading, error } = useFetch(getRecoveryFunnel, [])

  return (
    <Card eyebrow="Detect → Measure" title="Recovery Funnel">
      {loading && <LoadingState label="Loading funnel…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && <EmptyState message="No cases yet." />}
      {data && data.length > 0 && (
        <div className="space-y-2.5">
          {data.map((stage, i) => (
            <div key={stage.stage} className="flex items-center gap-3">
              <span className="w-8 shrink-0 font-mono text-[10px] text-faint">{String(i + 1).padStart(2, '0')}</span>
              <span className="w-36 shrink-0 text-xs font-medium text-muted">{STAGE_LABELS[stage.stage] ?? titleCase(stage.stage)}</span>
              <div className="h-5 flex-1 overflow-hidden rounded-sm bg-surface-2">
                <div
                  className="h-full rounded-sm bg-brand transition-[width] duration-500 ease-out"
                  style={{ width: `${Math.max(stage.pct_of_failed, stage.case_count > 0 ? 4 : 0)}%` }}
                />
              </div>
              <span className="w-24 shrink-0 text-right text-xs tabular-nums text-muted">
                {stage.case_count} <span className="text-faint">({stage.pct_of_failed.toFixed(0)}%)</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
