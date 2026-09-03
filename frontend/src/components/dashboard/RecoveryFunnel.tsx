import { getRecoveryFunnel } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'

const STAGE_LABELS: Record<string, string> = {
  failed_payment: 'Failed Payment',
  diagnosed: 'Diagnosed',
  predicted: 'Predicted',
  policy_eligible: 'Policy Eligible',
  agent_decision: 'Agent Decision',
  recovery_action: 'Recovery Action',
  recovered: 'Recovered',
}

export function RecoveryFunnel() {
  const { data, loading, error } = useFetch(getRecoveryFunnel, [])

  return (
    <Card eyebrow="Pipeline" title="Recovery Funnel">
      {loading && <LoadingState label="Loading funnel…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && <EmptyState message="No cases yet." />}
      {data && data.length > 0 && (
        <div className="space-y-2">
          {data.map((stage) => (
            <div key={stage.stage} className="flex items-center gap-3">
              <span className="w-32 shrink-0 text-xs text-slate-400">{STAGE_LABELS[stage.stage] ?? titleCase(stage.stage)}</span>
              <div className="h-6 flex-1 overflow-hidden rounded bg-slate-800">
                <div
                  className="h-full rounded bg-gradient-to-r from-violet-600 to-violet-400 transition-[width] duration-500"
                  style={{ width: `${Math.max(stage.pct_of_failed, stage.case_count > 0 ? 4 : 0)}%` }}
                />
              </div>
              <span className="w-20 shrink-0 text-right text-xs tabular-nums text-slate-400">
                {stage.case_count} <span className="text-slate-600">({stage.pct_of_failed.toFixed(0)}%)</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </Card>
  )
}
