import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { webClient } from '@/api/client'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { ALL_BROKERS, brokerName } from '@/lib/brokers'
import { showToast } from '@/utils/toast'

interface ProxyParts {
  scheme: string
  host: string
  port: string
  user: string
}

export default function BrokerCredentials() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [currentBroker, setCurrentBroker] = useState<string | null>(null)
  const [hostServer, setHostServer] = useState('')
  const [error, setError] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)

  const [broker, setBroker] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')
  const [proxy, setProxy] = useState<ProxyParts>({ scheme: 'http', host: '', port: '', user: '' })
  const [proxyPass, setProxyPass] = useState('')

  const load = async () => {
    try {
      const res = await webClient.get('/mt/api/broker-credentials')
      const data = res.data
      setCurrentBroker(data.current_broker || null)
      setHostServer((data.host_server || window.location.origin).replace(/\/$/, ''))
      if (data.current_broker) {
        setBroker(data.current_broker)
        setProxy({
          scheme: data.proxy?.scheme || 'http',
          host: data.proxy?.host || '',
          port: data.proxy?.port || '',
          user: data.proxy?.user || '',
        })
      }
    } catch {
      setError('Failed to load broker credentials.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault()
    setSaving(true)
    setError(null)
    try {
      await webClient.post('/mt/api/broker-credentials', {
        broker,
        api_key: apiKey,
        api_secret: apiSecret,
        proxy_scheme: proxy.scheme,
        proxy_host: proxy.host,
        proxy_port: proxy.port,
        proxy_user: proxy.user,
        proxy_pass: proxyPass,
      })
      showToast.success(`Saved ${brokerName(broker)}`, 'system')
      setApiKey('')
      setApiSecret('')
      setProxyPass('')
      await load()
    } catch (err) {
      const msg =
        (err as { response?: { data?: { message?: string } } })?.response?.data?.message ||
        'Failed to save credentials.'
      setError(msg)
    } finally {
      setSaving(false)
    }
  }

  const handleRemove = async () => {
    if (!currentBroker) return
    if (!window.confirm(`Remove ${brokerName(currentBroker)} credentials?`)) return
    try {
      await webClient.delete(`/mt/api/broker-credentials/${currentBroker}`)
      showToast.success(`Removed ${brokerName(currentBroker)}`, 'system')
      setCurrentBroker(null)
      setBroker('')
      setProxy({ scheme: 'http', host: '', port: '', user: '' })
      await load()
    } catch {
      showToast.error('Failed to remove credentials', 'system')
    }
  }

  if (loading) {
    return <p className="text-muted-foreground py-10 text-center">Loading…</p>
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Broker Credentials</h1>
        <p className="text-muted-foreground">
          Add your broker's API key &amp; secret. One broker per account, stored encrypted.
        </p>
      </div>

      {currentBroker && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Configured broker</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <p className="font-medium">{brokerName(currentBroker)}</p>
              <p className="text-sm text-muted-foreground">
                Egress: {proxy.host ? `${proxy.scheme}://${proxy.host}${proxy.port ? `:${proxy.port}` : ''}` : 'direct'}
              </p>
            </div>
            <div className="flex gap-2">
              <Button asChild variant="default" size="sm">
                <Link to="/broker">Connect</Link>
              </Button>
              <Button variant="outline" size="sm" onClick={handleRemove}>
                Remove
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            {currentBroker ? 'Update your broker' : 'Add your broker'}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {currentBroker && (
            <Alert className="mb-4">
              <AlertDescription>
                You have {brokerName(currentBroker)} configured. Update its keys/proxy below, or
                remove it to switch to a different broker — only one broker per account.
              </AlertDescription>
            </Alert>
          )}
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <form onSubmit={handleSave} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="broker">Broker</Label>
              <Select value={broker} onValueChange={setBroker} disabled={!!currentBroker}>
                <SelectTrigger id="broker">
                  <SelectValue placeholder="Select a broker" />
                </SelectTrigger>
                <SelectContent>
                  {(currentBroker
                    ? ALL_BROKERS.filter((b) => b.id === currentBroker)
                    : ALL_BROKERS
                  ).map((b) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {broker && (
              <div className="space-y-1.5">
                <Label>Callback / Redirect URL</Label>
                <div className="flex items-center gap-2 rounded-md border bg-muted/40 px-3 py-2">
                  <code className="flex-1 text-sm break-all">
                    {hostServer}/{broker}/callback
                  </code>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(`${hostServer}/${broker}/callback`)
                      setCopied(true)
                      setTimeout(() => setCopied(false), 1500)
                    }}
                  >
                    {copied ? 'Copied' : 'Copy'}
                  </Button>
                </div>
                <p className="text-xs text-muted-foreground">
                  Register this exact URL as the redirect / callback URL in your{' '}
                  {brokerName(broker)} developer app.
                </p>
              </div>
            )}

            <div className="space-y-2">
              <Label htmlFor="apiKey">API Key</Label>
              <Input
                id="apiKey"
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="Your broker API key"
                autoComplete="off"
                required
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="apiSecret">API Secret</Label>
              <Input
                id="apiSecret"
                type="password"
                value={apiSecret}
                onChange={(e) => setApiSecret(e.target.value)}
                placeholder="Your broker API secret"
                autoComplete="off"
                required
              />
            </div>

            <fieldset className="rounded-lg border p-4 space-y-3">
              <legend className="text-sm text-muted-foreground px-1">Egress proxy (optional)</legend>
              <p className="text-sm text-muted-foreground">
                If your broker whitelists a specific static IP, enter a proxy that egresses from it.
                Leave Host blank for a direct connection.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="proxyScheme">Scheme</Label>
                  <Select
                    value={proxy.scheme}
                    onValueChange={(v) => setProxy({ ...proxy, scheme: v })}
                  >
                    <SelectTrigger id="proxyScheme">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="http">http</SelectItem>
                      <SelectItem value="https">https</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2 sm:col-span-2">
                  <Label htmlFor="proxyHost">Host / IP</Label>
                  <Input
                    id="proxyHost"
                    value={proxy.host}
                    onChange={(e) => setProxy({ ...proxy, host: e.target.value })}
                    placeholder="e.g. 203.0.113.10"
                    autoComplete="off"
                  />
                </div>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                <div className="space-y-2">
                  <Label htmlFor="proxyPort">Port</Label>
                  <Input
                    id="proxyPort"
                    value={proxy.port}
                    onChange={(e) => setProxy({ ...proxy, port: e.target.value })}
                    placeholder="8080"
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="proxyUser">Username</Label>
                  <Input
                    id="proxyUser"
                    value={proxy.user}
                    onChange={(e) => setProxy({ ...proxy, user: e.target.value })}
                    placeholder="optional"
                    autoComplete="off"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="proxyPass">Password</Label>
                  <Input
                    id="proxyPass"
                    type="password"
                    value={proxyPass}
                    onChange={(e) => setProxyPass(e.target.value)}
                    placeholder="optional"
                    autoComplete="off"
                  />
                </div>
              </div>
            </fieldset>

            <Button type="submit" className="w-full" disabled={saving || !broker}>
              {saving ? 'Saving…' : 'Save credentials'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
