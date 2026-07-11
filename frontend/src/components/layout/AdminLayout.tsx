import { LogOut, Users, Wallet, TrendingUp, ListOrdered } from 'lucide-react'
import { NavLink, Navigate, Outlet, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/authStore'

const navItems = [
  { to: '/admin/mt/users', label: 'Users', icon: Users },
  { to: '/admin/mt/funds', label: 'Funds', icon: Wallet },
  { to: '/admin/mt/positions', label: 'Positions', icon: TrendingUp },
  { to: '/admin/mt/orders', label: 'Orders', icon: ListOrdered },
]

/**
 * Layout for the multi-tenant admin area. Unlike the normal Layout, it does
 * NOT require a broker session — admins manage users and view aggregated data
 * without connecting a broker of their own. It requires an active app session
 * (password/TOTP done) and role === 'admin'.
 */
export function AdminLayout() {
  const { isSessionActive, role, user, logout } = useAuthStore()
  const navigate = useNavigate()

  if (!isSessionActive) {
    return <Navigate to="/login" replace />
  }
  if (role !== 'admin') {
    return <Navigate to="/broker" replace />
  }

  const handleLogout = async () => {
    try {
      await authApi.logout()
    } catch {
      // ignore — clear client state regardless
    }
    logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <header className="border-b bg-card">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <img src="/logo.png" alt="OpenAlgo" className="h-8 w-8" />
            <span className="font-semibold">Admin Console</span>
          </div>
          <nav className="hidden md:flex items-center gap-1">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `flex items-center gap-2 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                    isActive
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:bg-muted'
                  }`
                }
              >
                <Icon className="h-4 w-4" />
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="flex items-center gap-3">
            <span className="hidden sm:inline text-sm text-muted-foreground">
              {user?.username}
            </span>
            <Button variant="outline" size="sm" onClick={handleLogout}>
              <LogOut className="h-4 w-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
        {/* Mobile nav */}
        <nav className="md:hidden flex items-center gap-1 overflow-x-auto px-4 pb-2">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm whitespace-nowrap ${
                  isActive ? 'bg-primary text-primary-foreground' : 'text-muted-foreground'
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
      </header>
      <main className="container mx-auto px-4 py-6 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
