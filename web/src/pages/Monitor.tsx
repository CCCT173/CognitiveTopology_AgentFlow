import { useEffect, useState, useMemo } from 'react'
import { systemApi, SysMetrics, SysStats } from '@/api'
import { useAuthStore } from '@/store/auth'
import Empty, { Loading } from '@/components/ui/Empty'
import Modal from '@/components/ui/Modal'

interface ApmEndpoint {
  key: string; method: string; path: string
  count: number; errors: number; error_rate: number
  avg_ms: number; p50_ms: number; p95_ms: number; max_ms: number
}
interface ApmSlowItem { method: string; path: string; status: number; dur_ms: number; ago: number }
interface ApmData {
  window_seconds: number; total_requests: number; qps: number
  errors: number; error_rate: number
  avg_ms: number; p50_ms: number; p95_ms: number; p99_ms: number; max_ms: number
  endpoints: ApmEndpoint[]; top_slow: ApmSlowItem[]; recent_errors: ApmSlowItem[]
  buf_size: number
}

function formatUptime(sec: number) {
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  const parts = []
  if (d) parts.push(`${d}天`)
  if (h) parts.push(`${h}小时`)
  if (m) parts.push(`${m}分`)
  if (!d && !h) parts.push(`${s}秒`)
  return parts.join(' ')
}

