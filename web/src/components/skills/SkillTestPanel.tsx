import { useEffect, useState } from 'react'
import toast from 'react-hot-toast'
import { skillApi, Skill, SkillTestOut } from '@/api'
import Button from '@/components/ui/Button'
import Modal from '@/components/ui/Modal'

/** 技能测试面板 - JSON参数输入、执行、日志、耗时、traceback */
export default function SkillTestPanel({ skill, onClose }: { skill: Skill; onClose: () => void }) {
  // 按 skill.id 持久化最近测试参数
  const STORAGE_KEY = `skill_test_params_${skill.id}`
  const [paramsJson, setParamsJson] = useState(() => localStorage.getItem(STORAGE_KEY) || '{}')
  const [contextJson, setContextJson] = useState('{}')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<SkillTestOut | null>(null)
  const [showTraceback, setShowTraceback] = useState(false)

  useEffect(() => {
    try { localStorage.setItem(STORAGE_KEY, paramsJson) } catch { /* ignore */ }
  }, [paramsJson, STORAGE_KEY])

  // 从日志中分离 traceback
  const tracebackLine = result?.logs?.find(l => l.startsWith('[TRACEBACK]'))
  const normalLogs = result?.logs?.filter(l => !l.startsWith('[TRACEBACK]')) || []
  const traceback = tracebackLine ? tracebackLine.replace('[TRACEBACK]\n', '') : ''

  const run = async () => {
    let params: Record<string, any>, context: Record<string, any>
    try { params = JSON.parse(paramsJson) } catch { toast.error('参数 JSON 格式错误'); return }
    try { context = JSON.parse(contextJson) } catch { toast.error('上下文 JSON 格式错误'); return }
    setRunning(true); setResult(null)
    const start = Date.now()
    try {
      const res = await skillApi.test(skill.id, { input_params: params, context })
      setResult(res)
      setShowTraceback(!res.success) // 失败时自动展开
    } catch (e: any) {
      setResult({ success: false, output: null, logs: [], elapsed_ms: Date.now() - start, error: e?.response?.data?.msg || '请求失败' })
      setShowTraceback(true)
    } finally { setRunning(false) }
  }

  const copyOutput = () => {
    if (!result?.output) return
    const text = typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2)
    navigator.clipboard.writeText(text).then(() => toast.success('已复制到剪贴板'))
  }

  // 耗时颜色: <500ms 绿, <2s 青, <5s 黄, >=5s 红
  const elapsedColor = (ms: number) =>
    ms < 500 ? 'text-emerald-300' : ms < 2000 ? 'text-cyan-300' : ms < 5000 ? 'text-amber-300' : 'text-red-300'

  return (
    <Modal isOpen={true} onClose={onClose} title={`🧪 测试技能: ${skill.name}`} width="max-w-3xl">
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-tertiary mb-1.5">输入参数 (JSON)</label>
          <textarea value={paramsJson} onChange={e => setParamsJson(e.target.value)} rows={8}
            className="glass-input w-full font-mono text-sm resize-y" placeholder={'{\n  "key": "value"\n}'} />
        </div>
        <div>
          <label className="block text-sm font-medium text-tertiary mb-1.5">上下文 (JSON, 可选)</label>
          <textarea value={contextJson} onChange={e => setContextJson(e.target.value)} rows={8}
            className="glass-input w-full font-mono text-sm resize-y" placeholder={'{\n  "user_id": 1\n}'} />
        </div>
      </div>

      {skill.config && Object.keys(skill.config).length > 0 && (
        <div className="mt-3 p-3 bg-card rounded-lg border border">
          <div className="text-xs text-tertiary mb-1">📋 参数 Schema:</div>
          <pre className="text-xs text-secondary overflow-x-auto">{JSON.stringify(skill.config, null, 2)}</pre>
        </div>
      )}

      <div className="flex justify-end gap-3 mt-4">
        <Button variant="secondary" onClick={onClose}>关闭</Button>
        <Button onClick={run} disabled={running}>
          {running ? (<span className="flex items-center gap-2"><span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />运行中...</span>) : '▶️ 运行'}
        </Button>
      </div>

      {result && (
        <div className="mt-4 space-y-3">
          <div className={`p-3 rounded-lg border ${result.success ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-red-500/10 border-red-500/30'}`}>
            <div className="flex items-center justify-between">
              <span className={`font-medium ${result.success ? 'text-emerald-300' : 'text-red-300'}`}>
                {result.success ? '✅ 执行成功' : '❌ 执行失败'}
              </span>
              <span className={`text-xs font-mono ${elapsedColor(result.elapsed_ms)}`}>
                ⏱ {result.elapsed_ms} ms
              </span>
            </div>
            {result.error && (
              <div className="text-sm mt-2 text-red-200 bg-red-500/10 rounded p-2 border border-red-500/20">
                {result.error}
              </div>
            )}
          </div>

          {normalLogs.length > 0 && (
            <div>
              <div className="text-sm font-medium text-tertiary mb-1.5">📜 执行日志</div>
              <div className="bg-black/30 rounded-lg p-3 max-h-48 overflow-y-auto font-mono text-xs space-y-0.5">
                {normalLogs.map((l, i) => {
                  let cls = 'text-secondary'
                  if (l.startsWith('[ERROR]')) cls = 'text-red-300'
                  else if (l.startsWith('[SECURITY]')) cls = 'text-amber-300'
                  else if (l.startsWith('[INFO]')) cls = 'text-cyan-300/80'
                  else if (l.startsWith('[STDOUT]')) cls = 'text-tertiary'
                  else if (l.startsWith('[STDERR]')) cls = 'text-amber-200/70'
                  return <div key={i} className={cls}>{l}</div>
                })}
              </div>
            </div>
          )}

          {traceback && (
            <div>
              <button onClick={() => setShowTraceback(v => !v)}
                className="text-xs text-amber-300 hover:text-amber-200 flex items-center gap-1">
                {showTraceback ? '▼' : '▶'} 📋 Traceback 详情
              </button>
              {showTraceback && (
                <pre className="mt-1 bg-black/40 rounded p-2 text-[11px] text-red-200/80 overflow-x-auto max-h-40">
                  {traceback}
                </pre>
              )}
            </div>
          )}

          {result.output !== null && result.output !== undefined && (
            <div>
              <div className="flex items-center justify-between mb-1.5">
                <span className="text-sm font-medium text-tertiary">📤 输出结果</span>
                <button onClick={copyOutput}
                  className="text-xs text-tertiary hover:text-primary transition">📋 复制</button>
              </div>
              <pre className="bg-black/30 rounded-lg p-3 max-h-64 overflow-auto text-xs text-emerald-200/90 whitespace-pre-wrap break-all font-mono">
                {typeof result.output === 'string' ? result.output : JSON.stringify(result.output, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </Modal>
  )
}
