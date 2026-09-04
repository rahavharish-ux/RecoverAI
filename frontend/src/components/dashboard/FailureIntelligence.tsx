import { getFailureCategories } from '../../api/dashboard'
import { useFetch } from '../../hooks/useFetch'
import { formatMoney, titleCase } from '../../lib/format'
import { Card } from '../ui/Card'
import { EmptyState, ErrorState, LoadingState } from '../ui/States'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from '../ui/Table'

export function FailureIntelligence() {
  const { data, loading, error } = useFetch(getFailureCategories, [])

  return (
    <Card eyebrow="Diagnose" title="Failure Intelligence">
      {loading && <LoadingState label="Loading failure categories…" />}
      {error && <ErrorState message={error} />}
      {data && data.length === 0 && (
        <EmptyState message="No diagnosed failures yet." action={{ label: 'Run a scenario from the Demo Center' }} />
      )}
      {data && data.length > 0 && (
        <Table>
          <TableHead>
            <TableHeaderCell>Category</TableHeaderCell>
            <TableHeaderCell align="right">Cases</TableHeaderCell>
            <TableHeaderCell align="right">Amount at Risk</TableHeaderCell>
            <TableHeaderCell align="center">Retry Eligible</TableHeaderCell>
            <TableHeaderCell align="right">Recovered</TableHeaderCell>
            <TableHeaderCell align="right">Escalated</TableHeaderCell>
          </TableHead>
          <TableBody>
            {data.map((c) => (
              <TableRow key={c.decline_code}>
                <TableCell>
                  <p className="font-medium text-ink">{titleCase(c.decline_code)}</p>
                  <p className="text-xs text-faint">{c.decline_class}</p>
                </TableCell>
                <TableCell align="right" className="text-muted">{c.case_count}</TableCell>
                <TableCell align="right" className="text-muted">{formatMoney(c.amount_involved_cents)}</TableCell>
                <TableCell align="center">
                  <span className={c.retry_eligible ? 'text-success' : 'text-faint'}>{c.retry_eligible ? '✓' : '—'}</span>
                </TableCell>
                <TableCell align="right" className="text-success">{c.resolved_count}</TableCell>
                <TableCell align="right" className="text-danger">{c.escalated_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
    </Card>
  )
}
