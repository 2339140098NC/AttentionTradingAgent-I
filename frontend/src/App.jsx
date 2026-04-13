import { useEffect, useState } from 'react'
import {
  Radar,
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  ResponsiveContainer,
} from 'recharts'

const API_BASE = '' // proxied by vite to http://localhost:8000

const DIMENSION_META = {
  momentum:           { icon: '📈', label: 'Momentum' },
  catalyst:           { icon: '⚡', label: 'Catalyst' },
  cross_platform:     { icon: '🌐', label: 'Cross-Platform' },
  cultural_context:   { icon: '🎭', label: 'Cultural Context' },
  market_positioning: { icon: '📊', label: 'Market Position' },
}

const STATUS_STYLE = {
  pending_confirmation: { label: 'Pending',        cls: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30' },
  pending:              { label: 'Pending',        cls: 'bg-yellow-500/15 text-yellow-300 border-yellow-500/30' },
  call_initiated:       { label: 'Call Initiated', cls: 'bg-blue-500/15 text-blue-300 border-blue-500/30' },
  trade_executed:       { label: 'Trade Executed', cls: 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30' },
  low_confidence:       { label: 'Low Confidence', cls: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30' },
  no_voice:             { label: 'No Voice',       cls: 'bg-zinc-500/15 text-zinc-300 border-zinc-500/30' },
}

function statusBadge(status) {
  const s = STATUS_STYLE[status] || { label: status || 'Unknown', cls: 'bg-zinc-700/30 text-zinc-300 border-zinc-600/40' }
  return <span className={`inline-block text-xs px-2 py-0.5 rounded-full border ${s.cls}`}>{s.label}</span>
}

function scoreColor(score) {
  if (score >= 7) return 'bg-emerald-500'
  if (score >= 4) return 'bg-yellow-500'
  return 'bg-red-500'
}

function formatTime(ts) {
  if (!ts) return '-'
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function Header() {
  return (
    <header className="border-b border-zinc-800 bg-zinc-950/80 backdrop-blur px-6 py-4 flex items-center justify-between">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-zinc-100">Attention Trading Agent</h1>
        <p className="text-xs text-zinc-500 mt-0.5">Five-Factor Attention Alpha Model</p>
      </div>
      <div className="flex items-center gap-2 text-sm text-zinc-300">
        <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulseDot shadow-[0_0_8px_rgba(52,211,153,0.8)]" />
        Agent Active
      </div>
    </header>
  )
}

function DirectionBadge({ direction }) {
  const isLong = direction === 'long'
  const cls = isLong
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : 'bg-red-500/15 text-red-300 border-red-500/30'
  return (
    <span className={`px-3 py-1 rounded-full border text-sm font-semibold tracking-wide ${cls}`}>
      {isLong ? 'LONG' : 'SHORT'}
    </span>
  )
}

function ScoreBar({ dim }) {
  const meta = DIMENSION_META[dim.name] || { icon: '•', label: dim.name }
  const pct = Math.max(0, Math.min(100, dim.score * 10))
  return (
    <div className="flex items-center gap-3">
      <div className="w-40 flex items-center gap-2 text-sm text-zinc-300">
        <span>{meta.icon}</span>
        <span className="truncate">{meta.label}</span>
      </div>
      <div className="flex-1 h-2 rounded-full bg-zinc-800 overflow-hidden">
        <div className={`h-full ${scoreColor(dim.score)} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
      <div className="w-10 text-right font-mono text-sm text-zinc-200">{dim.score}</div>
    </div>
  )
}

function Radar5({ dimensions }) {
  const data = dimensions.map((d) => ({
    dimension: DIMENSION_META[d.name]?.label || d.name,
    score: d.score,
  }))
  return (
    <div className="h-72">
      <ResponsiveContainer width="100%" height="100%">
        <RadarChart data={data} outerRadius="75%">
          <PolarGrid stroke="#27272a" />
          <PolarAngleAxis dataKey="dimension" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
          <PolarRadiusAxis angle={90} domain={[0, 10]} tick={{ fill: '#52525b', fontSize: 10 }} stroke="#27272a" />
          <Radar
            name="Score"
            dataKey="score"
            stroke="#10b981"
            fill="#10b981"
            fillOpacity={0.35}
            strokeWidth={2}
          />
        </RadarChart>
      </ResponsiveContainer>
    </div>
  )
}

function LatestReport({ report }) {
  const s = report.signal || {}
  const dims = s.dimensions || []
  return (
    <div key={report.id} className="grid grid-cols-1 lg:grid-cols-5 gap-6 animate-fadeIn">
      {/* Left column */}
      <div className="lg:col-span-3 space-y-5">
        <div className="flex items-center gap-4 flex-wrap">
          <h2 className="text-4xl font-bold tracking-tight text-zinc-50 font-mono">{s.ticker}</h2>
          <DirectionBadge direction={s.direction} />
          {statusBadge(report.status)}
        </div>

        <div className="flex items-baseline gap-8">
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider">Confidence</div>
            <div className="text-5xl font-bold font-mono text-emerald-400">{s.confidence}%</div>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider">Weighted Score</div>
            <div className="text-3xl font-mono text-zinc-200">{(s.weighted_score ?? 0).toFixed(1)} <span className="text-zinc-500 text-xl">/ 10</span></div>
          </div>
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider">Suggested Qty</div>
            <div className="text-3xl font-mono text-zinc-200">{s.suggested_qty ?? '-'}</div>
          </div>
        </div>

        {s.summary && (
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider mb-1">Summary</div>
            <p className="text-sm text-zinc-300 leading-relaxed">{s.summary}</p>
          </div>
        )}

        {s.cultural_narrative && (
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider mb-1 flex items-center gap-1"><span>🎭</span> Cultural Narrative</div>
            <p className="text-sm text-zinc-300 leading-relaxed">{s.cultural_narrative}</p>
          </div>
        )}

        {s.phone_script && (
          <div>
            <div className="text-xs uppercase text-zinc-500 tracking-wider mb-2 flex items-center gap-1"><span>📞</span> Phone Script</div>
            <div className="relative bg-emerald-500/10 border border-emerald-500/30 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-emerald-100 leading-relaxed">
              {s.phone_script}
            </div>
          </div>
        )}
      </div>

      {/* Right column */}
      <div className="lg:col-span-2 space-y-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-3">
          <Radar5 dimensions={dims} />
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 p-4 space-y-3">
          {dims.map((d) => <ScoreBar key={d.name} dim={d} />)}
        </div>
      </div>
    </div>
  )
}

function HistoryTable({ reports }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/40 overflow-hidden">
      <div className="px-4 py-3 border-b border-zinc-800 text-xs uppercase tracking-wider text-zinc-500">
        Trade History
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-xs uppercase text-zinc-500 tracking-wider">
            <th className="text-left font-normal px-4 py-2">Time</th>
            <th className="text-left font-normal px-4 py-2">Ticker</th>
            <th className="text-left font-normal px-4 py-2">Direction</th>
            <th className="text-right font-normal px-4 py-2">Confidence</th>
            <th className="text-right font-normal px-4 py-2">Score</th>
            <th className="text-left font-normal px-4 py-2">Status</th>
          </tr>
        </thead>
        <tbody>
          {reports.slice().reverse().map((r) => {
            const s = r.signal || {}
            const isLong = s.direction === 'long'
            return (
              <tr key={r.id} className="border-t border-zinc-800/70 hover:bg-zinc-800/30">
                <td className="px-4 py-2 font-mono text-zinc-400">{formatTime(r.timestamp)}</td>
                <td className="px-4 py-2 font-mono text-zinc-100">{r.ticker}</td>
                <td className={`px-4 py-2 font-semibold ${isLong ? 'text-emerald-400' : 'text-red-400'}`}>
                  {(s.direction || '').toUpperCase()}
                </td>
                <td className="px-4 py-2 font-mono text-right text-zinc-200">{s.confidence ?? '-'}%</td>
                <td className="px-4 py-2 font-mono text-right text-zinc-300">{(s.weighted_score ?? 0).toFixed(1)}</td>
                <td className="px-4 py-2">{statusBadge(r.status)}</td>
              </tr>
            )
          })}
          {reports.length === 0 && (
            <tr>
              <td colSpan={6} className="px-4 py-8 text-center text-zinc-500 text-sm">No trades yet</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

function WaitingState() {
  return (
    <div className="flex flex-col items-center justify-center py-24 text-zinc-400">
      <div className="w-10 h-10 border-2 border-zinc-700 border-t-emerald-400 rounded-full animate-spin mb-4" />
      <p className="text-sm">Waiting for agent to find opportunities...</p>
    </div>
  )
}

export default function App() {
  const [latest, setLatest] = useState(null)
  const [reports, setReports] = useState([])
  const [error, setError] = useState(null)

  useEffect(() => {
    let cancelled = false

    async function poll() {
      try {
        const [latestRes, listRes] = await Promise.all([
          fetch(`${API_BASE}/api/reports/latest`),
          fetch(`${API_BASE}/api/reports`),
        ])
        const latestJson = await latestRes.json()
        const listJson = await listRes.json()
        if (cancelled) return
        if (latestJson && !latestJson.error && latestJson.id) {
          setLatest((prev) => (prev && prev.id === latestJson.id ? prev : latestJson))
        }
        setReports(listJson.reports || [])
        setError(null)
      } catch (e) {
        if (!cancelled) setError(e.message || 'fetch failed')
      }
    }

    poll()
    const id = setInterval(poll, 5000)
    return () => { cancelled = true; clearInterval(id) }
  }, [])

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100">
      <Header />
      <main className="max-w-7xl mx-auto px-6 py-6 space-y-8">
        {error && (
          <div className="text-xs text-red-400 border border-red-500/30 bg-red-500/10 rounded px-3 py-2">
            API error: {error}
          </div>
        )}
        {latest ? <LatestReport report={latest} /> : <WaitingState />}
        <HistoryTable reports={reports} />
      </main>
    </div>
  )
}
