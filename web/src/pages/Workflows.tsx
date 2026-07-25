import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { workflowApi, Workflow } from '@/api'
import Empty from '@/components/ui/Empty'
import Modal from '@/components/ui/Modal'

interface Template {
  id: string; name: string; display_name: string; description: string
  category: string; node_count: number; edge_count: number
}

export default function Workflows() {
  const nav = useNavigate()
  const [wfs, setWfs] = useState<Workflow[]>([])
  const [show, setShow] = useState(false)
  const [showTpl, setShowTpl] = useState(false)
  const [loading, setLoading] = useState(true)
  const [f, setF] = useState({ name: '', display_name: '', description: '', category: '' })
  const [templates, setTemplates] = useState<Template[]>([])
  const [loadingTpl, setLoadingTpl] = useState(false)

  const load = async () => {
    setLoading(true)
    try { setWfs(await workflowApi.list()) } catch { toast.error('加载失败') }
    finally { setLoading(false) }
  }

  useEffect(() => {
    const h = () => { setF({ name: '', display_name: '', description: '', category: '' }); setShow(true) }
    window.addEventListener('cmd-new-wf', h)
    return () => window.removeEventListener('cmd-new-wf', h)
  }, [])
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!f.name.trim()) { toast.error('请填写名称'); return }
    try {
      const w = await workflowApi.create({ ...f, definition: { nodes: [], edges: [] } })
      toast.success('已创建'); setShow(false); load()
      setF({ name: '', display_name: '', description: '', category: '' })
      nav(`/workflows/${w.id}`)
    } catch (e: any) { toast.error(e?.response?.data?.detail || '创建失败') }
  }

  const openTemplates = async () => {
    setShowTpl(true)
    if (templates.length === 0) {
      setLoadingTpl(true)
      try { setTemplates(await workflowApi.templates()) } catch {}
      finally { setLoadingTpl(false) }
    }
  }

  const useTemplate = async (t: Template) => {
    try {
      const w = await workflowApi.fromTemplate({ template_id: t.id })
      toast.success(`已从模板创建: ${t.display_name}`)
      setShowTpl(false)
      nav(`/workflows/${w.id}`)
    } catch (e: any) { toast.error(e?.response?.data?.detail || '创建失败') }
  }

  const del = async (w: Workflow) => {
    if (!confirm(`删除工作流 "${w.display_name || w.name}"?`)) return
    await workflowApi.remove(w.id); toast.success('已删除'); load()
  }
  const toggle = async (w: Workflow) => { await workflowApi.toggle(w.id, !w.enabled); load() }
  const run = async (w: Workflow) => {
    try {
      const res = await workflowApi.run(w.id, {})
      toast.success(res?.status === 'success' ? '执行成功' : '执行完成')
    } catch (e: any) { toast.error(e?.response?.data?.detail || '运行失败') }
  }

  const tplByCat = templates.reduce<Record<string, Template[]>>((acc, t) => {
    (acc[t.category] = acc[t.category] || []).push(t)
    return acc
  }, {})

  return (
    <div className="p-6 space-y-5 animate-fadeIn">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-bold text-primary">工作流管理</h1>
          <p className="text-tertiary text-sm mt-1">可视化编排任务流程，拖拽节点连接成 DAG</p>
        </div>
        <div className="flex gap-2">
          <button onClick={openTemplates} className="btn btn-secondary">📋 从模板创建</button>
          <button onClick={() => setShow(true)} className="btn btn-primary">➕ 新建工作流</button>
        </div>
      </div>

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {[1,2,3,4].map(i => (
            <div key={i} className="card p-4">
              <div className="skeleton h-4 w-32 mb-3" /><div className="skeleton h-3 w-full mb-2" /><div className="skeleton h-3 w-2/3" />
            </div>
          ))}
        </div>
      ) : wfs.length === 0 ? (
        <Empty icon="⚡" title="暂无工作流" description="创建你的第一个工作流，通过可视化拖拽编排任务流程" action={
          <div className="flex gap-2 justify-center">
            <button onClick={openTemplates} className="btn btn-secondary">📋 从模板开始</button>
            <button onClick={() => setShow(true)} className="btn btn-primary">➕ 新建空白工作流</button>
          </div>
        } />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {wfs.map(w => (
            <div key={w.id} className="card p-4 cursor-pointer hover:shadow-md group" onClick={() => nav(`/workflows/${w.id}`)}>
              <div className="flex items-start justify-between mb-2">
                <div className="min-w-0 flex-1">
                  <div className="font-semibold text-primary truncate">{w.display_name || w.name}</div>
                  <div className="text-xs text-placeholder truncate mt-0.5">{w.name} · {w.category || '未分类'}</div>
                </div>
                <span className={`badge shrink-0 ml-2 ${w.enabled ? 'badge-green' : 'badge-gray'}`}>
                  {w.enabled ? '已启用' : '已禁用'}
                </span>
              </div>
              <p className="text-sm text-secondary mb-3 line-clamp-2">{w.description || '无描述'}</p>
              <div className="flex gap-2 pt-3 border-t border" onClick={e => e.stopPropagation()}>
                <button onClick={() => nav(`/workflows/${w.id}`)}
                  className="btn btn-primary btn-sm">✏️ 编辑</button>
                <button onClick={() => run(w)}
                  className="btn btn-secondary btn-sm">▶ 运行</button>
                <button onClick={() => toggle(w)}
                  className="btn btn-ghost btn-sm">{w.enabled ? '禁用' : '启用'}</button>
                <button onClick={() => del(w)}
                  className="btn btn-ghost btn-sm text-danger ml-auto">删除</button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Modal isOpen={show} onClose={() => setShow(false)} title="新建工作流" width="max-w-md">
        <div className="space-y-3">
          <div>
            <label className="block text-sm font-medium text-secondary mb-1.5">名称 (英文标识)</label>
            <input className="input" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} placeholder="my_workflow" />
          </div>
          <div>
            <label className="block text-sm font-medium text-secondary mb-1.5">显示名称</label>
            <input className="input" value={f.display_name} onChange={e => setF({ ...f, display_name: e.target.value })} placeholder="我的工作流" />
          </div>
          <div>
            <label className="block text-sm font-medium text-secondary mb-1.5">分类</label>
            <input className="input" value={f.category} onChange={e => setF({ ...f, category: e.target.value })} placeholder="基础/RAG/..." />
          </div>
          <div>
            <label className="block text-sm font-medium text-secondary mb-1.5">描述</label>
            <textarea className="input resize-none" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} rows={2} placeholder="描述这个工作流的用途..." />
          </div>
        </div>
        <div className="flex justify-end gap-3 mt-5">
          <button onClick={() => setShow(false)} className="btn btn-secondary">取消</button>
          <button onClick={create} className="btn btn-primary">创建</button>
        </div>
      </Modal>

      <Modal isOpen={showTpl} onClose={() => setShowTpl(false)} title="从模板创建工作流" width="max-w-3xl">
        {loadingTpl ? (
          <div className="py-12 text-center text-tertiary">加载模板中...</div>
        ) : templates.length === 0 ? (
          <Empty icon="📋" title="暂无模板" description="没有可用的工作流模板" />
        ) : (
          <div className="space-y-5 max-h-[60vh] overflow-y-auto pr-2">
            {Object.entries(tplByCat).map(([cat, list]) => (
              <div key={cat}>
                <h3 className="text-sm font-semibold text-tertiary mb-2 uppercase tracking-wider">{cat}</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  {list.map(t => (
                    <div key={t.id} className="card p-3 cursor-pointer hover:shadow-md" onClick={() => useTemplate(t)}>
                      <div className="font-semibold text-primary mb-1">{t.display_name}</div>
                      <p className="text-xs text-tertiary mb-2 line-clamp-2">{t.description}</p>
                      <div className="flex items-center gap-3 text-xs text-placeholder">
                        <span>🔗 {t.node_count} 节点</span>
                        <span>↔️ {t.edge_count} 连线</span>
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
