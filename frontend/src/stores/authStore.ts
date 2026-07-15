import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { useBrokerStore } from './brokerStore'

interface User {
  username: string
  broker: string | null
  isLoggedIn: boolean
  loginTime: string | null
  role?: string
}

interface AuthStore {
  user: User | null
  apiKey: string | null
  isAuthenticated: boolean
  // True when the user has completed password/TOTP login, even if no broker
  // is connected yet. Used to gate the multi-tenant admin area (admins have
  // no broker session of their own).
  isSessionActive: boolean
  role: string

  setUser: (user: User) => void
  setApiKey: (apiKey: string | null) => void
  setSession: (active: boolean, role: string) => void
  login: (username: string, broker: string) => void
  logout: () => void
  checkSession: () => boolean
}

export const useAuthStore = create<AuthStore>()(
  persist(
    (set, get) => ({
      user: null,
      apiKey: null,
      isAuthenticated: false,
      isSessionActive: false,
      role: 'user',

      setUser: (user) =>
        set({ user, isAuthenticated: user.isLoggedIn, role: user.role || 'user' }),

      setApiKey: (apiKey) => set({ apiKey }),

      setSession: (active, role) => set({ isSessionActive: active, role: role || 'user' }),

      login: (username, broker) => {
        // isAuthenticated (broker session live, gates the socket) requires a
        // broker. isSessionActive (app shell access) only needs the login.
        const hasBroker = !!broker
        const user: User = {
          username,
          broker: broker || null,
          isLoggedIn: hasBroker,
          loginTime: new Date().toISOString(),
        }
        set({ user, isAuthenticated: hasBroker, isSessionActive: true })
      },

      logout: () => {
        set({
          user: null,
          apiKey: null,
          isAuthenticated: false,
          isSessionActive: false,
          role: 'user',
        })
      },

      checkSession: () => {
        const { user } = get()
        if (!user || !user.loginTime) return false

        // Skip session expiry for crypto brokers (24/7 markets)
        const capabilities = useBrokerStore.getState().capabilities
        if (capabilities?.broker_type === 'crypto') {
          return true
        }

        // Session expiry check (3 AM IST daily)
        const now = new Date()
        const loginTime = new Date(user.loginTime)

        // Convert to IST properly: UTC + 5.5 hours
        // First get UTC time, then add IST offset
        const istOffsetMs = 5.5 * 60 * 60 * 1000
        const localOffsetMs = now.getTimezoneOffset() * 60 * 1000

        // Convert current time to IST
        const nowUTC = now.getTime() + localOffsetMs
        const nowIST = new Date(nowUTC + istOffsetMs)

        // Convert login time to IST
        const loginUTC = loginTime.getTime() + localOffsetMs
        const loginIST = new Date(loginUTC + istOffsetMs)

        // Create today's 3 AM IST expiry time
        const todayExpiry = new Date(nowIST)
        todayExpiry.setHours(3, 0, 0, 0)

        // If current time is after 3 AM IST today and login was before 3 AM IST today
        if (nowIST > todayExpiry && loginIST < todayExpiry) {
          get().logout()
          return false
        }

        return true
      },
    }),
    {
      name: 'openalgo-auth',
    }
  )
)
