import { useQuery } from '@tanstack/react-query'
import { RefreshCw } from 'lucide-react'
import { useMemo, useState } from 'react'
import { adminMtApi, type AggregateUserRow } from '@/api/adminMt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'

type AggType = 'funds' | 'positions' | 'orders'

const TITLES: Record<AggType, string> = {
  funds: 'Funds & Margins',
  positions: 'Positions',
  orders: 'Orders',
}

function fmtNum(v: unknown): string {
  const n = typeof v === 'number' ? v : Number(v)
  if (!Number.isFinite(n)) return String(v ?? '-')
  return n.toLocaleString('en-IN', { maximumFractionDigits: 2 })
}

// ---- Funds view --------------------------------------------------------------
const FUND_FIELDS: { key: string; label: string }[] = [
  { key: 'availablecash', label: 'Available Cash' },
  { key: 'collateral', label: 'Collateral' },
  { key: 'm2mrealized', label: 'M2M Realized' },
  { key: 'm2munrealized', label: 'M2M Unrealized' },
  { key: 'utiliseddebits', label: 'Utilised' },
]

function FundsTable({ rows }: { rows: AggregateUserRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>User</TableHead>
          <TableHead>Broker</TableHead>
          {FUND_FIELDS.map((f) => (
            <TableHead key={f.key} className="text-right">
              {f.label}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.map((r) => (
          <TableRow key={r.username}>
            <TableCell className="font-medium">{r.username}</TableCell>
            <TableCell>{r.broker || '-'}</TableCell>
            {r.error ? (
              <TableCell colSpan={FUND_FIELDS.length} className="text-destructive text-right">
                {r.error}
              </TableCell>
            ) : (
              FUND_FIELDS.map((f) => (
                <TableCell key={f.key} className="text-right">
                  {fmtNum(r.funds?.[f.key])}
                </TableCell>
              ))
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}

// ---- Positions view ----------------------------------------------------------
function PositionsTable({ rows }: { rows: AggregateUserRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>User</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Exchange</TableHead>
          <TableHead>Product</TableHead>
          <TableHead className="text-right">Qty</TableHead>
          <TableHead className="text-right">Avg Price</TableHead>
          <TableHead className="text-right">P&L</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.flatMap((r) => {
          if (r.error) {
            return [
              <TableRow key={r.username}>
                <TableCell className="font-medium">{r.username}</TableCell>
                <TableCell colSpan={6} className="text-destructive">
                  {r.error}
                </TableCell>
              </TableRow>,
            ]
          }
          const positions = r.positions || []
          if (positions.length === 0) {
            return [
              <TableRow key={r.username}>
                <TableCell className="font-medium">{r.username}</TableCell>
                <TableCell colSpan={6} className="text-muted-foreground">
                  No open positions
                </TableCell>
              </TableRow>,
            ]
          }
          return positions.map((p, i) => (
            <TableRow key={`${r.username}-${i}`}>
              <TableCell className="font-medium">{i === 0 ? r.username : ''}</TableCell>
              <TableCell>{String(p.symbol ?? '-')}</TableCell>
              <TableCell>{String(p.exchange ?? '-')}</TableCell>
              <TableCell>{String(p.product ?? '-')}</TableCell>
              <TableCell className="text-right">{fmtNum(p.quantity ?? p.netqty)}</TableCell>
              <TableCell className="text-right">{fmtNum(p.average_price ?? p.avgprice)}</TableCell>
              <TableCell className="text-right">{fmtNum(p.pnl ?? p.m2m)}</TableCell>
            </TableRow>
          ))
        })}
      </TableBody>
    </Table>
  )
}

// ---- Orders view -------------------------------------------------------------
function OrdersTable({ rows }: { rows: AggregateUserRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>User</TableHead>
          <TableHead>Symbol</TableHead>
          <TableHead>Action</TableHead>
          <TableHead className="text-right">Qty</TableHead>
          <TableHead className="text-right">Price</TableHead>
          <TableHead>Type</TableHead>
          <TableHead>Status</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {rows.flatMap((r) => {
          if (r.error) {
            return [
              <TableRow key={r.username}>
                <TableCell className="font-medium">{r.username}</TableCell>
                <TableCell colSpan={6} className="text-destructive">
                  {r.error}
                </TableCell>
              </TableRow>,
            ]
          }
          const orders = r.orders || []
          if (orders.length === 0) {
            return [
              <TableRow key={r.username}>
                <TableCell className="font-medium">{r.username}</TableCell>
                <TableCell colSpan={6} className="text-muted-foreground">
                  No orders
                </TableCell>
              </TableRow>,
            ]
          }
          return orders.map((o, i) => (
            <TableRow key={`${r.username}-${i}`}>
              <TableCell className="font-medium">{i === 0 ? r.username : ''}</TableCell>
              <TableCell>{String(o.symbol ?? '-')}</TableCell>
              <TableCell>{String(o.action ?? '-')}</TableCell>
              <TableCell className="text-right">{fmtNum(o.quantity)}</TableCell>
              <TableCell className="text-right">{fmtNum(o.price)}</TableCell>
              <TableCell>{String(o.pricetype ?? '-')}</TableCell>
              <TableCell>{String(o.order_status ?? o.status ?? '-')}</TableCell>
            </TableRow>
          ))
        })}
      </TableBody>
    </Table>
  )
}

interface AdminAggregateProps {
  type: AggType
}

export default function AdminAggregate({ type }: AdminAggregateProps) {
  const [selectedUser, setSelectedUser] = useState<string>('all')

  const query = useQuery({
    queryKey: ['admin-mt-aggregate', type],
    queryFn: () => {
      if (type === 'funds') return adminMtApi.aggregateFunds()
      if (type === 'positions') return adminMtApi.aggregatePositions()
      return adminMtApi.aggregateOrders()
    },
  })

  const allRows: AggregateUserRow[] = query.data?.users || []
  const usernames = useMemo(() => allRows.map((r) => r.username), [allRows])
  const rows = selectedUser === 'all' ? allRows : allRows.filter((r) => r.username === selectedUser)
  const totals = query.data?.totals as Record<string, number> | undefined

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{TITLES[type]}</h1>
          <p className="text-muted-foreground">Across all approved users</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={selectedUser} onValueChange={setSelectedUser}>
            <SelectTrigger className="w-48">
              <SelectValue placeholder="Filter by user" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All users</SelectItem>
              {usernames.map((u) => (
                <SelectItem key={u} value={u}>
                  {u}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            size="icon"
            onClick={() => query.refetch()}
            disabled={query.isFetching}
          >
            <RefreshCw className={`h-4 w-4 ${query.isFetching ? 'animate-spin' : ''}`} />
          </Button>
        </div>
      </div>

      {/* Totals bar */}
      {totals && (
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {type === 'funds' &&
            FUND_FIELDS.map((f) => (
              <Card key={f.key}>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">{f.label}</p>
                  <p className="text-lg font-semibold">₹{fmtNum(totals[f.key])}</p>
                </CardContent>
              </Card>
            ))}
          {type === 'positions' && (
            <>
              <Card>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">Open Positions</p>
                  <p className="text-lg font-semibold">{fmtNum(totals.position_count)}</p>
                </CardContent>
              </Card>
              <Card>
                <CardContent className="p-4">
                  <p className="text-xs text-muted-foreground">Total P&L</p>
                  <p
                    className={`text-lg font-semibold ${
                      totals.total_pnl >= 0 ? 'text-green-600' : 'text-destructive'
                    }`}
                  >
                    ₹{fmtNum(totals.total_pnl)}
                  </p>
                </CardContent>
              </Card>
            </>
          )}
          {type === 'orders' && (
            <Card>
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">Total Orders</p>
                <p className="text-lg font-semibold">{fmtNum(totals.order_count)}</p>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            {selectedUser === 'all' ? 'All Users' : selectedUser}
            <Badge variant="secondary">{rows.length} user(s)</Badge>
          </CardTitle>
        </CardHeader>
        <CardContent className="overflow-x-auto">
          {query.isLoading ? (
            <p className="text-muted-foreground py-8 text-center">Loading…</p>
          ) : query.error ? (
            <p className="text-destructive py-8 text-center">Failed to load data.</p>
          ) : rows.length === 0 ? (
            <p className="text-muted-foreground py-8 text-center">
              No approved users with a connected broker.
            </p>
          ) : type === 'funds' ? (
            <FundsTable rows={rows} />
          ) : type === 'positions' ? (
            <PositionsTable rows={rows} />
          ) : (
            <OrdersTable rows={rows} />
          )}
        </CardContent>
      </Card>
    </div>
  )
}
