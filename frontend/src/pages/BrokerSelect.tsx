import { BookOpen, ExternalLink, Info, Loader2, LogOut } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { authApi } from '@/api/auth'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { useAuthStore } from '@/stores/authStore'

// All supported brokers with their display names and auth types
const allBrokers = [
  { id: 'fivepaisa', name: '5 Paisa', authType: 'totp' },
  { id: 'fivepaisaxts', name: '5 Paisa (XTS)', authType: 'totp' },
  { id: 'aliceblue', name: 'Alice Blue', authType: 'totp' },
  { id: 'angel', name: 'Angel One', authType: 'totp' },
  { id: 'arrow', name: 'Arrow', authType: 'oauth' },
  { id: 'compositedge', name: 'CompositEdge', authType: 'oauth' },
  { id: 'dhan', name: 'Dhan', authType: 'oauth' },
  { id: 'deltaexchange', name: 'Delta Exchange', authType: 'totp' },
  { id: 'indmoney', name: 'IndMoney', authType: 'totp' },
  { id: 'dhan_sandbox', name: 'Dhan (Sandbox)', authType: 'totp' },
  { id: 'definedge', name: 'Definedge', authType: 'totp' },
  { id: 'firstock', name: 'Firstock', authType: 'totp' },
  { id: 'flattrade', name: 'Flattrade', authType: 'oauth' },
  { id: 'motilal', name: 'Motilal Oswal', authType: 'totp' },
  { id: 'fyers', name: 'Fyers', authType: 'oauth' },
  { id: 'groww', name: 'Groww', authType: 'totp' },
  { id: 'ibulls', name: 'Ibulls', authType: 'totp' },
  { id: 'iifl', name: 'IIFL', authType: 'totp' },
  { id: 'iiflcapital', name: 'IIFL Capital', authType: 'oauth' },
  { id: 'jainamxts', name: 'JainamXts', authType: 'totp' },
  { id: 'kotak', name: 'Kotak Securities', authType: 'totp' },
  { id: 'mstock', name: 'mStock by Mirae Asset', authType: 'totp' },
  { id: 'nubra', name: 'Nubra', authType: 'totp' },
  { id: 'paytm', name: 'Paytm Money', authType: 'oauth' },
  { id: 'pocketful', name: 'Pocketful', authType: 'oauth' },
  { id: 'rmoney', name: 'RMoney', authType: 'oauth' },
  { id: 'samco', name: 'Samco', authType: 'totp' },
  { id: 'shoonya', name: 'Shoonya', authType: 'totp' },
  { id: 'tradejini', name: 'Tradejini', authType: 'totp' },
  { id: 'tradesmart', name: 'TradeSmart', authType: 'oauth' },
  { id: 'upstox', name: 'Upstox', authType: 'oauth' },
  { id: 'wisdom', name: 'Wisdom Capital', authType: 'totp' },
  { id: 'zebu', name: 'Zebu', authType: 'totp' },
  { id: 'zerodha', name: 'Zerodha', authType: 'oauth' },
] as const

interface BrokerConfig {
  broker_name: string
  broker_api_key: string
  redirect_url: string
}

// Helper function to get Flattrade API key
function getFlattradeApiKey(fullKey: string): string {
  if (!fullKey) return ''
  const parts = fullKey.split(':::')
  return parts.length > 1 ? parts[1] : fullKey
}

// Generate random state for OAuth
function generateRandomState(): string {
  const length = 16
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
  let result = ''
  for (let i = 0; i < length; i++) {
    result += chars.charAt(Math.floor(Math.random() * chars.length))
  }
  return result
}

