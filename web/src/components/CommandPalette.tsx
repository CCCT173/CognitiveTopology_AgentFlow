import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { agentsApi, workflowApi, skillApi, ragApi, Agent, Workflow } from '@/api'
import { useAuthStore } from '@/store/auth'

interface CommandItem {
  id: string
  title: string
  subtitle?: string
  icon: string
  action: () => void
  group: string
}

const SHORTCUTS: Array<{ keys: string[]; desc: string; group: string }> = [
  { group: '全局', keys: ['Ctrl', 'K'], desc: '打开命令面板' },
  { group: '全局', keys: ['/'], desc: '快速唤起搜索（非输入框内）' },
  { group: '全局', keys: ['?'], desc: '显示快捷键帮助' },
  { group: '全局', keys: ['Esc'], desc: '关闭弹窗 / 取消操作' },
  { group: '命令面板', keys: ['↑', '↓'], desc: '上下切换选项' },
  { group: '命令面板', keys: ['Enter'], desc: '执行选中命令' },
  { group: '工作流编辑器', keys: ['Ctrl', 'Z'], desc: '撤销' },
  { group: '工作流编辑器', keys: ['Ctrl', 'Shift', 'Z'], desc: '重做' },
  { group: '工作流编辑器', keys: ['Delete'], desc: '删除选中节点/连线' },
  { group: '工作流编辑器', keys: ['Ctrl', 'A'], desc: '全选节点' },
  { group: '工作流编辑器', keys: ['Ctrl', 'C/V'], desc: '复制粘贴节点' },
  { group: '工作流编辑器', keys: ['Shift', '拖拽'], desc: '框选多个节点' },
]

/**
 * 全局命令面板 (Cmd/Ctrl+K 唤起)
 * - 导航到主要页面
 * - 搜索并跳转到 Agent / 工作流 / 技能 / 知识库
 */
