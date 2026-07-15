import { Link, Navigate, Outlet, useLocation } from 'react-router-dom'
import { SocketProvider } from '@/components/socket/SocketProvider'
import { useAuthStore } from '@/stores/authStore'
import { Footer } from './Footer'
import { MobileBottomNav } from './MobileBottomNav'
import { Navbar } from './Navbar'

export function Layout() {
  const { isSessionActive, user } = useAuthStore()
  const location = useLocation()

  // Require a logged-in app session (password/TOTP done). A broker is NOT
  // required to enter the app shell — users can browse the dashboard and menus
  // before connecting; broker-dependent views show a "connect broker" prompt.
  if (!isSessionActive) {
    return <Navigate to="/login" replace />
  }

  // Show the connect-broker banner everywhere except the broker connect and
  // credentials pages, where it would be redundant.
  const onBrokerPages = ['/broker', '/broker-credentials'].includes(location.pathname)
  const noBroker = !user?.broker && !onBrokerPages

  return (
    <SocketProvider>
      <div className="min-h-screen bg-background flex flex-col">
        <Navbar />
        <main className="container mx-auto px-4 py-6 pb-24 md:pb-6 flex-1">
          {noBroker && (
            <div className="mb-6 flex flex-col sm:flex-row sm:items-center justify-between gap-3 rounded-lg border border-amber-500/40 bg-amber-500/10 px-4 py-3">
              <p className="text-sm text-amber-700 dark:text-amber-400">
                You haven't connected a broker yet. Connect one to place orders and see live
                positions, funds and market data.
              </p>
              <Link
                to="/broker"
                className="shrink-0 inline-flex items-center justify-center rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90"
              >
                Connect broker
              </Link>
            </div>
          )}
          <Outlet />
        </main>
        <Footer className="hidden md:block" />
        <MobileBottomNav />
      </div>
    </SocketProvider>
  )
}

export function PublicLayout() {
  return (
    <div className="min-h-screen bg-background">
      <Outlet />
    </div>
  )
}
