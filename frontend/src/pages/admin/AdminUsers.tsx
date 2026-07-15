import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Check, X } from 'lucide-react'
import { adminMtApi, type MtUser } from '@/api/adminMt'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { showToast } from '@/utils/toast'

function statusBadge(status: string) {
  if (status === 'approved') return <Badge className="bg-green-600">approved</Badge>
  if (status === 'pending') return <Badge className="bg-amber-500">pending</Badge>
  if (status === 'rejected') return <Badge variant="destructive">rejected</Badge>
  return <Badge variant="secondary">{status}</Badge>
}

export default function AdminUsers() {
  const queryClient = useQueryClient()
  const { data: users = [], isLoading, error } = useQuery({
    queryKey: ['admin-mt-users'],
    queryFn: adminMtApi.listUsers,
  })

  const approve = useMutation({
    mutationFn: (u: string) => adminMtApi.approveUser(u),
    onSuccess: (_d, u) => {
      showToast.success(`Approved ${u}`, 'system')
      queryClient.invalidateQueries({ queryKey: ['admin-mt-users'] })
    },
    onError: () => showToast.error('Failed to approve user', 'system'),
  })

  const reject = useMutation({
    mutationFn: (u: string) => adminMtApi.rejectUser(u),
    onSuccess: (_d, u) => {
      showToast.success(`Rejected ${u}`, 'system')
      queryClient.invalidateQueries({ queryKey: ['admin-mt-users'] })
    },
    onError: () => showToast.error('Failed to reject user', 'system'),
  })

  const pendingCount = users.filter((u) => u.status === 'pending').length

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">User Management</h1>
        <p className="text-muted-foreground">
          Approve or reject registered users. {pendingCount} pending.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>All Users ({users.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading ? (
            <p className="text-muted-foreground py-8 text-center">Loading users…</p>
          ) : error ? (
            <p className="text-destructive py-8 text-center">Failed to load users.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Username</TableHead>
                  <TableHead>Email</TableHead>
                  <TableHead>Role</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {users.map((u: MtUser) => (
                  <TableRow key={u.username}>
                    <TableCell className="font-medium">{u.username}</TableCell>
                    <TableCell>{u.email}</TableCell>
                    <TableCell>
                      <Badge variant={u.role === 'admin' ? 'default' : 'secondary'}>
                        {u.role}
                      </Badge>
                    </TableCell>
                    <TableCell>{statusBadge(u.status)}</TableCell>
                    <TableCell className="text-right space-x-2">
                      {u.status === 'pending' && (
                        <>
                          <Button
                            size="sm"
                            onClick={() => approve.mutate(u.username)}
                            disabled={approve.isPending}
                          >
                            <Check className="h-4 w-4 mr-1" />
                            Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="destructive"
                            onClick={() => reject.mutate(u.username)}
                            disabled={reject.isPending}
                          >
                            <X className="h-4 w-4 mr-1" />
                            Reject
                          </Button>
                        </>
                      )}
                      {u.status === 'approved' && u.role !== 'admin' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => reject.mutate(u.username)}
                          disabled={reject.isPending}
                        >
                          Revoke
                        </Button>
                      )}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
