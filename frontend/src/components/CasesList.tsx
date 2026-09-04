import { useMemo, useState } from 'react'
import { listCases } from '../api/cases'
import { useFetch } from '../hooks/useFetch'
import { formatMoney } from '../lib/format'
import { CASE_STATUS_STYLES, META_LABEL_CLASS } from '../lib/theme'
import { Badge } from './ui/Badge'
import { Card } from './ui/Card'
import { EmptyState, ErrorState, LoadingState } from './ui/States'
import { Table, TableBody, TableCell, TableHead, TableHeaderCell, TableRow } from './ui/Table'
import type { CaseStatus } from '../types/case'

const FILTERS = ['all', 'open', 'escalated', 'resolved'] as const

function formatOpened(iso: string): string {
  return new Date(iso).toLocaleString('en-IN', { day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit' })
}

export function CasesList({ onOpenCase }: { onOpenCase: (caseId: number) => void }) {
  const [statusFilter, setStatusFilter] = useState<CaseStatus | 'all'>('all')
  // Fetched once, unfiltered: the summary strip and the table both derive
  // from this same real set, so the two can never drift out of sync with
  // each other or need a second round-trip per filter click.
  const { data, loading, error } = useFetch(() => listCases(), [])

  const filtered = useMemo(() => {
    if (!data) return null
    return statusFilter === 'all' ? data : data.filter((c) => c.status === statusFilter)
  }, [data, statusFilter])

  // Every figure here is a real aggregate over the same list rendered
  // below — "Revenue at Risk" mirrors Overview's own definition (open
  // cases only; a resolved case's amount_at_risk_cents is zeroed by the
  // backend on resolution, so summing it stays correct without excluding
  // resolved rows by hand).
  const summary = useMemo(() => {
    if (!data) return null
    return {
      active: data.filter((c) => c.status === 'open').length,
      revenueAtRiskCents: data.filter((c) => c.status === 'open').reduce((sum, c) => sum + c.amount_at_risk_cents, 0),
      escalated: data.filter((c) => c.status === 'escalated').length,
      resolved: data.filter((c) => c.status === 'resolved').length,
    }
  }, [data])

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-bold tracking-tight text-ink">Recovery Cases</h1>
        <p className="mt-0.5 text-sm text-muted">Every case Detect has opened, ranked by amount at risk.</p>
      </header>

      {summary && (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Card>
            <p className={META_LABEL_CLASS}>Active Cases</p>
            <p className="mt-1.5 text-2xl font-bold tabular-nums text-brand">{summary.active}</p>
          </Card>
          <Card>
            <p className={META_LABEL_CLASS}>Revenue at Risk</p>
            <p className="mt-1.5 text-xl font-bold tabular-nums text-warning sm:text-2xl">{formatMoney(summary.revenueAtRiskCents)}</p>
          </Card>
          <Card>
            <p className={META_LABEL_CLASS}>Escalated</p>
            <p className={`mt-1.5 text-2xl font-bold tabular-nums ${summary.escalated > 0 ? 'text-danger' : 'text-ink'}`}>
              {summary.escalated}
            </p>
          </Card>
          <Card>
            <p className={META_LABEL_CLASS}>Resolved</p>
            <p className="mt-1.5 text-2xl font-bold tabular-nums text-success">{summary.resolved}</p>
          </Card>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-1.5">
        {FILTERS.map((s) => (
          <button
            key={s}
            type="button"
            onClick={() => setStatusFilter(s)}
            aria-pressed={statusFilter === s}
            className={`rounded-full border px-3 py-1.5 text-xs font-medium capitalize transition-colors duration-150 ${
              statusFilter === s
                ? 'border-brand bg-brand/10 text-brand'
                : 'border-line-strong text-muted hover:bg-surface-hover hover:text-ink'
            }`}
          >
            {s}
          </button>
        ))}
      </div>

      {loading && (
        <Card>
          <LoadingState label="Loading cases…" />
        </Card>
      )}
      {error && (
        <Card>
          <ErrorState message={error} />
        </Card>
      )}
      {filtered && filtered.length === 0 && (
        <Card>
          <EmptyState
            message={statusFilter === 'all' ? 'No cases yet.' : `No ${statusFilter} cases.`}
            action={
              statusFilter === 'all'
                ? { label: 'Run a scenario from the Demo Center' }
                : { label: 'Clear filter', onClick: () => setStatusFilter('all') }
            }
          />
        </Card>
      )}

      {/* Bare — no Card wrapper. This table is the screen, not content
          inside a box (see ui/Table.tsx). */}
      {filtered && filtered.length > 0 && (
        <div className="border-t border-line">
          <Table>
            <TableHead>
              <TableHeaderCell>Case</TableHeaderCell>
              <TableHeaderCell align="right">Amount at Risk</TableHeaderCell>
              <TableHeaderCell align="right">Recovered</TableHeaderCell>
              <TableHeaderCell>Status</TableHeaderCell>
              <TableHeaderCell>Opened</TableHeaderCell>
            </TableHead>
            <TableBody>
              {filtered.map((c) => (
                <TableRow key={c.id} onClick={() => onOpenCase(c.id)} ariaLabel={`Open case ${c.id}`}>
                  <TableCell className="font-medium text-brand">#{c.id}</TableCell>
                  <TableCell align="right" className="text-ink">{formatMoney(c.amount_at_risk_cents)}</TableCell>
                  <TableCell align="right" className="text-muted">{formatMoney(c.amount_recovered_cents)}</TableCell>
                  <TableCell>
                    <Badge className={CASE_STATUS_STYLES[c.status]}>{c.status}</Badge>
                  </TableCell>
                  <TableCell className="text-faint">{formatOpened(c.opened_at)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {filtered && filtered.length > 0 && (
        <p className="text-xs text-faint">
          {filtered.length} of {data?.length ?? filtered.length} case(s) shown.
        </p>
      )}
    </div>
  )
}
