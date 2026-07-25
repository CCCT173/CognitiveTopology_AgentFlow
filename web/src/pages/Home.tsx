import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentsApi, ragApi, workflowApi, groupApi, chatApi, skillApi, systemApi, ChatThread, SysMetrics, DashboardData } from '@/api'
import { useAuthStore } from '@/store/auth'

function formatUptime(sec: number) {
  const d = Math.floor(sec / 86400), h = Math.floor((sec % 86400) / 3600), m = Math.floor((sec % 3600) / 60)
  if (d) return `${d}天 ${h}小时`
  if (h) return `${h}小时 ${m}分`
  return `${m}分钟`
}

function fmtMs(ms: number) {
  if (!ms) return '—'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}

function MiniBar({ label, value, max = 100, unit = '%' }: { label: string; value: number; max?: number; unit?: string }) {
  const pct = Math.min(100, (value / max) * 100)
  const warn = pct > 80
  return (
    <div>
      <div className="flex items-center justify-between text-xs mb-1.5">
        <span className="text-tertiary">{label}</span>
        <span className={warn ? 'text-warning font-medium' : 'text-primary font-medium'}>{value.toFixed(1)}{unit}</span>
      </div>
      <div className="h-1.5 rounded-full bg-hover overflow-hidden">
        <div className={`h-full rounded-full transition-all duration-500 ${warn ? 'bg-warning' : 'bg-brand'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

function TrendChart({ data }: { data: DashboardData['wf_trend'] }) {
  const W = 480, H = 160, pad = { l: 30, r: 10, t: 16, b: 24 }
  const iw = W - pad.l - pad.r, ih = H - pad.t - pad.b
  const max = Math.max(1, ...data.map(d => d.success + d.failed))
  const bw = iw / data.length * 0.6
  const gap = iw / data.length
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full h-auto">
      {[0, 0.25, 0.5, 0.75, 1].map(r => {
        const y = pad.t + ih * (1 - r)
        return <line key={r} x1={pad.l} y1={y} x2={W - pad.r} y2={y} stroke="#EAECEF" strokeWidth={1} />
      })}
      {[0, 0.5, 1].map(r => {
        const y = pad.t + ih * (1 - r)
        return <text key={r} x={pad.l - 6} y={y + 3} textAnchor="end" fontSize={10} fill="#9AA2B8">{Math.round(max * r)}</text>
      })}
      {data.map((d, i) => {
        const x = pad.l + gap * i + (gap - bw) / 2
        const totalH = (ih * (d.success + d.failed)) / max
        const succH = (ih * d.success) / max
        return (
          <g key={d.date}>
            {d.failed > 0 && (
              <rect x={x} y={pad.t + ih - totalH} width={bw} height={totalH - succH} rx={2} fill="#F04438" opacity={0.7} />
            )}
            {d.success > 0 && (
              <rect x={x} y={pad.t + ih - succH} width={bw} height={succH} rx={2} fill="#2970FF" />
            )}
            {(d.success + d.failed) === 0 && (
              <rect x={x} y={pad.t + ih - 2} width={bw} height={2} rx={1} fill="#EAECEF" />
            )}
            <text x={x + bw / 2} y={H - 6} textAnchor="middle" fontSize={10} fill="#9AA2B8">{d.date}</text>
          </g>
        )
      })}
    </svg>
  )
}

function RingChart({ rate, size = 96 }: { rate: number; size?: number }) {
  const r = size / 2 - 8
  const c = 2 * Math.PI * r
  const off = c * (1 - rate / 100)
  const color = rate >= 90 ? '#079455' : rate >= 70 ? '#2970FF' : rate >= 40 ? '#DC6803' : '#D92D20'
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} stroke="#EAECEF" strokeWidth={8} fill="none" />
      <circle cx={size / 2} cy={size / 2} r={r} stroke={color} strokeWidth={8} fill="none"
        strokeDasharray={c} strokeDashoffset={off} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: 'stroke-dashoffset 0.6s ease' }} />
      <text x={size / 2} y={size / 2 + 2} textAnchor="middle" fontSize={size * 0.22} fontWeight={700} fill="#0F1528">{rate.toFixed(1)}%</text>
      <text x={size / 2} y={size / 2 + size * 0.2} textAnchor="middle" fontSize={size * 0.11} fill="#9AA2B8">成功率</text>
    </svg>
  )
}

function StatusDot({ status }: { status: string }) {
  const map: Record<string, string> = {
    success: 'dot-green', failed: 'dot-red', running: 'dot-blue animate-pulse',
  }
  return <span className={`inline-block dot ${map[status] || 'dot-gray'}`} />
}

export default function Home() {
  const nav = useNavigate()
  const user = useAuthStore(s => s.user)
  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin'
  const [counts, setCounts] = useState({ agents: 0, kbs: 0, wfs: 0, groups: 0, skills: 0 })
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [metrics, setMetrics] = useState<SysMetrics | null>(null)
  const [dash, setDash] = useState<DashboardData | null>(null)

  useEffect(() => {
    Promise.all([agentsApi.list(), ragApi.listKb(), workflowApi.list(), groupApi.list(), skillApi.list()]).then(
      ([as, ks, ws, gs, ss]) => setCounts({ agents: as.length, kbs: ks.length, wfs: ws.length, groups: gs.length, skills: ss.length })
    ).catch(() => {})
    chatApi.threads().then(setThreads).catch(() => {})
    if (isAdmin) {
      systemApi.metrics().then(setMetrics).catch(() => {})
      systemApi.dashboard().then(setDash).catch(() => {})
      const t1 = setInterval(() => systemApi.metrics().then(setMetrics).catch(() => {}), 10000)
      const t2 = setInterval(() => systemApi.dashboard().then(setDash).catch(() => {}), 30000)
      return () => { clearInterval(t1); clearInterval(t2) }
    }
  }, [isAdmin])

  const cards = [
    { title: 'Agent', value: counts.agents, icon: '🤖', to: '/agents' },
    { title: '技能', value: counts.skills, icon: '🧩', to: '/skills' },
    { title: '工作流', value: counts.wfs, icon: '⚡', to: '/workflows' },
    { title: '知识库', value: counts.kbs, icon: '📚', to: '/rag' },
    { title: '群组', value: counts.groups, icon: '👥', to: '/groups' },
  ]

  return (
    <div className="p-6 space-y-6 animate-fadeIn">
      {/* 头部欢迎区 */}
      <div className="flex items-end justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-primary">欢迎回来，{user?.username || '用户'} 👋</h1>
          <p className="text-tertiary mt-1 text-sm">你的 AI 工作站已就绪</p>
        </div>
        {metrics && (
          <div className="flex items-center gap-2 text-xs text-tertiary">
            <span className="dot dot-green" />
            服务运行 {formatUptime(metrics.uptime_seconds)} · 内存 {metrics.process.memory_rss_mb.toFixed(0)}MB
          </div>
        )}
      </div>

      {/* 资源统计卡片 */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-4">
        {cards.map(c => (
          <div key={c.title} onClick={() => nav(c.to)}
            className="card cursor-pointer p-5 group">
            <div className="text-3xl mb-3 group-hover:scale-110 transition-transform duration-200">{c.icon}</div>
            <div className="text-3xl font-bold text-primary">{c.value}</div>
            <div className="text-tertiary text-sm mt-0.5">{c.title}</div>
          </div>
        ))}
      </div>

      {/* 管理员：工作流数据看板 */}
      {isAdmin && dash && (
        <>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* 工作流统计 */}
            <div className="card p-5 flex flex-col items-center justify-center">
              <h3 className="text-sm font-medium text-secondary mb-3 self-start flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">🎯</span>
                工作流运行
              </h3>
              <div className="flex items-center gap-5">
                <RingChart rate={dash.wf_stats.success_rate} />
                <div className="space-y-2 text-sm">
                  <div className="flex items-center gap-2">
                    <span className="dot dot-green" />
                    <span className="text-tertiary">成功</span>
                    <span className="font-semibold text-primary">{dash.wf_stats.success}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="dot dot-red" />
                    <span className="text-tertiary">失败</span>
                    <span className="font-semibold text-primary">{dash.wf_stats.failed}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="dot dot-blue animate-pulse" />
                    <span className="text-tertiary">运行中</span>
                    <span className="font-semibold text-primary">{dash.wf_stats.running}</span>
                  </div>
                  <div className="divider" />
                  <div className="text-tertiary text-xs">总运行 <b className="text-primary">{dash.wf_stats.total}</b> 次</div>
                </div>
              </div>
              <div className="grid grid-cols-3 gap-2 w-full mt-4 text-center">
                {[
                  { label: '平均', value: fmtMs(dash.wf_stats.avg_ms) },
                  { label: 'P50', value: fmtMs(dash.wf_stats.p50_ms) },
                  { label: 'P95', value: fmtMs(dash.wf_stats.p95_ms) },
                ].map(s => (
                  <div key={s.label} className="bg-subtle rounded-lg p-2.5">
                    <div className="text-xs text-tertiary">{s.label}</div>
                    <div className="text-sm font-semibold text-primary mt-0.5">{s.value}</div>
                  </div>
                ))}
              </div>
            </div>

            {/* 7日趋势 */}
            <div className="lg:col-span-2 card p-5">
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-sm font-medium text-secondary flex items-center gap-2">
                  <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">📈</span>
                  近 7 日运行趋势
                </h3>
                <div className="flex items-center gap-3 text-xs text-tertiary">
                  <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-brand" />成功</span>
                  <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm bg-danger/70" />失败</span>
                </div>
              </div>
              <TrendChart data={dash.wf_trend} />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {/* 热门工作流 */}
            <div className="card p-5">
              <h3 className="text-sm font-medium text-secondary mb-3 flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">🏆</span>
                热门工作流 TOP5
              </h3>
              {dash.wf_top.length === 0 ? (
                <p className="text-placeholder text-sm py-6 text-center">暂无运行记录</p>
              ) : (
                <div className="space-y-1">
                  {dash.wf_top.map((w, i) => (
                    <div key={w.id} onClick={() => nav(`/workflows/${w.id}`)}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-hover cursor-pointer transition">
                      <span className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold ${
                        i === 0 ? 'bg-warning/10 text-warning' : i === 1 ? 'bg-hover text-secondary' : i === 2 ? 'bg-warning/10 text-warning/70' : 'bg-hover text-tertiary'
                      }`}>{i + 1}</span>
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-primary truncate">{w.name}</div>
                        <div className="text-xs text-tertiary">平均 {fmtMs(w.avg_ms)}</div>
                      </div>
                      <div className="text-right shrink-0">
                        <div className="text-sm font-semibold text-primary">{w.runs}</div>
                        <div className="text-xs text-success">{w.success}✓</div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* 热门Agent */}
            <div className="card p-5">
              <h3 className="text-sm font-medium text-secondary mb-3 flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">🔥</span>
                热门 Agent TOP5
              </h3>
              {dash.agent_top.length === 0 ? (
                <p className="text-placeholder text-sm py-6 text-center">暂无对话</p>
              ) : (
                <div className="space-y-1">
                  {dash.agent_top.map((a, i) => (
                    <div key={a.name} onClick={() => nav(`/agents/${a.name}`)}
                      className="flex items-center gap-3 p-2 rounded-lg hover:bg-hover cursor-pointer transition">
                      <span className={`w-6 h-6 rounded-md flex items-center justify-center text-xs font-bold ${
                        i === 0 ? 'bg-danger/10 text-danger' : 'bg-hover text-tertiary'
                      }`}>{i + 1}</span>
                      <div className="min-w-0 flex-1 text-sm font-medium text-primary truncate">{a.name}</div>
                      <div className="text-sm text-tertiary shrink-0">{a.msgs} 条</div>
                    </div>
                  ))}
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 mt-4 pt-3 border-t border">
                <div className="text-center">
                  <div className="text-xs text-tertiary">总消息</div>
                  <div className="text-lg font-bold text-brand mt-0.5">{dash.agent_stats.messages}</div>
                </div>
                <div className="text-center">
                  <div className="text-xs text-tertiary">对话数</div>
                  <div className="text-lg font-bold text-brand mt-0.5">{dash.agent_stats.threads}</div>
                </div>
              </div>
            </div>

            {/* 最近运行 */}
            <div className="card p-5">
              <h3 className="text-sm font-medium text-secondary mb-3 flex items-center gap-2">
                <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">⏱️</span>
                最近运行
              </h3>
              {dash.recent_runs.length === 0 ? (
                <p className="text-placeholder text-sm py-6 text-center">暂无运行记录</p>
              ) : (
                <div className="space-y-1">
                  {dash.recent_runs.slice(0, 6).map(r => (
                    <div key={r.run_id} onClick={() => nav(`/workflows/${r.workflow_id}`)}
                      className="flex items-center gap-2 p-2 rounded-lg hover:bg-hover cursor-pointer transition">
                      <StatusDot status={r.status} />
                      <div className="min-w-0 flex-1">
                        <div className="text-sm font-medium text-primary truncate">{r.workflow_name || `WF#${r.workflow_id}`}</div>
                        <div className="text-xs text-tertiary">{new Date(r.created_at).toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })}</div>
                      </div>
                      <div className="text-xs text-tertiary shrink-0">{fmtMs(r.elapsed_ms)}</div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* 系统监控 */}
          {metrics && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
              <div className="lg:col-span-2 card p-5">
                <h2 className="text-lg font-semibold text-primary mb-4 flex items-center gap-2">
                  <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">📊</span>
                  系统监控
                </h2>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-3">
                    <MiniBar label="CPU 使用率" value={metrics.system.cpu_percent} />
                    <MiniBar label="内存使用率" value={metrics.system.memory_percent} />
                    <MiniBar label="磁盘使用率" value={metrics.system.disk_percent} max={100} unit="%" />
                  </div>
                  <div className="space-y-2 text-sm">
                    <div className="flex justify-between"><span className="text-tertiary">内存总量</span><span className="text-primary">{metrics.system.memory_total_gb.toFixed(1)} GB</span></div>
                    <div className="flex justify-between"><span className="text-tertiary">可用内存</span><span className="text-success">{metrics.system.memory_available_gb.toFixed(1)} GB</span></div>
                    <div className="flex justify-between"><span className="text-tertiary">磁盘总量</span><span className="text-primary">{metrics.system.disk_total_gb.toFixed(0)} GB</span></div>
                    <div className="flex justify-between"><span className="text-tertiary">磁盘可用</span><span className="text-success">{metrics.system.disk_free_gb.toFixed(0)} GB</span></div>
                    <div className="divider" />
                    <div className="flex justify-between"><span className="text-tertiary">进程PID</span><span className="text-primary">{metrics.process.pid}</span></div>
                    <div className="flex justify-between"><span className="text-tertiary">进程内存</span><span className="text-primary">{metrics.process.memory_rss_mb.toFixed(0)} MB</span></div>
                    <div className="flex justify-between"><span className="text-tertiary">线程数</span><span className="text-primary">{metrics.process.threads}</span></div>
                  </div>
                </div>
              </div>
              <div className="card p-5">
                <h2 className="text-lg font-semibold text-primary mb-4 flex items-center gap-2">
                  <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">📡</span>
                  业务规模
                </h2>
                <div className="space-y-3">
                  {[
                    { label: 'Agent 总数', value: counts.agents },
                    { label: '技能总数', value: counts.skills },
                    { label: '工作流总数', value: counts.wfs },
                    { label: '知识库总数', value: counts.kbs },
                    { label: '群组总数', value: counts.groups },
                  ].map(s => (
                    <div key={s.label} className="flex items-center justify-between">
                      <div className="text-sm text-tertiary">{s.label}</div>
                      <div className="text-2xl font-bold text-brand">{s.value}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* 最近对话 */}
      <div className="card p-5">
        <h2 className="text-lg font-semibold text-primary mb-4 flex items-center gap-2">
          <span className="w-4 h-4 rounded bg-brand/10 flex items-center justify-center text-brand text-xs">💬</span>
          最近对话
        </h2>
        {threads.length === 0 ? (
          <p className="text-tertiary text-sm">还没有对话，<button className="text-brand hover:underline" onClick={() => nav('/agents')}>去和 Agent 聊聊 →</button></p>
        ) : (
          <div className="space-y-1">
            {threads.slice(0, 6).map(t => (
              <div key={t.thread_id} onClick={() => nav(`/agents/${t.agent_name}`)}
                className="p-3 rounded-lg hover:bg-hover cursor-pointer flex items-center justify-between transition">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-primary truncate">{t.title || '新对话'}</div>
                  <div className="text-xs text-tertiary truncate mt-0.5">{t.agent_name} · {t.last_message?.slice(0, 60) || '暂无消息'}</div>
                </div>
                <span className="text-placeholder text-xs shrink-0 ml-3">{new Date(t.updated_at).toLocaleDateString()}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