export default function CommandPalette() {
  const token = useAuthStore(s => s.token)
  const [open, setOpen] = useState(false)
  const [showHelp, setShowHelp] = useState(false)
  const [query, setQuery] = useState('')
  const [active, setActive] = useState(0)
  const [agents, setAgents] = useState<Agent[]>([])
  const [wfs, setWfs] = useState<Workflow[]>([])
  const [skills, setSkills] = useState<any[]>([])
  const [kbs, setKbs] = useState<any[]>([])
  const [loaded, setLoaded] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const nav = useNavigate()

  // 最近访问记录 (localStorage 持久化)
  const RECENT_KEY = 'cmd_recent_v1'
  const [recent, setRecent] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
  })
  const bumpRecent = (id: string) => {
    const next = [id, ...recent.filter(x => x !== id)].slice(0, 8)
    setRecent(next)
    try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)) } catch {}
  }

  // 快捷键 (仅登录后)
  useEffect(() => {
    if (!token) return
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      const isInput = tag === 'INPUT' || tag === 'TEXTAREA' || (e.target as HTMLElement)?.isContentEditable
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault(); setShowHelp(false); setOpen(o => !o)
      } else if (e.key === '/' && !isInput) {
        e.preventDefault(); setShowHelp(false); setOpen(true)
      } else if (e.key === '?' && !isInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault(); setShowHelp(true); setOpen(false)
      } else if (e.key === 'Escape') {
        if (showHelp) setShowHelp(false)
        else setOpen(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [token, showHelp])

  // 打开时一次性加载数据 + 聚焦
  useEffect(() => {
    if (!open) return
    setQuery(''); setActive(0)
    setTimeout(() => inputRef.current?.focus(), 20)
    if (loaded) return
    Promise.all([
      agentsApi.list().catch(() => []),
      workflowApi.list().catch(() => []),
      skillApi.list().catch(() => []),
      ragApi.listKb().catch(() => []),
    ]).then(([a, w, s, k]) => { setAgents(a); setWfs(w); setSkills(s); setKbs(k); setLoaded(true) })
  }, [open, loaded])

  const navItems: CommandItem[] = useMemo(() => {
    const base: CommandItem[] = [
      { id: 'nav_home', title: '首页概览', icon: '🏠', group: '导航', action: () => nav('/') },
      { id: 'nav_agents', title: 'Agent 管理', icon: '🤖', group: '导航', action: () => nav('/agents') },
      { id: 'nav_skills', title: '技能管理', icon: '🧩', group: '导航', action: () => nav('/skills') },
      { id: 'nav_wfs', title: '工作流管理', icon: '⚡', group: '导航', action: () => nav('/workflows') },
      { id: 'nav_rag', title: '知识库', icon: '📚', group: '导航', action: () => nav('/rag') },
      { id: 'nav_groups', title: 'Agent 群组', icon: '👥', group: '导航', action: () => nav('/groups') },
      { id: 'nav_me', title: '个人中心', icon: '👤', group: '导航', action: () => nav('/me') },
    ]
    return base
  }, [nav])

  // 操作类命令：新建/跳转等动作
  const actionItems: CommandItem[] = useMemo(() => {
    return [
      { id: 'act_new_agent', title: '新建 Agent', subtitle: '创建一个新的智能体', icon: '➕', group: '操作',
        action: () => { setOpen(false); nav('/agents'); setTimeout(() => window.dispatchEvent(new CustomEvent('cmd-new-agent')), 100) } },
      { id: 'act_new_wf', title: '新建工作流', subtitle: '可视化编排流程', icon: '➕', group: '操作',
        action: () => { setOpen(false); nav('/workflows'); setTimeout(() => window.dispatchEvent(new CustomEvent('cmd-new-wf')), 100) } },
      { id: 'act_new_skill', title: '新建技能', subtitle: '创建自定义 Skill', icon: '➕', group: '操作',
        action: () => { setOpen(false); nav('/skills'); setTimeout(() => window.dispatchEvent(new CustomEvent('cmd-new-skill')), 100) } },
      { id: 'act_new_kb', title: '新建知识库', subtitle: '创建 RAG 知识库', icon: '➕', group: '操作',
        action: () => { setOpen(false); nav('/rag'); setTimeout(() => window.dispatchEvent(new CustomEvent('cmd-new-kb')), 100) } },
      { id: 'act_refresh', title: '刷新页面', subtitle: '重新加载当前页面', icon: '🔄', group: '操作',
        action: () => { setOpen(false); window.location.reload() } },
      { id: 'act_docs', title: 'API 文档', subtitle: '查看 FastAPI 接口文档', icon: '📖', group: '操作',
        action: () => { setOpen(false); window.open('/docs', '_blank') } },
      { id: 'act_help', title: '快捷键帮助', subtitle: '查看所有键盘快捷键', icon: '⌨️', group: '操作',
        action: () => { setOpen(false); setShowHelp(true) } },
    ]
  }, [nav])

  const items = useMemo<CommandItem[]>(() => {
    const arr: CommandItem[] = [...actionItems, ...navItems]
    agents.forEach(a => arr.push({
      id: `agent_${a.name}`, title: a.display_name || a.name, subtitle: `Agent · ${a.architecture}`,
      icon: '🤖', group: 'Agent', action: () => nav(`/agents/${a.name}`),
    }))
    wfs.forEach(w => arr.push({
      id: `wf_${w.id}`, title: w.display_name || w.name, subtitle: `工作流 · ${w.category || '未分类'}`,
      icon: '⚡', group: '工作流', action: () => nav(`/workflows/${w.id}`),
    }))
    skills.forEach(s => arr.push({
      id: `sk_${s.id}`, title: s.display_name || s.name, subtitle: `技能 · ${s.category || ''}`,
      icon: '🧩', group: '技能', action: () => nav('/skills'),
    }))
    kbs.forEach(k => arr.push({
      id: `kb_${k.id}`, title: k.name, subtitle: `知识库 · ${k.document_count || 0} 文档`,
      icon: '📚', group: '知识库', action: () => nav(`/rag/${k.id}`),
    }))
    let result = arr
    if (!query.trim()) {
      // 无搜索词：最近访问的项独立成组置顶
      const recentItems = recent.map(rid => arr.find(x => x.id === rid)).filter(Boolean).map(x => ({ ...(x as CommandItem), group: '最近访问' })) as CommandItem[]
      const otherItems = arr.filter(x => !recent.includes(x.id))
      result = [...recentItems, ...otherItems]
    } else {
      const q = query.toLowerCase()
      const recentIdx = new Map(recent.map((id, i) => [id, recent.length - i]))
      const scored: Array<{ item: CommandItem; score: number; recency: number }> = []
      for (const i of arr) {
        const t = i.title.toLowerCase(); const s = (i.subtitle || '').toLowerCase(); const g = i.group.toLowerCase()
        let score = 0
        if (t.startsWith(q)) score = 100
        else if (t.includes(q)) score = 60
        else if (s.includes(q)) score = 30
        else if (g.includes(q)) score = 10
        const recency = recentIdx.get(i.id) ?? 0
        // 最近访问加权：按访问顺序线性加成 (最近一条+8，依次递减)
        score += recency * 2
        if (score > 0) scored.push({ item: i, score, recency })
      }
      // 先按 score 降序，同分时按 recency 降序（最近访问优先）
      scored.sort((a, b) => b.score - a.score || b.recency - a.recency)
      result = scored.map(x => x.item)
    }
    return result
  }, [navItems, agents, wfs, skills, kbs, query, nav, recent])

  const grouped = useMemo(() => {
    const m = new Map<string, CommandItem[]>()
    items.forEach(i => { if (!m.has(i.group)) m.set(i.group, []); m.get(i.group)!.push(i) })
    return Array.from(m.entries())
  }, [items])

  // 键盘导航
  const onListKey = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive(a => Math.min(items.length - 1, a + 1)) }
    else if (e.key === 'ArrowUp') { e.preventDefault(); setActive(a => Math.max(0, a - 1)) }
    else if (e.key === 'Enter') {
      e.preventDefault()
      const it = items[active]
      if (it) { bumpRecent(it.id); it.action(); setOpen(false) }
    }
  }

  if (!open && !showHelp) {
    // 未登录不显示悬浮按钮
    if (!token) return null
    // 底部悬浮按钮 (小型触发器)
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-5 right-5 z-40 w-11 h-11 rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 text-primary shadow-lg shadow-purple-500/30 hover:scale-110 transition-transform flex items-center justify-center text-lg"
        title="命令面板 (Ctrl+K) · 按 ? 查看快捷键"
      >
        🔍
      </button>
    )
  }

  if (showHelp) {
    const groups = Array.from(new Set(SHORTCUTS.map(s => s.group)))
    return (
      <div className="fixed inset-0 z-[80] bg-black/60  flex items-start justify-center pt-[10vh] p-4" onClick={() => setShowHelp(false)}>
        <div className="w-full max-w-2xl bg-card/95 border border rounded-2xl shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
          <div className="flex items-center justify-between px-5 py-3 border-b border">
            <div className="flex items-center gap-2">
              <span className="text-tertiary">⌨️</span>
              <h2 className="text-base font-semibold">键盘快捷键</h2>
            </div>
            <button onClick={() => setShowHelp(false)} className="text-tertiary hover:text-primary text-xl leading-none">×</button>
          </div>
          <div className="p-5 max-h-[70vh] overflow-y-auto grid md:grid-cols-2 gap-5">
            {groups.map(g => (
              <div key={g}>
                <div className="text-[11px] uppercase tracking-wider text-placeholder mb-2">{g}</div>
                <div className="space-y-1.5">
                  {SHORTCUTS.filter(s => s.group === g).map((s, i) => (
                    <div key={i} className="flex items-center justify-between gap-3 text-sm">
                      <span className="text-secondary">{s.desc}</span>
                      <span className="flex gap-1 shrink-0">
                        {s.keys.map((k, j) => (
                          <kbd key={j} className="px-1.5 py-0.5 rounded text-[11px] bg-hover border border text-primary font-mono min-w-[22px] text-center">{k}</kbd>
                        ))}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
          <div className="px-5 py-2.5 border-t border text-[11px] text-placeholder text-center">按 Esc 或点击外部关闭</div>
        </div>
      </div>
    )
  }

  return (
    <div className="fixed inset-0 z-[80] bg-black/60  flex items-start justify-center pt-[12vh] p-4" onClick={() => setOpen(false)}>
      <div className="w-full max-w-xl bg-card/95 border border rounded-2xl shadow-lg overflow-hidden" onClick={e => e.stopPropagation()}>
        <div className="flex items-center gap-3 px-4 py-3 border-b border">
          <span className="text-tertiary">🔍</span>
          <input
            ref={inputRef}
            value={query}
            onChange={e => { setQuery(e.target.value); setActive(0) }}
            onKeyDown={onListKey}
            placeholder="搜索 Agent / 工作流 / 技能 / 知识库, 或输入命令..."
            className="flex-1 bg-transparent outline-none text-sm placeholder:text-placeholder"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-hover text-tertiary border border">ESC</kbd>
        </div>
        <div className="max-h-[50vh] overflow-y-auto py-2">
          {items.length === 0 ? (
            <div className="py-12 text-center text-placeholder text-sm">没有匹配结果</div>
          ) : (
            grouped.map(([group, list]) => {
              // 计算该 group 在整体 items 中的起止 index
              const startIdx = items.findIndex(x => x.id === list[0].id)
              return (
                <div key={group}>
                  <div className="px-4 py-1.5 text-[11px] uppercase tracking-wider text-placeholder">{group}</div>
                  {list.map((it, i) => {
                    const idx = startIdx + i
                    const isActive = idx === active
                    return (
                      <button key={it.id}
                        onMouseEnter={() => setActive(idx)}
                        onClick={() => { bumpRecent(it.id); it.action(); setOpen(false) }}
                        className={`w-full flex items-center gap-3 px-4 py-2.5 text-left text-sm transition-colors ${isActive ? 'bg-hover' : 'hover:bg-card'}`}>
                        <span className="text-lg">{it.icon}</span>
                        <div className="min-w-0 flex-1">
                          <div className="truncate">{it.title}</div>
                          {it.subtitle && <div className="text-xs text-placeholder truncate">{it.subtitle}</div>}
                        </div>
                        {isActive && <span className="text-placeholder text-xs">↵</span>}
                      </button>
                    )
                  })}
                </div>
              )
            })
          )}
        </div>
        <div className="px-4 py-2 border-t border flex items-center justify-between text-[11px] text-placeholder">
          <div className="flex gap-3">
            <span>↑↓ 选择</span><span>↵ 执行</span><span>Ctrl+K 切换</span>
            {recent.length > 0 && !query.trim() && (
              <button onClick={() => { setRecent([]); try { localStorage.removeItem(RECENT_KEY) } catch {} }}
                className="hover:text-secondary transition">清除历史</button>
            )}
          </div>
          <span>{items.length} 个结果</span>
        </div>
      </div>
    </div>
  )
}
