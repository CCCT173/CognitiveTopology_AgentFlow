import { useEffect, useState, useCallback, useRef } from 'react'
import toast from 'react-hot-toast'
import { workflowApi, Workflow } from '@/api'
import { useParams, useNavigate, useBlocker } from 'react-router-dom'
import WorkflowEditor, { WFDefinition } from '@/components/WorkflowEditor'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'

function fp(d: WFDefinition) { return JSON.stringify({ nodes: d.nodes, edges: d.edges }) }

interface RunRec {
  id: number; run_id: string; workflow_id: number; workflow_name: string
  status: string; elapsed_ms: number; error?: string; created_at: string
}

export default function WFDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const [wf, setWf] = useState<Workflow | null>(null)
  const [def, setDef] = useState<WFDefinition>({ nodes: [], edges: [] })
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [runResult, setRunResult] = useState<any>(null)
  const [runInput, setRunInput] = useState<Record<string, any>>({})
  const [showRunModal, setShowRunModal] = useState(false)
  const [runs, setRuns] = useState<RunRec[]>([])
  const [showHistory, setShowHistory] = useState(false)
  const [detailRun, setDetailRun] = useState<any>(null)
  const [dirty, setDirty] = useState(false)
  const [savedFp, setSavedFp] = useState<string>('')
  const loadedFpRef = useRef<string>('')

  const load = useCallback(async () => {
    try {
      const data = await workflowApi.get(Number(id))
      setWf(data)
      const loaded = data.definition || { nodes: [], edges: [] }
      setDef(loaded)
      const f = fp(loaded)
      setSavedFp(f)
      loadedFpRef.current = f
      setDirty(false)
    } catch { toast.error('工作流不存在') }
  }, [id])

  useEffect(() => { load() }, [load])

  // 离开页面拦截：有未保存改动时提示
  const [leavingTo, setLeavingTo] = useState<string | null>(null)
  useEffect(() => {
    if (!dirty) return
    const onBeforeUnload = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = '' }
    window.addEventListener('beforeunload', onBeforeUnload)
    return () => window.removeEventListener('beforeunload', onBeforeUnload)
  }, [dirty])

  // 拦截 popstate (浏览器后退/前进)
  useEffect(() => {
    if (!dirty) return
    const handlePop = (e: PopStateEvent) => {
      // 已经在确认中则放行
      if (leavingTo) return
      e.preventDefault()
      const ok = window.confirm('有未保存的更改，确定要离开吗？')
      if (ok) {
        history.back()
      } else {
        // 再 push 一次当前历史以保持在本页
        history.pushState(null, '', location.href)
      }
    }
    // 初次进入时 pushState 一次以让后退能被拦截
    history.pushState(null, '', location.href)
    window.addEventListener('popstate', handlePop)
    return () => window.removeEventListener('popstate', handlePop)
  }, [dirty, leavingTo])

  const confirmLeave = (to: string) => {
    if (!dirty) { nav(to); return }
    if (window.confirm('有未保存的更改，确定要离开吗？')) {
      setDirty(false)
      setTimeout(() => nav(to), 0)
    }
  }

  // 加载运行历史
  const loadRuns = useCallback(async () => {
    try { setRuns(await workflowApi.runs(Number(id), 30)) } catch {}
  }, [id])
  useEffect(() => { if (showHistory) loadRuns() }, [showHistory, loadRuns])

  const viewRunDetail = async (runId: string) => {
    try { setDetailRun(await workflowApi.runDetail(runId)) } catch { toast.error('加载详情失败') }
  }

  const save = async () => {
    if (!wf) return
    setSaving(true)
    try {
      await workflowApi.update(wf.id, { definition: def })
      toast.success('已保存')
      const f = fp(def)
      setSavedFp(f)
      setDirty(false)
      await load()
    } catch (e: any) {
      toast.error(e?.response?.data?.detail || '保存失败')
    } finally { setSaving(false) }
  }

  const openRun = () => { setShowRunModal(true) }

  const doRun = async () => {
    if (!wf) return
    setShowRunModal(false)
    setRunning(true)
    setRunResult(null)
    // 保存最新状态再运行
    try { await workflowApi.update(wf.id, { definition: def }) } catch {}
    try {
      const res = await workflowApi.run(wf.id, { input: runInput, variables: runInput })
      setRunResult(res)
      loadRuns()
    } catch (e: any) {
      const detail = e?.response?.data?.detail || e?.message || '运行失败'
      setRunResult({ status: 'failed', error: detail, logs: [`❌ ${detail}`], output: null })
      toast.error(detail)
    } finally { setRunning(false) }
  }

  if (!wf) return <div className="flex items-center justify-center py-16 text-tertiary"><div className="animate-spin w-6 h-6 border-2 border-cyan-400 border-t-transparent rounded-full" /></div>

  return (
    <div className="flex flex-col h-[calc(100vh-120px)] space-y-3">
      {/* 顶部工具栏 */}
      <div className="flex items-center gap-3 shrink-0">
        <button onClick={() => confirmLeave('/workflows')} className="text-tertiary hover:text-primary text-sm flex items-center gap-1 transition">← 返回</button>
        <div className="flex-1 min-w-0">
          <h1 className="text-xl font-bold truncate flex items-center gap-2">
            {wf.display_name || wf.name}
            {dirty && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/20 text-amber-300 border border-amber-500/30" title="有未保存的更改">未保存</span>}
          </h1>
          <p className="text-tertiary text-xs truncate">{wf.description || '无描述'} · {wf.category || '未分类'}</p>
        </div>
        <span className={`px-2 py-0.5 text-xs rounded ${wf.enabled ? 'bg-emerald-500/20 text-emerald-300' : 'bg-card text-tertiary'}`}>
          {wf.enabled ? '已启用' : '已禁用'}
        </span>
        <button onClick={save} disabled={saving || !dirty}
          className="px-3 py-1.5 text-sm rounded-lg bg-hover hover:bg-active transition disabled:opacity-40">
          {saving ? '保存中...' : dirty ? '💾 保存*' : '💾 保存'}
        </button>
        <button onClick={() => setShowHistory(true)}
          className="px-3 py-1.5 text-sm rounded-lg bg-hover hover:bg-active transition">
          📜 历史
        </button>
        <button onClick={openRun} disabled={running}
          className="px-3 py-1.5 text-sm rounded-lg bg-gradient-to-r from-brand to-brand-700 hover:opacity-90 transition disabled:opacity-50 font-medium">
          {running ? '⏳ 运行中...' : '▶️ 运行'}
        </button>
      </div>

      {/* 编辑器 */}
      <div className="flex-1 min-h-0">
        <WorkflowEditor
          definition={def}
          onChange={setDef}
          onSave={save}
          onRun={openRun}
          running={running}
          savedFingerprint={savedFp}
          onDirtyChange={setDirty}
          runResult={runResult}
        />
      </div>

      {/* 运行输入 Modal */}
      {showRunModal && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60  p-4" onClick={() => setShowRunModal(false)}>
          <div className="bg-card border border rounded-2xl w-full max-w-lg p-6" onClick={e => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-3">运行工作流</h3>
            <p className="text-sm text-tertiary mb-3">输入 JSON 格式的参数，将作为 {'{{input}}'} 传递给开始节点。</p>
            <textarea
              className="w-full px-3 py-2 rounded-xl bg-card border border font-mono text-sm resize-none"
              rows={8}
              value={JSON.stringify(runInput, null, 2)}
              onChange={e => { try { setRunInput(JSON.parse(e.target.value)) } catch {} }}
            />
            <div className="flex justify-end gap-2 mt-4">
              <button onClick={() => setShowRunModal(false)} className="px-4 py-2 rounded-xl bg-hover hover:bg-active">取消</button>
              <button onClick={doRun} className="px-4 py-2 rounded-xl bg-gradient-to-r from-brand to-brand-700 font-medium">🚀 运行</button>
            </div>
          </div>
        </div>
      )}

      {/* 运行结果 Modal */}
      {runResult && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60  p-4" onClick={() => setRunResult(null)}>
          <div className="bg-card border border rounded-2xl w-full max-w-3xl max-h-[80vh] overflow-y-auto p-6" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-semibold">运行结果</h3>
              <button onClick={() => setRunResult(null)} className="w-8 h-8 rounded-lg hover:bg-hover flex items-center justify-center">✕</button>
            </div>
            <div className={`inline-flex px-3 py-1 rounded-full text-sm mb-3 ${runResult.status === 'success' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
              {runResult.status === 'success' ? '✅ 执行成功' : '❌ 执行失败'}
              {runResult.elapsed_ms && <span className="ml-2 text-tertiary">({runResult.elapsed_ms}ms)</span>}
            </div>
            {runResult.error && <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 mb-3 text-sm text-red-300">{runResult.error}</div>}
            <div className="mb-3">
              <div className="text-sm text-tertiary mb-1">执行日志</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-primary max-h-48 overflow-y-auto whitespace-pre-wrap">{runResult.logs?.join('\n')}</pre>
            </div>
            <div>
              <div className="text-sm text-tertiary mb-1">输出结果</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-cyan-300 max-h-48 overflow-y-auto">{JSON.stringify(runResult.output, null, 2)}</pre>
            </div>
          </div>
        </div>
      )}

      {/* 运行历史 Modal */}
      <Modal isOpen={showHistory} onClose={() => setShowHistory(false)} title="📜 运行历史" width="max-w-3xl">
        {runs.length === 0 ? (
          <p className="py-8 text-center text-placeholder text-sm">暂无运行记录</p>
        ) : (
          <div className="space-y-2 max-h-[60vh] overflow-y-auto">
            {runs.map(r => (
              <div key={r.id} className="p-3 rounded-lg bg-card hover:bg-hover transition flex items-center gap-3">
                <span className={`w-2 h-2 rounded-full shrink-0 ${r.status === 'success' ? 'bg-emerald-400' : r.status === 'failed' ? 'bg-red-400' : 'bg-amber-400'}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 text-sm">
                    <span className="font-mono text-xs text-tertiary">{r.run_id}</span>
                    <span className={`text-xs px-2 py-0.5 rounded ${r.status === 'success' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>{r.status}</span>
                    <span className="text-xs text-placeholder">{r.elapsed_ms}ms</span>
                  </div>
                  <div className="text-xs text-placeholder mt-0.5">{new Date(r.created_at).toLocaleString()}</div>
                  {r.error && <div className="text-xs text-red-300 mt-1 truncate">{r.error}</div>}
                </div>
                <button onClick={() => viewRunDetail(r.run_id)}
                  className="px-3 py-1 text-xs rounded-lg bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30">详情</button>
              </div>
            ))}
          </div>
        )}
      </Modal>

      {/* 单次运行详情 Modal */}
      <Modal isOpen={!!detailRun} onClose={() => setDetailRun(null)} title="运行详情" width="max-w-3xl">
        {detailRun && (
          <div className="space-y-3 max-h-[70vh] overflow-y-auto">
            <div className="flex items-center gap-3">
              <span className={`inline-flex px-3 py-1 rounded-full text-sm ${detailRun.status === 'success' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-red-500/20 text-red-300'}`}>
                {detailRun.status === 'success' ? '✅ 成功' : '❌ 失败'}
              </span>
              <span className="text-xs text-tertiary font-mono">{detailRun.run_id}</span>
              <span className="text-xs text-tertiary">{detailRun.elapsed_ms}ms</span>
            </div>
            {detailRun.error && <div className="bg-red-500/10 border border-red-500/30 rounded-xl p-3 text-sm text-red-300">{detailRun.error}</div>}
            <div>
              <div className="text-sm text-secondary mb-1">输入</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-secondary max-h-32 overflow-y-auto">{JSON.stringify(detailRun.input_data, null, 2)}</pre>
            </div>
            <div>
              <div className="text-sm text-secondary mb-1">执行日志</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-primary max-h-48 overflow-y-auto whitespace-pre-wrap">{(detailRun.logs || []).join('\n')}</pre>
            </div>
            <div>
              <div className="text-sm text-secondary mb-1">输出</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-cyan-300 max-h-48 overflow-y-auto">{JSON.stringify(detailRun.output_data, null, 2)}</pre>
            </div>
          </div>
        )}
      </Modal>
    </div>
  )
}
