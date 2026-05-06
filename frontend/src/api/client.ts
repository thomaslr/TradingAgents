import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ── Runs ────────────────────────────────────────────────
export interface Run {
  id: number
  ticker: string
  trade_date: string
  provider: string
  quick_model: string
  deep_model: string
  depth: number
  rating: string | null
  action: string | null
  entry_price: number | null
  stop_loss: number | null
  price_target: number | null
  position_sizing: string | null
  time_horizon: string | null
  close_price: number | null
  status: string
  error_message: string | null
  started_at: string | null
  completed_at: string | null
  report_dir: string | null
}

export async function fetchRuns(ticker?: string, status?: string, limit = 100): Promise<Run[]> {
  const params: Record<string, string | number> = { limit }
  if (ticker) params.ticker = ticker
  if (status) params.status = status
  const { data } = await api.get<Run[]>('/runs', { params })
  return data
}

export async function deleteRun(runId: number): Promise<void> {
  await api.delete(`/runs/${runId}`)
}

// ── Reports ─────────────────────────────────────────────
export interface ReportFile {
  filename: string
  content: string
}

export async function fetchReportList(ticker: string, date: string): Promise<string[]> {
  const { data } = await api.get(`/reports/${ticker}/${date}`)
  return data.files
}

export async function fetchReportContent(ticker: string, date: string, filename: string): Promise<string> {
  const { data } = await api.get(`/reports/${ticker}/${date}/${filename}`)
  return data.content
}

// ── Market Data ─────────────────────────────────────────
export interface Candle {
  time: string
  open: number
  high: number
  low: number
  close: number
}

export interface VolumeItem {
  time: string
  value: number
}

export interface OHLCData {
  ticker: string
  candles: Candle[]
  volumes: VolumeItem[]
}

export async function fetchOHLC(ticker: string, period = '1y', interval = '1d'): Promise<OHLCData> {
  const { data } = await api.get(`/market/ohlc/${ticker}`, { params: { period, interval } })
  return data
}

// ── Analysis ────────────────────────────────────────────
export interface AnalysisRequest {
  tickers: string[]
  dates: string[]
  force?: boolean
  skip_completed?: boolean
}

export async function startAnalysis(request: AnalysisRequest) {
  const { data } = await api.post('/analysis/batch', request)
  return data
}

// ── Health ───────────────────────────────────────────────
export async function healthCheck() {
  const { data } = await api.get('/health')
  return data
}
