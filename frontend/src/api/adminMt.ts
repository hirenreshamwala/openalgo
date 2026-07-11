// Multi-tenant admin API: user management + cross-user aggregation.
import { webClient } from './client'

export interface MtUser {
  username: string
  email: string
  status: string
  role: string
}

export interface AggregateUserRow {
  username: string
  broker: string | null
  error: string | null
  orders?: Record<string, unknown>[]
  statistics?: Record<string, number>
  positions?: Record<string, unknown>[]
  funds?: Record<string, unknown>
}

export interface OrdersAggregate {
  status: string
  users: AggregateUserRow[]
  totals: { order_count: number }
}

export interface PositionsAggregate {
  status: string
  users: AggregateUserRow[]
  totals: { position_count: number; total_pnl: number }
}

export interface FundsAggregate {
  status: string
  users: AggregateUserRow[]
  totals: Record<string, number>
}

export const adminMtApi = {
  listUsers: async (): Promise<MtUser[]> => {
    const res = await webClient.get<{ status: string; users: MtUser[] }>('/admin/users')
    return res.data.users || []
  },

  approveUser: async (username: string): Promise<void> => {
    await webClient.post(`/admin/users/${encodeURIComponent(username)}/approve`)
  },

  rejectUser: async (username: string): Promise<void> => {
    await webClient.post(`/admin/users/${encodeURIComponent(username)}/reject`)
  },

  aggregateOrders: async (): Promise<OrdersAggregate> => {
    const res = await webClient.get<OrdersAggregate>('/admin/aggregate/orders')
    return res.data
  },

  aggregatePositions: async (): Promise<PositionsAggregate> => {
    const res = await webClient.get<PositionsAggregate>('/admin/aggregate/positions')
    return res.data
  },

  aggregateFunds: async (): Promise<FundsAggregate> => {
    const res = await webClient.get<FundsAggregate>('/admin/aggregate/funds')
    return res.data
  },
}