export default function BrokerSelect() {
  const { user, logout } = useAuthStore()
  const navigate = useNavigate()
  const [selectedBroker, setSelectedBroker] = useState<string>('')
  const [isLoading, setIsLoading] = useState(true)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [brokerConfig, setBrokerConfig] = useState<BrokerConfig | null>(null)
  // Multi-tenant: each user has their own set of configured brokers.
  const [multiTenant, setMultiTenant] = useState(false)
  const [mtBrokers, setMtBrokers] = useState<BrokerConfig[]>([])

  useEffect(() => {
    // Fetch broker configuration
    const fetchBrokerConfig = async () => {
      try {
        // Multi-tenant first: the per-user endpoint returns the brokers this
        // user has configured. A 404 means single-tenant mode — fall back.
        const mtResp = await fetch('/mt/broker-config', { credentials: 'include' })
        if (mtResp.ok) {
          const mtData = await mtResp.json()
          if (mtData.status === 'success' && mtData.multi_tenant) {
            setMultiTenant(true)
            setMtBrokers(mtData.brokers || [])
            if (mtData.brokers && mtData.brokers.length > 0) {
              setBrokerConfig(mtData.brokers[0])
              setSelectedBroker(mtData.brokers[0].broker_name)
            }
            setIsLoading(false)
            return
          }
        }

        // Single-tenant mode
        const response = await fetch('/auth/broker-config', {
          credentials: 'include',
        })
        const data = await response.json()

        if (data.status === 'success') {
          setBrokerConfig(data)
          // Auto-select the configured broker
          setSelectedBroker(data.broker_name)
        } else {
          setError(data.message || 'Failed to load broker configuration')
        }
      } catch {
        setError('Failed to load broker configuration')
      } finally {
        setIsLoading(false)
      }
    }

    fetchBrokerConfig()
  }, [])

  // Multi-tenant: when the user picks a different broker, swap the active
  // config (api key + redirect url) to that broker's stored credentials.
  const handleBrokerChange = (value: string) => {
    setSelectedBroker(value)
    if (multiTenant) {
      const cfg = mtBrokers.find((b) => b.broker_name === value)
      if (cfg) setBrokerConfig(cfg)
    }
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

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()

    if (!selectedBroker) {
      setError('Please select a broker')
      return
    }

    if (!brokerConfig) {
      setError('Broker configuration not loaded')
      return
    }

    setIsSubmitting(true)
    let loginUrl = ''

    const { broker_api_key, redirect_url } = brokerConfig

    // Build login URL based on broker type (matching original broker.html logic)
    switch (selectedBroker) {
      case 'fivepaisa':
      case 'fivepaisaxts':
      case 'aliceblue':
      case 'angel':
      case 'mstock':
      case 'indmoney':
      case 'deltaexchange':
      case 'jainamxts':
      case 'dhan_sandbox':
      case 'definedge':
      case 'firstock':
      case 'samco':
      case 'motilal':
      case 'nubra':
      case 'groww':
      case 'ibulls':
      case 'iifl':
      case 'kotak':
      case 'rmoney':
      case 'shoonya':
      case 'tradejini':
      case 'tradesmart':
      case 'wisdom':
      case 'zebu':
        // Brokers using callback route (form-based or redirect-based)
        loginUrl = `/${selectedBroker}/callback`
        break

      case 'iiflcapital':
        // Route via backend callback endpoint to centralize URL generation and
        // avoid provider-specific redirect parameter parsing differences.
        loginUrl = '/iiflcapital/callback'
        break

      case 'dhan':
        loginUrl = '/dhan/initiate-oauth'
        break

      case 'compositedge':
        loginUrl = `https://xts.compositedge.com/interactive/thirdparty?appKey=${broker_api_key}&returnURL=${redirect_url}`
        break

      case 'flattrade': {
        const flattradeApiKey = getFlattradeApiKey(broker_api_key)
        loginUrl = `https://auth.flattrade.in/?app_key=${flattradeApiKey}`
        break
      }

      case 'fyers':
        loginUrl = `https://api-t1.fyers.in/api/v3/generate-authcode?client_id=${broker_api_key}&redirect_uri=${redirect_url}&response_type=code&state=2e9b44629ebb28226224d09db3ffb47c`
        break

      case 'upstox':
        loginUrl = `https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id=${broker_api_key}&redirect_uri=${redirect_url}`
        break

      case 'zerodha':
        loginUrl = `https://kite.trade/connect/login?api_key=${broker_api_key}`
        break

      case 'arrow':
        // Arrow hosted login; redirects back to /arrow/callback with request-token.
        loginUrl = `https://app.arrow.trade/app/login?appID=${broker_api_key}`
        break

      case 'paytm':
        loginUrl = `https://login.paytmmoney.com/merchant-login?apiKey=${broker_api_key}&state={default}`
        break

      case 'pocketful': {
        const state = generateRandomState()
        localStorage.setItem('pocketful_oauth_state', state)
        const scope = 'orders holdings'
        loginUrl = `https://trade.pocketful.in/oauth2/auth?client_id=${broker_api_key}&redirect_uri=${redirect_url}&response_type=code&scope=${encodeURIComponent(scope)}&state=${encodeURIComponent(state)}`
        break
      }

      default:
        setError('Please select a broker')
        setIsSubmitting(false)
        return
    }

    // Use setTimeout to ensure state updates complete before navigation
    setTimeout(() => {
      window.location.href = loginUrl
    }, 100)
  }

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin" />
      </div>
    )
  }

  return (
    <div className="min-h-[70vh] flex items-center justify-center py-4">
      <div className="container max-w-6xl">
        <div className="flex flex-col lg:flex-row items-center justify-between gap-8 lg:gap-16">
          {/* Right side broker form - Shown first on mobile */}
          <Card className="w-full max-w-md shadow-xl order-1 lg:order-2">
            <CardHeader className="text-center">
              <div className="flex justify-center mb-4">
                <img src="/logo.png" alt="OpenAlgo" className="h-20 w-20" />
              </div>
              <CardTitle className="text-2xl">Connect Your Trading Account</CardTitle>
              <CardDescription>
                Welcome, <span className="font-medium">{user?.username}</span>!
              </CardDescription>
            </CardHeader>
            <CardContent>
              {error && (
                <Alert variant="destructive" className="mb-4">
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              )}

              {multiTenant && mtBrokers.length === 0 ? (
                <div className="space-y-4 text-center">
                  <Alert>
                    <Info className="h-4 w-4" />
                    <AlertDescription>
                      You haven't added any broker credentials yet. Add your broker's
                      API key and secret to get started.
                    </AlertDescription>
                  </Alert>
                  <Button asChild className="w-full">
                    <Link to="/broker-credentials">Add Broker Credentials</Link>
                  </Button>
                </div>
              ) : (
              <form onSubmit={handleSubmit} className="space-y-6">
                <div className="space-y-2">
                  <Label htmlFor="broker-select" className="block text-center">
                    Login with your Broker
                  </Label>
                  <Select
                    value={selectedBroker}
                    onValueChange={handleBrokerChange}
                    disabled={isSubmitting}
                  >
                    <SelectTrigger id="broker-select" className="w-full">
                      <SelectValue placeholder="Select a Broker" />
                    </SelectTrigger>
                    <SelectContent>
                      {multiTenant
                        ? mtBrokers.map((cfg) => {
                            const meta = allBrokers.find((b) => b.id === cfg.broker_name)
                            return (
                              <SelectItem key={cfg.broker_name} value={cfg.broker_name}>
                                {meta?.name || cfg.broker_name}
                              </SelectItem>
                            )
                          })
                        : allBrokers
                            .filter((broker) => broker.id === brokerConfig?.broker_name)
                            .map((broker) => (
                              <SelectItem key={broker.id} value={broker.id}>
                                {broker.name}
                              </SelectItem>
                            ))}
                    </SelectContent>
                  </Select>
                </div>

                {(selectedBroker === 'zerodha' || selectedBroker === 'dhan') && (
                  <Alert className="border-amber-500/50 bg-amber-500/10">
                    <Info className="h-4 w-4 text-amber-500" />
                    <AlertDescription className="text-amber-700 dark:text-amber-400">
                      {selectedBroker === 'zerodha'
                        ? 'Zerodha requires an active Kite Connect data subscription for market data access.'
                        : 'Dhan requires an active Data API subscription for market data access.'}
                    </AlertDescription>
                  </Alert>
                )}

                <Button type="submit" className="w-full" disabled={!selectedBroker || isSubmitting}>
                  {isSubmitting ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      Connecting...
                    </>
                  ) : (
                    <>
                      <ExternalLink className="mr-2 h-4 w-4" />
                      Connect Account
                    </>
                  )}
                </Button>
              </form>
              )}
              {multiTenant && (
                <p className="mt-4 text-center text-sm text-muted-foreground">
                  <Link to="/broker-credentials" className="text-primary hover:underline">
                    Manage broker credentials
                  </Link>
                </p>
              )}

              <Button
                type="button"
                variant="outline"
                className="w-full mt-4"
                onClick={handleLogout}
              >
                <LogOut className="mr-2 h-4 w-4" />
                Logout
              </Button>
            </CardContent>
          </Card>

          {/* Left side content - Shown second on mobile */}
          <div className="flex-1 max-w-xl text-center lg:text-left order-2 lg:order-1">
            <h1 className="text-4xl lg:text-5xl font-bold mb-6">
              Connect Your <span className="text-primary">Broker</span>
            </h1>
            <p className="text-lg lg:text-xl mb-8 text-muted-foreground">
              Link your trading account to start executing trades through OpenAlgo's algorithmic
              trading platform.
            </p>

            <Alert className="mb-6">
              <BookOpen className="h-4 w-4" />
              <AlertTitle>Need Help?</AlertTitle>
              <AlertDescription>Check our documentation for broker setup guides.</AlertDescription>
            </Alert>

            <div className="flex justify-center lg:justify-start gap-4">
              <Button variant="outline" asChild>
                <a href="https://docs.openalgo.in" target="_blank" rel="noopener noreferrer">
                  <BookOpen className="mr-2 h-4 w-4" />
                  Documentation
                </a>
              </Button>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