function Bar({ label, value, max = 100, unit = '%', color = 'cyan' }: { label: string; value: number; max?: number; unit?: string; color?: string }) {
  const pct = Math.min(100, (value / max) * 100)
  const warn = pct > 80
  const colorMap: Record<string, string> = {
    cyan: 'from-cyan-400 to-blue-500', purple: 'from-purple-400 to-fuchsia-500',
    emerald: 'from-emerald-400 to-green-500', amber: 'from-amber-400 to-orange-500', pink: 'from-pink-400 to-rose-500',
  }
  return (
    <div className="bg-card rounded-xl p-3 border border">
      <div className="flex items-center justify-between text-sm mb-2">
        <span className="text-secondary">{label}</span>
        <span className={`font-mono font-medium ${warn ? 'text-amber-300' : 'text-primary'}`}>{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-2 rounded-full bg-hover overflow-hidden">
        <div className={`h-full rounded-full bg-gradient-to-r ${colorMap[color]} transition-all duration-500`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function MetricCard({ icon, label, value, sub, color }: { icon: string; label: string; value: string | number; sub?: string; color: string }) {
  return (
    <div className={`bg-gradient-to-br ${color} rounded-xl p-4 border border`}>
      <div className="flex items-center justify-between mb-2">
        <span className="text-2xl">{icon}</span>
        {sub && <span className="text-xs text-tertiary">{sub}</span>}
      </div>
      <div className="text-2xl font-bold">{value}</div>
      <div className="text-sm text-tertiary">{label}</div>
    </div>
  )
}

interface LogItem { id: number; user_id: number; username: string; action: string; resource: string; resource_id: string; status: string; ip?: string; created_at: string; detail: any }

export default function Monitor() {
  const user = useAuthStore(s => s.user)
  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin'
  const [metrics, setMetrics] = useState<SysMetrics | null>(null)
  const [stats, setStats] = useState<SysStats | null>(null)
  const [apm, setApm] = useState<ApmData | null>(null)
  const [logs, setLogs] = useState<LogItem[]>([])
  const [logsTotal, setLogsTotal] = useState(0)
  const [loading, setLoading] = useState(true)
  const [logsLoading, setLogsLoading] = useState(false)
  const [history, setHistory] = useState<{ cpu: number[]; mem: number[] }>({ cpu: [], mem: [] })

  // 日志筛选/分页
  const [logPage, setLogPage] = useState(1)
  const [logDays, setLogDays] = useState(7)
  const [logAction, setLogAction] = useState('')
  const [logResource, setLogResource] = useState('')
  const [selectedLog, setSelectedLog] = useState<LogItem | null>(null)
  const LOG_PAGE_SIZE = 15

  const loadMetrics = async () => {
    try {
      const [m, s, a] = await Promise.all([
        systemApi.metrics(), systemApi.stats(),
        fetch('/api/v1/system/apm?window=300').then(r => r.json()).then(j => j.data).catch(() => null),
      ])
      setMetrics(m); setStats(s); setApm(a)
      setHistory(h => ({
        cpu: [...h.cpu.slice(-29), m.system.cpu_percent],
        mem: [...h.mem.slice(-29), m.system.memory_percent],
      }))
    } catch {}
  }

  const loadLogs = async () => {
    setLogsLoading(true)
    try {
      const params: any = { page: logPage, page_size: LOG_PAGE_SIZE, days: logDays }
      if (logAction) params.action = logAction
      if (logResource) params.resource = logResource
      const res = await systemApi.logs(params)
      setLogs(res.data?.items || [])
      setLogsTotal(res.data?.total || 0)
    } catch {} finally { setLogsLoading(false) }
  }

  useEffect(() => {
    if (!isAdmin) { setLoading(false); return }
    ;(async () => {
      await loadMetrics()
      setLoading(false)
    })()
    const timer = setInterval(loadMetrics, 5000)
    return () => clearInterval(timer)
  }, [isAdmin])

  useEffect(() => { if (isAdmin) loadLogs() }, [isAdmin, logPage, logDays, logAction, logResource])

  const logTotalPages = Math.max(1, Math.ceil(logsTotal / LOG_PAGE_SIZE))
  const uniqueActions = useMemo(() => Array.from(new Set(logs.map(l => l.action))).slice(0, 30), [logs])
  const uniqueResources = useMemo(() => Array.from(new Set(logs.map(l => l.resource))).slice(0, 30), [logs])

  if (!isAdmin) return <Empty icon="🔒" title="无权限访问" description="此页面仅管理员可查看" />
  if (loading) return <Loading text="加载监控数据..." />

  return (
    <div className="space-y-6 animate-fade-in">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">📊 系统监控</h1>
          <p className="text-tertiary text-sm mt-1">
            {metrics && <>服务运行 {formatUptime(metrics.uptime_seconds)} · 进程 PID {metrics.process.pid} · {metrics.process.threads} 线程</>}
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm text-tertiary">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          实时刷新 (5s)
        </div>
      </div>

      {metrics && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <MetricCard icon="💻" label="CPU 使用率" value={`${metrics.system.cpu_percent.toFixed(1)}%`} color="from-cyan-500/20 to-blue-500/20" />
            <MetricCard icon="🧠" label="内存使用率" value={`${metrics.system.memory_percent.toFixed(1)}%`} sub={`${metrics.system.memory_available_gb.toFixed(1)}GB 可用`} color="from-purple-500/20 to-fuchsia-500/20" />
            <MetricCard icon="💾" label="磁盘使用率" value={`${metrics.system.disk_percent.toFixed(1)}%`} sub={`${metrics.system.disk_free_gb.toFixed(0)}GB 可用`} color="from-amber-500/20 to-orange-500/20" />
            <MetricCard icon="⚡" label="进程内存" value={`${metrics.process.memory_rss_mb.toFixed(0)}MB`} color="from-emerald-500/20 to-green-500/20" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="bg-card border border rounded-xl p-5">
              <h2 className="font-semibold mb-4">系统资源</h2>
              <div className="space-y-3">
                <Bar label="CPU 使用率" value={metrics.system.cpu_percent} color="cyan" />
                <Bar label="内存使用率" value={metrics.system.memory_percent} color="purple" />
                <Bar label="磁盘使用率" value={metrics.system.disk_percent} color="amber" />
              </div>
              <div className="mt-4 pt-4 border-t border grid grid-cols-2 gap-3 text-sm">
                <div><span className="text-tertiary">内存总量：</span>{metrics.system.memory_total_gb.toFixed(1)} GB</div>
                <div><span className="text-tertiary">磁盘总量：</span>{metrics.system.disk_total_gb.toFixed(0)} GB</div>
                <div><span className="text-tertiary">Python：</span>平台 {metrics.psutil_available ? '✓' : '✗'}</div>
                <div><span className="text-tertiary">线程数：</span>{metrics.process.threads}</div>
              </div>
            </div>

            <div className="bg-card border border rounded-xl p-5">
              <h2 className="font-semibold mb-4">资源趋势 (最近150s)</h2>
              <div className="h-40 relative">
                <Sparkline data={history.cpu} color="#06B6D4" label="CPU" />
                <Sparkline data={history.mem} color="#A855F7" label="内存" />
              </div>
              <div className="flex gap-4 mt-2 text-xs">
                <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-cyan-400" />CPU</span>
                <span className="flex items-center gap-1.5"><span className="w-3 h-0.5 bg-purple-400" />内存</span>
              </div>
            </div>
          </div>
        </>
      )}

      {stats && (
        <div className="bg-card border border rounded-xl p-5">
          <h2 className="font-semibold mb-4">📈 业务统计</h2>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            <StatBox label="Agent 总数" value={stats.total.agents} sub={`${stats.enabled.agents} 启用`} />
            <StatBox label="技能总数" value={stats.total.skills} />
            <StatBox label="工作流总数" value={stats.total.workflows} sub={`${stats.enabled.workflows} 启用`} />
            <StatBox label="用户总数" value={stats.total.users} />
          </div>
        </div>
      )}

      {/* ==== API 性能监控 (APM) ==== */}
      {apm && (
        <div className="bg-card border border rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold">⚡ API 性能监控 <span className="text-xs text-placeholder ml-2">最近 {Math.round(apm.window_seconds/60)} 分钟</span></h2>
            <span className="text-xs text-placeholder">缓冲区 {apm.buf_size} 条</span>
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
            <StatBox label="总请求" value={apm.total_requests} sub={`${apm.qps} QPS`} />
            <StatBox label="错误率" value={`${(apm.error_rate*100).toFixed(1)}%`} sub={`${apm.errors} 次错误`} />
            <StatBox label="平均耗时" value={`${apm.avg_ms.toFixed(0)}ms`} />
            <StatBox label="P50" value={`${apm.p50_ms.toFixed(0)}ms`} />
            <StatBox label="P95" value={`${apm.p95_ms.toFixed(0)}ms`} sub={`P99 ${apm.p99_ms.toFixed(0)}ms`} />
          </div>
          {/* 端点列表 */}
          {apm.endpoints.length > 0 && (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-tertiary uppercase tracking-wider border-b border">
                    <th className="text-left py-2 px-2">端点</th>
                    <th className="text-right py-2 px-2">调用</th>
                    <th className="text-right py-2 px-2">错误率</th>
                    <th className="text-right py-2 px-2">Avg</th>
                    <th className="text-right py-2 px-2">P50</th>
                    <th className="text-right py-2 px-2">P95</th>
                    <th className="text-right py-2 px-2">Max</th>
                  </tr>
                </thead>
                <tbody>
                  {apm.endpoints.slice(0, 15).map(ep => {
                    const errColor = ep.error_rate > 0.1 ? 'text-red-300' : ep.error_rate > 0.02 ? 'text-amber-300' : 'text-secondary'
                    const slowColor = ep.p95_ms > 1000 ? 'text-red-300' : ep.p95_ms > 300 ? 'text-amber-300' : 'text-cyan-300'
                    return (
                      <tr key={ep.key} className="border-b border hover:bg-card">
                        <td className="py-1.5 px-2">
                          <span className={`font-mono text-[10px] px-1.5 py-0.5 rounded mr-1 ${ep.method==='GET'?'bg-emerald-500/20 text-emerald-300':ep.method==='POST'?'bg-blue-500/20 text-blue-300':ep.method==='DELETE'?'bg-red-500/20 text-red-300':'bg-purple-500/20 text-brand'}`}>{ep.method}</span>
                          <span className="font-mono text-primary">{ep.path}</span>
                        </td>
                        <td className="py-1.5 px-2 text-right text-secondary">{ep.count}</td>
                        <td className={`py-1.5 px-2 text-right font-mono ${errColor}`}>{(ep.error_rate*100).toFixed(1)}%</td>
                        <td className="py-1.5 px-2 text-right font-mono text-secondary">{ep.avg_ms.toFixed(0)}ms</td>
                        <td className="py-1.5 px-2 text-right font-mono text-secondary">{ep.p50_ms.toFixed(0)}ms</td>
                        <td className={`py-1.5 px-2 text-right font-mono ${slowColor}`}>{ep.p95_ms.toFixed(0)}ms</td>
                        <td className="py-1.5 px-2 text-right font-mono text-tertiary">{ep.max_ms.toFixed(0)}ms</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
          {/* 慢请求 Top */}
          {apm.top_slow.length > 0 && (
            <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div>
                <h3 className="text-xs font-medium text-amber-300 mb-2">🐢 最近慢请求 (100ms+)</h3>
                <div className="space-y-1">
                  {apm.top_slow.slice(0,5).map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-black/20 rounded px-2 py-1">
                      <span className="font-mono truncate text-secondary">
                        <span className="text-placeholder mr-1">{s.method}</span>{s.path}
                      </span>
                      <span className="text-amber-300 font-mono shrink-0 ml-2">{s.dur_ms.toFixed(0)}ms</span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3 className="text-xs font-medium text-red-300 mb-2">❌ 最近错误</h3>
                <div className="space-y-1">
                  {apm.recent_errors.length === 0 ? (
                    <p className="text-xs text-placeholder">暂无错误</p>
                  ) : apm.recent_errors.slice(0,5).map((s, i) => (
                    <div key={i} className="flex items-center justify-between text-xs bg-black/20 rounded px-2 py-1">
                      <span className="font-mono truncate text-secondary">
                        <span className="text-red-400 mr-1">{s.status}</span>{s.method} {s.path}
                      </span>
                      <span className="text-placeholder text-[10px] shrink-0 ml-2">{s.ago.toFixed(0)}s前</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="bg-card border border rounded-xl p-5">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h2 className="font-semibold">📝 操作日志 {logsTotal > 0 && <span className="text-xs text-placeholder ml-2">共 {logsTotal} 条</span>}</h2>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <select value={logDays} onChange={e => { setLogPage(1); setLogDays(Number(e.target.value)) }}
              className="bg-hover border border rounded-md px-2 py-1 text-primary outline-none focus:border-cyan-400/50">
              <option value={1}>最近 1 天</option>
              <option value={3}>最近 3 天</option>
              <option value={7}>最近 7 天</option>
              <option value={30}>最近 30 天</option>
            </select>
            <input placeholder="按动作过滤..." value={logAction} onChange={e => { setLogPage(1); setLogAction(e.target.value) }}
              list="log-actions" className="bg-hover border border rounded-md px-2 py-1 text-primary placeholder-white/30 outline-none focus:border-cyan-400/50 w-32" />
            <datalist id="log-actions">{uniqueActions.map(a => <option key={a} value={a} />)}</datalist>
            <input placeholder="按资源过滤..." value={logResource} onChange={e => { setLogPage(1); setLogResource(e.target.value) }}
              list="log-resources" className="bg-hover border border rounded-md px-2 py-1 text-primary placeholder-white/30 outline-none focus:border-cyan-400/50 w-32" />
            <datalist id="log-resources">{uniqueResources.map(r => <option key={r} value={r} />)}</datalist>
            <button onClick={loadLogs} className="px-2 py-1 rounded-md bg-hover hover:bg-active transition-colors">🔄 刷新</button>
          </div>
        </div>
        {logsLoading && logs.length === 0 ? (
          <p className="text-placeholder text-sm text-center py-8">加载日志...</p>
        ) : logs.length === 0 ? (
          <p className="text-placeholder text-sm text-center py-8">暂无日志记录</p>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-tertiary text-xs uppercase tracking-wider border-b border">
                    <th className="text-left py-2 px-2">时间</th>
                    <th className="text-left py-2 px-2">用户</th>
                    <th className="text-left py-2 px-2">动作</th>
                    <th className="text-left py-2 px-2">资源</th>
                    <th className="text-left py-2 px-2">IP</th>
                    <th className="text-left py-2 px-2">状态</th>
                    <th className="text-right py-2 px-2"></th>
                  </tr>
                </thead>
                <tbody>
                  {logs.map(l => (
                    <tr key={l.id} className="border-b border hover:bg-card cursor-pointer transition-colors" onClick={() => setSelectedLog(l)}>
                      <td className="py-2 px-2 text-tertiary text-xs whitespace-nowrap">{new Date(l.created_at).toLocaleString()}</td>
                      <td className="py-2 px-2">{l.username || `#${l.user_id}`}</td>
                      <td className="py-2 px-2"><code className="text-cyan-300 text-xs">{l.action}</code></td>
                      <td className="py-2 px-2 text-secondary">{l.resource}{l.resource_id ? `#${l.resource_id}` : ''}</td>
                      <td className="py-2 px-2 text-placeholder text-xs font-mono">{l.ip || '-'}</td>
                      <td className="py-2 px-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full ${l.status === 'success' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>{l.status}</span>
                      </td>
                      <td className="py-2 px-2 text-right text-placeholder text-xs">详情 →</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {/* 分页 */}
            {logTotalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-4 text-sm">
                <button disabled={logPage <= 1} onClick={() => setLogPage(p => p - 1)}
                  className="px-3 py-1 rounded-md bg-hover hover:bg-active disabled:opacity-30 disabled:cursor-not-allowed transition-colors">上一页</button>
                <span className="text-tertiary">第 {logPage} / {logTotalPages} 页</span>
                <button disabled={logPage >= logTotalPages} onClick={() => setLogPage(p => p + 1)}
                  className="px-3 py-1 rounded-md bg-hover hover:bg-active disabled:opacity-30 disabled:cursor-not-allowed transition-colors">下一页</button>
              </div>
            )}
          </>
        )}
      </div>

      {/* 日志详情 Modal */}
      <Modal isOpen={!!selectedLog} onClose={() => setSelectedLog(null)} title={`日志详情 #${selectedLog?.id}`} width="max-w-3xl">
        {selectedLog && (
          <div className="space-y-4 text-sm">
            <div className="grid grid-cols-2 gap-3">
              <Info label="时间" value={new Date(selectedLog.created_at).toLocaleString()} />
              <Info label="状态" value={selectedLog.status} />
              <Info label="用户" value={`${selectedLog.username || '-'} (#${selectedLog.user_id})`} />
              <Info label="IP" value={selectedLog.ip || '-'} />
              <Info label="动作" value={<code className="text-cyan-300">{selectedLog.action}</code>} />
              <Info label="资源" value={`${selectedLog.resource}${selectedLog.resource_id ? '#' + selectedLog.resource_id : ''}`} />
            </div>
            <div>
              <div className="text-tertiary text-xs mb-2">详情 (detail)</div>
              <pre className="bg-black/40 border border rounded-lg p-3 text-xs font-mono overflow-x-auto max-h-80 whitespace-pre-wrap break-all text-emerald-200/90">
                {selectedLog.detail ? JSON.stringify(selectedLog.detail, null, 2) : '(无)'}
              </pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}

function Info({ label, value }: { label: string; value: any }) {
  return (
    <div className="bg-card rounded-lg p-2 border border">
      <div className="text-placeholder text-xs mb-0.5">{label}</div>
      <div className="text-primary text-sm">{value}</div>
    </div>
  )
}

function StatBox({ label, value, sub }: { label: string; value: number | string; sub?: string }) {
  return (
    <div className="bg-card rounded-xl p-3 text-center border border">
      <div className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">{value}</div>
      <div className="text-sm text-tertiary mt-1">{label}</div>
      {sub && <div className="text-xs text-placeholder">{sub}</div>}
    </div>
  )
}

// 极简SVG折线图
function Sparkline({ data, color, label }: { data: number[]; color: string; label: string }) {
  if (data.length < 2) return <div className="flex items-center justify-center h-full text-placeholder text-sm">收集数据中...</div>
  const w = 400, h = 140
  const max = 100
  const step = w / (data.length - 1)
  const points = data.map((v, i) => `${i * step},${h - (v / max) * h}`).join(' ')
  const area = `0,${h} ${points} ${(data.length - 1) * step},${h}`
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full h-full" preserveAspectRatio="none">
      <polygon points={area} fill={color} opacity="0.1" />
      <polyline points={points} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" />
    </svg>
  )
}
