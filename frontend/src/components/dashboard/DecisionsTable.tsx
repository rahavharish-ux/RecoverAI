import { getRecentDecisions } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, formatPercent, titleCase } from '../../lib/format'
import { DECISION_STATUS_TEXT } from '../../lib/theme'
import { Card } from '../ui/Card'
import { ModeBadge } from '../ui/ModeBadge'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../ui/Table'

export function DecisionsTable({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const { data, loading, error } = useFetch(() => getRecentDecisions(15), [])

  return (
    <Card eyebrow="Decide" title="AI Recovery Decisions">
      {loading && <LoadingState label="Loading decisions…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && (
        <EmptyState message="No agent decisions yet." action={{ label: 'Run a scenario from the Demo Center' }} />
      )}
      {data && data.length > 0 && (
        <Table>
          <TableHead>
            <TableHeaderCell>Case</TableHeaderCell>
            <TableHeaderCell align="right">Amount at Risk</TableHeaderCell>
            <TableHeaderCell>Failure</TableHeaderCell>
            <TableHeaderCell align="right">Probability</TableHeaderCell>
            <TableHeaderCell>Selected Action</TableHeaderCell>
            <TableHeaderCell align="right">Expected Value</TableHeaderCell>
            <TableHeaderCell>Engine</TableHeaderCell>
            <TableHeaderCell>Status</TableHeaderCell>
          </TableHead>
          <TableBody>
            {data.map((d) => (
              <TableRow key={d.decision_id} onClick={() => onOpenCase(d.case_id)} ariaLabel={`Open case ${d.case_id}`}>
                <TableCell className="font-medium text-brand">#{d.case_id}</TableCell>
                <TableCell align="right" className="text-muted">{formatMoney(d.amount_at_risk_cents)}</TableCell>
                <TableCell className="text-muted">{d.decline_code ? titleCase(d.decline_code) : '—'}</TableCell>
                <TableCell align="right" className="text-muted">{formatPercent(d.recovery_probability)}</TableCell>
                <TableCell className="text-ink">{d.selected_action ? titleCase(d.selected_action) : 'No action'}</TableCell>
                <TableCell align="right" className="text-muted">
                  {d.expected_value_cents !== null ? formatMoney(d.expected_value_cents) : '—'}
                </TableCell>
                <TableCell>
                  <ModeBadge agentMode={d.agent_mode} label={d.mode_label} />
                </TableCell>
                <TableCell className={`font-medium ${DECISION_STATUS_TEXT[d.status] ?? 'text-muted'}`}>{titleCase(d.status)}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  )
}
