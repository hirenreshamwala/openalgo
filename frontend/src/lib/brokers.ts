// Canonical list of supported brokers (id + display name). Shared by the
// broker-connect screen and the broker-credentials manager. Mirrors
// SUPPORTED_BROKERS in blueprints/mt_settings.py.
export interface BrokerMeta {
  id: string
  name: string
}

export const ALL_BROKERS: BrokerMeta[] = [
  { id: 'fivepaisa', name: '5 Paisa' },
  { id: 'fivepaisaxts', name: '5 Paisa (XTS)' },
  { id: 'aliceblue', name: 'Alice Blue' },
  { id: 'angel', name: 'Angel One' },
  { id: 'arrow', name: 'Arrow' },
  { id: 'compositedge', name: 'CompositEdge' },
  { id: 'dhan', name: 'Dhan' },
  { id: 'deltaexchange', name: 'Delta Exchange' },
  { id: 'indmoney', name: 'IndMoney' },
  { id: 'dhan_sandbox', name: 'Dhan (Sandbox)' },
  { id: 'definedge', name: 'Definedge' },
  { id: 'firstock', name: 'Firstock' },
  { id: 'flattrade', name: 'Flattrade' },
  { id: 'motilal', name: 'Motilal Oswal' },
  { id: 'fyers', name: 'Fyers' },
  { id: 'groww', name: 'Groww' },
  { id: 'ibulls', name: 'Ibulls' },
  { id: 'iifl', name: 'IIFL' },
  { id: 'iiflcapital', name: 'IIFL Capital' },
  { id: 'jainamxts', name: 'JainamXts' },
  { id: 'kotak', name: 'Kotak Securities' },
  { id: 'mstock', name: 'mStock by Mirae Asset' },
  { id: 'nubra', name: 'Nubra' },
  { id: 'paytm', name: 'Paytm Money' },
  { id: 'pocketful', name: 'Pocketful' },
  { id: 'rmoney', name: 'RMoney' },
  { id: 'samco', name: 'Samco' },
  { id: 'shoonya', name: 'Shoonya' },
  { id: 'tradejini', name: 'Tradejini' },
  { id: 'tradesmart', name: 'TradeSmart' },
  { id: 'upstox', name: 'Upstox' },
  { id: 'wisdom', name: 'Wisdom Capital' },
  { id: 'zebu', name: 'Zebu' },
  { id: 'zerodha', name: 'Zerodha' },
]

export const brokerName = (id: string): string =>
  ALL_BROKERS.find((b) => b.id === id)?.name || id
