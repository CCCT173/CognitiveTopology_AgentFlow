import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { agentsApi, ragApi, workflowApi, Agent, KB, Workflow } from '@/api'
import { useMetaStore } from '@/store/meta'
import Empty from '@/components/ui/Empty'
import Modal from '@/components/ui/Modal'

interface AgentTemplate {
  id: string; name: string; display_name: string; description: string; category: string; icon: string
}

const archBadge: Record<string, { label: string; cls: string }> = {
  single: { label: '单 Agent', cls: 'badge-blue' },
  react: { label: 'ReAct', cls: 'badge-blue' },
  workflow: { label: '工作流', cls: 'badge-yellow' },
  skill: { label: 'Skill 代理', cls: 'badge-green' },
}

export default function Agents() {
  const nav = useNavigate()
  const { architectures, tools } = useMetaStore()
  const [agents, setAgents] = useState<Agent[]>([])
  const [kbs, setKbs] = useState<KB[]>([])
  const [wfs, setWfs] = useState<Workflow[]>([])
  const [loading, setLoading] = useState(true)
  const [keyword, setKeyword] = useState('')
  const [enabledOnly, setEnabledOnly] = useState(false)
  const [editing, setEditing] = useState<Agent | null>(null)
  const [showModal, setShowModal] = useState(false)
  const [showTpl, setShowTpl] = useState(false)
  const [templates, setTemplates] = useState<AgentTemplate[]>([])
  const [loadingTpl, setLoadingTpl] = useState(false)

  const openTemplates = async () => {
    setShowTpl(true)
    if (templates.length === 0) {
      setLoadingTpl(true)
      try { setTemplates(await agentsApi.templates()) } catch { toast.error('加载模板失败') }
      finally { setLoadingTpl(false) }
    }
  }

  const useTemplate = async (t: AgentTemplate) => {
    try {
      const a = await agentsApi.fromTemplate({ template_id: t.id })
      toast.success(`已基于「${t.display_name}」创建 Agent`)
      setShowTpl(false)
      load()
      nav(`/agents/${a.name}`)
    } catch (e: any) { toast.error(e?.response?.data?.detail || '创建失败') }
  }

  const load = async () => {
    setLoading(true)
    try {
      const [as, ks, ws] = await Promise.all([
        agentsApi.list({ keyword: keyword || undefined, enabled_only: enabledOnly || undefined }),
        ragApi.listKb(), workflowApi.list(),
      ])
      setAgents(as); setKbs(ks); setWfs(ws)
    } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [keyword, enabledOnly])

  const openCreate = () => { setEditing(null); setShowModal(true) }
  const openEdit = (a: Agent) => { setEditing(a); setShowModal(true) }

  useEffect(() => {
    const h = () => openCreate()
    window.addEventListener('cmd-new-agent', h)
    return () => window.removeEventListener('cmd-new-agent', h)
  }, [])

  const onDelete = async (a: Agent) => {
    if (!confirm(`确定删除 Agent "${a.display_name||a.name}"?`)) return
    await agentsApi.remove(a.name); toast.success('已删除'); load()
  }
  const onToggle = async (a: Agent) => {
    await agentsApi.toggle(a.name, !a.enabled); load()
  }

  return (
    <div className="p-6 space-y-5 animate-fadeIn">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-primary">Agent 管理</h1>
          <p className="text-tertiary text-sm mt-1">创建和管理你的智能助手，支持多种架构和工具调用</p>
        </div>
        <div className="flex gap-2">
          <button onClick={openTemplates} className="btn btn-secondary">
            📋 从模板创建
          </button>
          <button onClick={openCreate} className="btn btn-primary">
            ➕ 新建 Agent
          </button>
        </div>
      </div>

      {/* 筛选栏 */}
      <div className="card p-3 flex gap-4 items-center">
        <input value={keyword} onChange={e => setKeyword(e.target.value)} placeholder="搜索 Agent..."
          className="input flex-1 max-w-xs" />
        <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
          <input type="checkbox" checked={enabledOnly} onChange={e => setEnabledOnly(e.target.checked)}
            className="w-4 h-4 rounded border-strong text-brand focus:ring-brand/20" />
          只看已启用
        </label>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1,2,3].map(i => <div key={i} className="card p-4"><div className="skeleton h-4 w-24 mb-3" /><div className="skeleton h-3 w-full mb-2" /><div className="skeleton h-3 w-2/3" /></div>)}
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {agents.map(a => (
            <div key={a.id} className="card p-4 group">
              <div className="flex items-start justify-between mb-2">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-primary">{a.display_name || a.name}</span>
                    <span className={`badge ${archBadge[a.architecture]?.cls || 'badge-gray'}`}>
                      {archBadge[a.architecture]?.label || a.architecture}
                    </span>
                  </div>
                  <p className="text-xs text-placeholder mt-0.5">{a.name}</p>
                </div>
                <button onClick={() => onToggle(a)}
                  className={`w-9 h-5 rounded-full transition-colors relative ${a.enabled ? 'bg-success' : 'bg-hover'}`}>
                  <div className={`absolute top-0.5 w-4 h-4 bg-white rounded-full shadow-sm transition-transform ${a.enabled ? 'translate-x-4' : 'translate-x-0.5'}`} />
                </button>
              </div>
              <p className="text-sm text-secondary line-clamp-2 min-h-[2.5rem]">{a.description || '无描述'}</p>
              {a.tools?.length > 0 && (
                <div className="flex flex-wrap gap-1 mt-2">
                  {a.tools.slice(0, 4).map(t => <span key={t} className="badge badge-gray">{t}</span>)}
                  {a.tools.length > 4 && <span className="badge badge-gray">+{a.tools.length - 4}</span>}
                </div>
              )}
              <div className="flex gap-2 mt-3 pt-3 border-t border">
                <button onClick={() => nav(`/agents/${a.name}`)}
                  className="btn btn-primary btn-sm flex-1">对话</button>
                <button onClick={() => openEdit(a)}
                  className="btn btn-secondary btn-sm">编辑</button>
                <button onClick={() => onDelete(a)}
                  className="btn btn-ghost btn-sm text-danger">删除</button>
              </div>
            </div>
          ))}
          {agents.length === 0 && (
            <div className="col-span-full">
              <Empty icon="🤖" title="暂无 Agent" description="创建你的第一个智能助手" action={
                <div className="flex gap-2 justify-center">
                  <button onClick={openTemplates} className="btn btn-secondary">📋 从模板开始</button>
                  <button onClick={openCreate} className="btn btn-primary">➕ 新建 Agent</button>
                </div>
              } />
            </div>
          )}
        </div>
      )}

      {showModal && (
        <AgentForm agent={editing} kbs={kbs} wfs={wfs} archs={architectures} allTools={tools} agents={agents}
          onClose={() => setShowModal(false)} onSaved={() => { setShowModal(false); load() }} />
      )}

      <Modal isOpen={showTpl} onClose={() => setShowTpl(false)} title="从模板创建 Agent" width="max-w-3xl">
        {loadingTpl ? (
          <div className="py-12 text-center text-tertiary">加载模板中...</div>
        ) : templates.length === 0 ? (
          <Empty icon="📋" title="暂无模板" description="没有可用的 Agent 模板" />
        ) : (
          <div className="space-y-4 max-h-[60vh] overflow-y-auto pr-2">
            {Object.entries(templates.reduce<Record<string, AgentTemplate[]>>((acc, t) => {
              (acc[t.category] = acc[t.category] || []).push(t); return acc
            }, {})).map(([cat, list]) => (
              <div key={cat}>
                <h3 className="text-sm font-semibold text-tertiary mb-2 uppercase tracking-wider">{cat}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {list.map(t => (
                    <div key={t.id} className="card p-4 cursor-pointer hover:shadow-md" onClick={() => useTemplate(t)}>
                      <div className="flex items-start gap-3">
                        <div className="text-3xl shrink-0">{t.icon}</div>
                        <div className="min-w-0 flex-1">
                          <div className="font-semibold text-primary">{t.display_name}</div>
                          <p className="text-xs text-tertiary mt-1 line-clamp-2">{t.description}</p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </Modal>
    </div>
  )
}

function AgentForm({ agent, kbs, wfs, archs, allTools, agents, onClose, onSaved }: {
  agent: Agent | null; kbs: KB[]; wfs: Workflow[];
  archs: { key: string; label: string; desc: string; needs_framework: boolean; frameworks?: string[] }[];
  allTools: { name: string; display_name: string }[];
  agents: Agent[];
  onClose: () => void; onSaved: () => void;
}) {
  const isEdit = !!agent
  const [f, setF] = useState({
    name: agent?.name || '',
    display_name: agent?.display_name || '',
    description: agent?.description || '',
    architecture: agent?.architecture || 'single',
    framework: agent?.framework || '',
    system_prompt: agent?.system_prompt || '',
    tools: agent?.tools || [] as string[],
    rag_kb_ids: agent?.rag_kb_ids || [] as number[],
    llm_config: {
      provider: agent?.llm_config?.provider,
      model: agent?.llm_config?.model,
      temperature: agent?.llm_config?.temperature ?? 1.0,
      top_p: agent?.llm_config?.top_p ?? 1.0,
      max_tokens: agent?.llm_config?.max_tokens ?? null,
      presence_penalty: agent?.llm_config?.presence_penalty ?? 0,
      frequency_penalty: agent?.llm_config?.frequency_penalty ?? 0,
      stream: agent?.llm_config?.stream ?? true,
      thinking: agent?.llm_config?.thinking ?? true,
    },
    workflow_id: agent?.workflow_id || null as number | null,
    parent_agent_id: agent?.parent_agent_id || null as number | null,
    max_iterations: agent?.max_iterations ?? 10,
  })
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [saving, setSaving] = useState(false)

  const arch = archs.find(a => a.key === f.architecture)
  const isWf = f.architecture === 'workflow'
  const isSkill = f.architecture === 'skill'

  const toggleArr = (key: 'tools' | 'rag_kb_ids', val: any) => {
    const arr = f[key] as any[]
    setF({ ...f, [key]: arr.includes(val) ? arr.filter(x => x !== val) : [...arr, val] })
  }

  const save = async () => {
    if (!f.name.trim()) { toast.error('请填写 Agent 名称'); return }
    if (isWf && !f.workflow_id) { toast.error('请选择关联工作流'); return }
    setSaving(true)
    try {
      const cleanCfg: any = { ...f.llm_config }
      if (!cleanCfg.provider) delete cleanCfg.provider
      if (!cleanCfg.model) delete cleanCfg.model
      if (cleanCfg.max_tokens === '' || cleanCfg.max_tokens === undefined) cleanCfg.max_tokens = null
      const body = {
        name: f.name.trim(), display_name: f.display_name, description: f.description,
        architecture: f.architecture, framework: isWf ? f.framework : '',
        system_prompt: f.system_prompt, tools: f.tools, rag_kb_ids: f.rag_kb_ids,
        llm_config: cleanCfg, workflow_id: isWf ? f.workflow_id : null,
        parent_agent_id: isSkill ? f.parent_agent_id : null,
        max_iterations: Number(f.max_iterations) || 10,
      }
      if (isEdit) await agentsApi.update(agent!.name, body)
      else await agentsApi.create(body)
      toast.success('已保存'); onSaved()
    } finally { setSaving(false) }
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/40 p-4" onClick={onClose}>
      <div className="bg-card border border rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-6 animate-slideUp" onClick={e => e.stopPropagation()}>
        <h2 className="text-xl font-bold text-primary mb-5">{isEdit ? '编辑 Agent' : '新建 Agent'}</h2>

        <div className="grid grid-cols-2 gap-4">
          <Field label="Agent 英文名称 *">
            <input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} disabled={isEdit} />
          </Field>
          <Field label="显示名称">
            <input className="input" value={f.display_name} onChange={e => setF({ ...f, display_name: e.target.value })} />
          </Field>
        </div>
        <Field label="描述">
          <textarea className="input resize-none" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} rows={2} />
        </Field>

        <div className="grid grid-cols-2 gap-4">
          <Field label="架构类型">
            <select className="input" value={f.architecture} onChange={e => setF({ ...f, architecture: e.target.value as any, workflow_id: null, parent_agent_id: null })}>
              {archs.map(a => <option key={a.key} value={a.key}>{a.label} - {a.desc}</option>)}
            </select>
          </Field>
          {isWf && (
            <Field label="底层框架">
              <select className="input" value={f.framework} onChange={e => setF({ ...f, framework: e.target.value })}>
                <option value="">内置执行</option>
                <option value="langgraph">LangGraph</option>
                <option value="crewai">CrewAI</option>
                <option value="autogen">AutoGen</option>
              </select>
            </Field>
          )}
        </div>

        {isWf && (
          <Field label="关联工作流 *">
            <select className="input" value={f.workflow_id || ''} onChange={e => setF({ ...f, workflow_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">-- 请选择 --</option>
              {wfs.map(w => <option key={w.id} value={w.id}>{w.display_name || w.name}</option>)}
            </select>
          </Field>
        )}
        {isSkill && (
          <Field label="父 Agent (归属)">
            <select className="input" value={f.parent_agent_id || ''} onChange={e => setF({ ...f, parent_agent_id: e.target.value ? Number(e.target.value) : null })}>
              <option value="">无</option>
              {agents.filter(a => a.architecture !== 'skill' && a.id !== agent?.id).map(a =>
                <option key={a.id} value={a.id}>{a.display_name || a.name}</option>)}
            </select>
          </Field>
        )}

        <Field label="系统提示词 (System Prompt)">
          <textarea className="input resize-none" value={f.system_prompt} onChange={e => setF({ ...f, system_prompt: e.target.value })} rows={4}
            placeholder="定义 Agent 的角色、能力和约束..." />
        </Field>

        <Field label={`绑定工具 (已选 ${f.tools.length})`}>
          <div className="flex flex-wrap gap-2 p-2 bg-subtle rounded-lg border max-h-32 overflow-y-auto">
            {allTools.map(t => (
              <label key={t.name} className={`text-sm px-2 py-1 rounded-md cursor-pointer transition ${f.tools.includes(t.name) ? 'bg-brand-subtle text-brand' : 'bg-hover text-secondary'}`}>
                <input type="checkbox" className="hidden" checked={f.tools.includes(t.name)}
                  onChange={() => toggleArr('tools', t.name)} />
                {t.display_name || t.name}
              </label>
            ))}
            {allTools.length === 0 && <span className="text-placeholder text-sm">暂无工具</span>}
          </div>
        </Field>

        <Field label={`绑定知识库 (已选 ${f.rag_kb_ids.length})`}>
          <div className="flex flex-wrap gap-2 p-2 bg-subtle rounded-lg border max-h-32 overflow-y-auto">
            {kbs.map(k => (
              <label key={k.id} className={`text-sm px-2 py-1 rounded-md cursor-pointer transition ${f.rag_kb_ids.includes(k.id) ? 'bg-success/10 text-success' : 'bg-hover text-secondary'}`}>
                <input type="checkbox" className="hidden" checked={f.rag_kb_ids.includes(k.id)}
                  onChange={() => toggleArr('rag_kb_ids', k.id)} />
                {k.name}
              </label>
            ))}
            {kbs.length === 0 && <span className="text-placeholder text-sm">暂无知识库</span>}
          </div>
        </Field>

        {/* 基础参数 */}
        <div className="pt-3 border-t border">
          <div className="text-sm font-medium mb-3 text-primary">模型配置 · 基础</div>
          <div className="grid grid-cols-2 gap-4">
            <Field label="模型提供方">
              <select className="input" value={f.llm_config.provider || ''}
                onChange={e => setF({ ...f, llm_config: { ...f.llm_config, provider: (e.target.value || undefined) as any } })}>
                <option value="">默认 (跟随系统配置)</option>
                <option value="ark">ARK 火山方舟</option>
                <option value="giteeai">GiteeAI 模力方舟</option>
                <option value="deepseek">DeepSeek 直连</option>
              </select>
            </Field>
            <Field label="模型名 (留空用默认)">
              <input className="input" value={f.llm_config.model || ''}
                onChange={e => setF({ ...f, llm_config: { ...f.llm_config, model: e.target.value || undefined } })}
                placeholder="doubao-seed-evolving" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <Field label={`Temperature (随机性) ${f.llm_config.temperature}`}>
              <input type="range" min={0} max={2} step={0.1} value={f.llm_config.temperature ?? 1}
                onChange={e => setF({ ...f, llm_config: { ...f.llm_config, temperature: Number(e.target.value) } })}
                className="w-full accent-brand" />
            </Field>
            <Field label="最大推理步数 (ReAct)">
              <input type="number" min={1} max={50} value={f.max_iterations}
                onChange={e => setF({ ...f, max_iterations: Number(e.target.value) })}
                className="input" />
            </Field>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <label className="flex items-center gap-2 text-sm cursor-pointer bg-subtle p-2 rounded-lg border">
              <input type="checkbox" checked={!!f.llm_config.stream}
                onChange={e => setF({ ...f, llm_config: { ...f.llm_config, stream: e.target.checked } })}
                className="w-4 h-4 rounded border-strong text-brand" />
              <span className="text-secondary">🌊 流式输出</span>
            </label>
            <label className="flex items-center gap-2 text-sm cursor-pointer bg-subtle p-2 rounded-lg border">
              <input type="checkbox" checked={!!f.llm_config.thinking}
                onChange={e => setF({ ...f, llm_config: { ...f.llm_config, thinking: e.target.checked } })}
                className="w-4 h-4 rounded border-strong text-brand" />
              <span className="text-secondary">🧠 显示思考内容</span>
            </label>
          </div>
        </div>

        {/* 高级参数 */}
        <div className="pt-3">
          <button type="button" onClick={() => setShowAdvanced(!showAdvanced)}
            className="text-sm text-brand hover:underline flex items-center gap-1">
            <span>{showAdvanced ? '▼' : '▶'}</span>
            {showAdvanced ? '收起高级参数' : '展开高级参数 (top_p / max_tokens / 惩罚等)'}
          </button>
          {showAdvanced && (
            <div className="mt-3 grid grid-cols-2 gap-4 p-3 bg-subtle rounded-lg border">
              <Field label="Top P (核采样)">
                <input type="number" min={0} max={1} step={0.05} value={f.llm_config.top_p ?? 1}
                  onChange={e => setF({ ...f, llm_config: { ...f.llm_config, top_p: Number(e.target.value) } })}
                  className="input" />
              </Field>
              <Field label="Max Tokens (空=不限制)">
                <input type="number" min={1} step={1}
                  value={f.llm_config.max_tokens ?? ''}
                  onChange={e => setF({ ...f, llm_config: { ...f.llm_config, max_tokens: e.target.value ? Number(e.target.value) : null } })}
                  placeholder="不限制"
                  className="input" />
              </Field>
              <Field label="Presence Penalty (-2~2)">
                <input type="number" min={-2} max={2} step={0.1} value={f.llm_config.presence_penalty ?? 0}
                  onChange={e => setF({ ...f, llm_config: { ...f.llm_config, presence_penalty: Number(e.target.value) } })}
                  className="input" />
              </Field>
              <Field label="Frequency Penalty (-2~2)">
                <input type="number" min={-2} max={2} step={0.1} value={f.llm_config.frequency_penalty ?? 0}
                  onChange={e => setF({ ...f, llm_config: { ...f.llm_config, frequency_penalty: Number(e.target.value) } })}
                  className="input" />
              </Field>
            </div>
          )}
        </div>

        <div className="flex justify-end gap-3 mt-6 pt-4 border-t border">
          <button onClick={onClose} className="btn btn-secondary">取消</button>
          <button onClick={save} disabled={saving}
            className="btn btn-primary disabled:opacity-50">
            {saving ? '...' : '保存'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="mb-3">
      <label className="block text-sm font-medium text-secondary mb-1.5">{label}</label>
      {children}
    </div>
  )
}
