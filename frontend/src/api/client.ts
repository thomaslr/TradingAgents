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

export async function deleteRuns(runIds: number[]): Promise<void> {
  await api.post('/runs/batch-delete', { run_ids: runIds })
}

export interface TickerInfo {
  ticker: string
  name: string
}

export async function fetchTickers(): Promise<TickerInfo[]> {
  const { data } = await api.get<TickerInfo[]>('/runs/tickers')
  return data
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

export async function fetchOHLC(ticker: string, period = '1y', interval = '1d', start?: string, end?: string): Promise<OHLCData> {
  const params: any = { interval, period }
  if (start) params.start = start
  if (end) params.end = end
  
  const { data } = await api.get(`/market/ohlc/${ticker}`, { params })
  return data
}

// ── Analysis ────────────────────────────────────────────
export interface AnalysisRequest {
  tickers: string[]
  dates: string[]
  force?: boolean
  skip_completed?: boolean
  llm_provider?: string
  quick_think_llm?: string
  deep_think_llm?: string
  max_debate_rounds?: number
}

export async function startAnalysis(request: AnalysisRequest) {
  const { data } = await api.post('/analysis/batch', request)
  return data
}

export async function stopAnalysis() {
  const { data } = await api.post('/analysis/stop')
  return data
}

export async function fetchAnalysisStatus(): Promise<{ running: boolean, job: any, last_error?: string | null }> {
  const { data } = await api.get('/analysis/status')
  return data
}

// ── Health & Config ──────────────────────────────────────
export async function healthCheck() {
  const { data } = await api.get('/health')
  return data
}

export interface AppConfig {
  llm_provider: string
  quick_think_llm: string
  deep_think_llm: string
}

export async function fetchConfig(): Promise<AppConfig> {
  const { data } = await api.get('/config')
  return data
}

export async function fetchOllamaModels(): Promise<string[]> {
  const { data } = await api.get('/ollama/tags')
  return data
}

// ── Schedule ────────────────────────────────────────────
export interface ScheduleJob {
  id: string
  tickers: string[]
  config: Record<string, any>
  interval_minutes: number
  last_run: string | null
  next_run: string | null
  created_at: string
}

export async function fetchSchedules(): Promise<ScheduleJob[]> {
  const { data } = await api.get('/schedule')
  return data
}

export async function addSchedule(tickers: string[], config: Record<string, any>, interval_minutes: number): Promise<ScheduleJob> {
  const { data } = await api.post('/schedule', { tickers, config, interval_minutes })
  return data.job
}

export async function deleteSchedule(jobId: string): Promise<void> {
  await api.delete(`/schedule/${jobId}`)
}

// ── Memory / Performance ────────────────────────────────
export interface MemoryEntry {
  date: string
  ticker: string
  rating: string
  pending: boolean
  raw: string | null
  alpha: string | null
  holding: string | null
  decision: string
  reflection: string
  quick_model?: string
  deep_model?: string
  depth?: string
  runtime_sec?: string
  config_id?: string
}

export async function fetchMemoryEntries(): Promise<MemoryEntry[]> {
  const { data } = await api.get<MemoryEntry[]>('/memory')
  return data
}


export async function clearMemoryEntries(): Promise<void> {
  await api.delete('/memory')
}

// ── Simulation Configs ──────────────────────────────────
export interface SimulationConfig {
  config_id: string
  provider: string
  quick_model: string
  deep_model: string
  depth: number
  label: string
  color: string
  created_at: string
}

export async function fetchConfigs(): Promise<SimulationConfig[]> {
  const { data } = await api.get<SimulationConfig[]>('/runs/configs')
  return data
}

// ── Performance Data (DB-backed) ────────────────────────
export interface PerformanceEntry {
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
  close_price: number | null
  config_id: string
  config_label: string
  config_color: string
  raw_return: number
  alpha_return: number
  holding_days: number
  reflection: string | null
  runtime_sec: number | null
  outcome_status: string
}

export async function fetchPerformanceData(params?: {
  ticker?: string
  config_id?: string
  date_from?: string
  date_to?: string
}): Promise<PerformanceEntry[]> {
  const { data } = await api.get<PerformanceEntry[]>('/runs/performance', { params })
  return data
}
