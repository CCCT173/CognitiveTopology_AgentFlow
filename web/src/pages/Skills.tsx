import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { skillApi, Skill, SkillCategory } from '@/api'
import Button from '@/components/ui/Button'
import Badge from '@/components/ui/Badge'
import SkillForm from '@/components/skills/SkillForm'
import SkillTestPanel from '@/components/skills/SkillTestPanel'
import SkillImportModal from '@/components/skills/SkillImportModal'

type ViewMode = 'card' | 'table'

export default function Skills() {
  const [skills, setSkills] = useState<Skill[]>([])
  const [categories, setCategories] = useState<SkillCategory[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [category, setCategory] = useState<string>('')
  const [tag, setTag] = useState<string>('')
  const [activeOnly, setActiveOnly] = useState(false)
  const [viewMode, setViewMode] = useState<ViewMode>('card')

  const [editing, setEditing] = useState<Skill | null>(null)
  const [formOpen, setFormOpen] = useState(false)
  const [testSkill, setTestSkill] = useState<Skill | null>(null)
  const [importOpen, setImportOpen] = useState(false)

  const allTags = useMemo(() => {
    const set = new Set<string>()
    skills.forEach(s => (s.tags || []).forEach(t => set.add(t)))
    return Array.from(set)
  }, [skills])

  const load = async () => {
    setLoading(true)
    try {
      const [ls, cs] = await Promise.all([
        skillApi.list({
          keyword: keyword || undefined,
          category: category || undefined,
          tag: tag || undefined,
          is_active: activeOnly || undefined,
        }),
        skillApi.categories(),
      ])
      setSkills(ls); setCategories(cs)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [keyword, category, tag, activeOnly])

  // 命令面板事件监听
  useEffect(() => {
    const h = () => { setEditing(null); setFormOpen(true) }
    window.addEventListener('cmd-new-skill', h)
    return () => window.removeEventListener('cmd-new-skill', h)
  }, [])

  const onToggle = async (s: Skill) => {
    if (s.is_builtin) { toast.error('内置技能不可修改状态'); return }
    await skillApi.toggle(s.id, !s.is_active); toast.success(s.is_active ? '已禁用' : '已启用'); load()
  }
  const onDelete = async (s: Skill) => {
    if (s.is_builtin) { toast.error('内置技能不可删除'); return }
    if (!confirm(`确定删除技能 "${s.name}"?`)) return
    await skillApi.remove(s.id); toast.success('已删除'); load()
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold">🧩 技能管理</h1>
          <p className="text-tertiary text-sm mt-1">管理可复用的 Skill 技能包，支持导入、编辑和测试运行</p>
        </div>
        <div className="flex gap-2">
          <Button variant="secondary" onClick={() => setImportOpen(true)}>📥 导入技能</Button>
          <Button onClick={() => { setEditing(null); setFormOpen(true) }}>➕ 新建技能</Button>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="glass-card p-4 flex flex-wrap gap-3 items-center">
        <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索技能名称/描述..."
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-hover border border focus:outline-none focus:border-brand" />
        <select value={category} onChange={e => setCategory(e.target.value)}
          className="px-3 py-2 rounded-lg bg-hover border border focus:outline-none">
          <option value="">全部分类</option>
          {categories.map(c => <option key={c.category} value={c.category}>{c.category} ({c.count})</option>)}
        </select>
        <select value={tag} onChange={e => setTag(e.target.value)}
          className="px-3 py-2 rounded-lg bg-hover border border focus:outline-none">
          <option value="">全部标签</option>
          {allTags.map(t => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
          <input type="checkbox" checked={activeOnly} onChange={e => setActiveOnly(e.target.checked)} />
          仅看已启用
        </label>
        <div className="flex bg-card rounded-lg p-0.5 ml-auto">
          <button onClick={() => setViewMode('card')}
            className={`px-3 py-1.5 rounded-md text-sm transition ${viewMode === 'card' ? 'bg-active' : 'text-tertiary'}`}>
            🎴 卡片
          </button>
          <button onClick={() => setViewMode('table')}
            className={`px-3 py-1.5 rounded-md text-sm transition ${viewMode === 'table' ? 'bg-active' : 'text-tertiary'}`}>
            📋 表格
          </button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="glass-card p-4 animate-pulse">
              <div className="h-5 bg-hover rounded w-2/3 mb-3" />
              <div className="h-4 bg-card rounded w-full mb-2" />
              <div className="h-4 bg-card rounded w-3/4" />
            </div>
          ))}
        </div>
      ) : viewMode === 'card' ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {skills.map(s => (
            <div key={s.id} className="glass-card p-4 group">
              <div className="flex items-start justify-between mb-2">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="font-semibold truncate">{s.name}</span>
                    {s.is_builtin && <Badge variant="info" className="text-xs">内置</Badge>}
                    <Badge variant={s.is_active ? 'success' : 'warning'} className="text-xs">
                      {s.is_active ? '启用' : '禁用'}
                    </Badge>
                  </div>
                  <p className="text-xs text-placeholder mt-0.5">v{s.version || '1.0.0'} · {s.author || 'unknown'}</p>
                </div>
                <button onClick={() => onToggle(s)}
                  className={`w-10 h-5 rounded-full transition shrink-0 ${s.is_active ? 'bg-emerald-500/60' : 'bg-hover'}`}>
                  <div className={`w-4 h-4 bg-white rounded-full transition ${s.is_active ? 'ml-5' : 'ml-0.5'}`} />
                </button>
              </div>
              <p className="text-sm text-secondary line-clamp-2 min-h-[2.5rem]">{s.description || '无描述'}</p>
              {s.category && (
                <Badge variant="primary" className="mt-2 text-xs mr-1">{s.category}</Badge>
              )}
              {(s.tags || []).slice(0, 3).map(t => (
                <span key={t} className="text-xs px-2 py-0.5 rounded bg-card text-tertiary mr-1">{t}</span>
              ))}
              <div className="text-xs text-placeholder mt-2">使用 {s.usage_count} 次</div>
              <div className="flex gap-2 mt-3 pt-3 border-t border">
                <button onClick={() => setTestSkill(s)}
                  className="flex-1 py-1.5 text-sm rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30">测试</button>
                <button onClick={() => { setEditing(s); setFormOpen(true) }}
                  disabled={s.is_builtin}
                  className="px-3 py-1.5 text-sm rounded bg-card hover:bg-hover disabled:opacity-40 disabled:cursor-not-allowed">编辑</button>
                <button onClick={() => onDelete(s)}
                  disabled={s.is_builtin}
                  className="px-3 py-1.5 text-sm rounded text-red-400 hover:bg-red-500/20 disabled:opacity-40 disabled:cursor-not-allowed">删除</button>
              </div>
            </div>
          ))}
          {skills.length === 0 && (
            <div className="col-span-full text-center py-16 text-placeholder">
              <div className="text-5xl mb-3">🧩</div>
              <p>暂无技能，点击"新建技能"或"导入技能"开始</p>
            </div>
          )}
        </div>
      ) : (
        <div className="glass-card overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-card text-tertiary text-left">
              <tr>
                <th className="px-4 py-3 font-medium">名称</th>
                <th className="px-4 py-3 font-medium">分类</th>
                <th className="px-4 py-3 font-medium">版本</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">使用次数</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {skills.map(s => (
                <tr key={s.id} className="border-t border hover:bg-card">
                  <td className="px-4 py-3">
                    <div className="font-medium">{s.name}</div>
                    <div className="text-xs text-placeholder">{s.description}</div>
                  </td>
                  <td className="px-4 py-3 text-tertiary">{s.category || '-'}</td>
                  <td className="px-4 py-3 text-tertiary">{s.version || '1.0.0'}</td>
                  <td className="px-4 py-3">
                    {s.is_builtin && <Badge variant="info" className="text-xs mr-1">内置</Badge>}
                    <Badge variant={s.is_active ? 'success' : 'warning'} className="text-xs">
                      {s.is_active ? '启用' : '禁用'}
                    </Badge>
                  </td>
                  <td className="px-4 py-3 text-tertiary">{s.usage_count}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <button onClick={() => setTestSkill(s)} className="px-2 py-1 text-xs rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30">测试</button>
                      <button onClick={() => { setEditing(s); setFormOpen(true) }} disabled={s.is_builtin}
                        className="px-2 py-1 text-xs rounded bg-card hover:bg-hover disabled:opacity-40">编辑</button>
                      <button onClick={() => onDelete(s)} disabled={s.is_builtin}
                        className="px-2 py-1 text-xs rounded text-red-400 hover:bg-red-500/20 disabled:opacity-40">删除</button>
                    </div>
                  </td>
                </tr>
              ))}
              {skills.length === 0 && (
                <tr><td colSpan={6} className="text-center py-12 text-placeholder">暂无技能</td></tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {formOpen && (
        <SkillForm skill={editing} categories={categories.map(c => c.category)}
          onClose={() => setFormOpen(false)} onSaved={() => { setFormOpen(false); load() }} />
      )}
      {testSkill && (
        <SkillTestPanel skill={testSkill} onClose={() => setTestSkill(null)} />
      )}
      {importOpen && (
        <SkillImportModal onClose={() => setImportOpen(false)} onImported={() => { setImportOpen(false); load() }} />
      )}
    </div>
  )
}
