import { useState, useRef, useCallback, useEffect, useMemo } from 'react'
import toast from 'react-hot-toast'
import Button from './ui/Button'
import Modal from './ui/Modal'
import { useMetaStore } from '@/store/meta'
import { agentsApi, skillApi, Agent, Skill } from '@/api'

// ===== 类型定义 =====
export interface WFNode {
  id: string
  type: 'start' | 'end' | 'llm' | 'tool' | 'skill' | 'condition' | 'agent' | 'code' | 'loop' | 'parallel' | 'transform' | 'delay'
  name: string
  config: Record<string, any>
  position: { x: number; y: number }
}

export interface WFEdge {
  id: string
  source: string
  target: string
  sourceHandle?: string
  condition?: string
}

export interface WFDefinition {
  nodes: WFNode[]
  edges: WFEdge[]
  entry?: string
}

interface WorkflowEditorProps {
  definition: WFDefinition
  onChange: (def: WFDefinition) => void
  onSave?: () => void
  onRun?: () => void
  running?: boolean
  savedFingerprint?: string  // 父组件传入当前"已保存版本"的指纹, 用于计算 dirty
  onDirtyChange?: (dirty: boolean) => void
  runResult?: { logs: string[]; output: any; status: string; error?: string } | null
}

// ===== 参数配置 Schema 类型定义 =====
export interface ParamField {
  key: string
  label: string
  type: 'text' | 'number' | 'slider' | 'select' | 'switch' | 'textarea' | 'json' | 'code'
  description?: string
  placeholder?: string
  default?: any
  min?: number
  max?: number
  step?: number
  options?: { value: any; label: string }[]
  required?: boolean
  hidden?: boolean
  dependsOn?: { field: string; value: any }
  group?: string
  rows?: number
  readonly?: boolean
  fullWidth?: boolean
  specialHandler?: boolean
}

export interface NodeParamSchema {
  [key: string]: ParamField[]
}

// 节点类型配置
const NODE_TYPES = [
  { type: 'start', label: '开始', icon: '▶️', color: '#10B981', desc: '接收输入参数' },
  { type: 'end', label: '结束', icon: '⏹️', color: '#EF4444', desc: '返回输出结果' },
  { type: 'llm', label: 'LLM', icon: '🧠', color: '#7C3AED', desc: '调用大语言模型' },
  { type: 'tool', label: '工具', icon: '🔧', color: '#06B6D4', desc: '调用注册工具' },
  { type: 'skill', label: '技能', icon: '🧩', color: '#F59E0B', desc: '调用 Skill 技能' },
  { type: 'condition', label: '条件', icon: '🔀', color: '#EC4899', desc: '条件分支判断' },
  { type: 'agent', label: 'Agent', icon: '🤖', color: '#8B5CF6', desc: '调用子 Agent' },
  { type: 'code', label: '代码', icon: '💻', color: '#6366F1', desc: '执行自定义代码' },
  { type: 'loop', label: '循环', icon: '🔄', color: '#84CC16', desc: '遍历列表执行' },
  { type: 'parallel', label: '并行', icon: '⚡', color: '#F97316', desc: '并行执行多个分支' },
  { type: 'transform', label: '转换', icon: '🔄', color: '#0EA5E9', desc: '数据格式转换' },
  { type: 'delay', label: '延迟', icon: '⏱️', color: '#A855F7', desc: '延迟指定时间' },
] as const

// ===== 节点参数配置 Schema =====
const NODE_PARAM_SCHEMAS: NodeParamSchema = {
  llm: [
    { key: 'provider', label: 'Provider', type: 'select', description: '选择 LLM 服务提供商', options: [] },
    { key: 'model', label: 'Model', type: 'text', description: '模型名称', placeholder: '留空使用默认模型' },
    { key: 'system_prompt', label: 'System Prompt', type: 'textarea', description: '系统提示词，用于设定模型的行为和角色', rows: 3, fullWidth: true },
    { key: 'prompt', label: 'Prompt 模板', type: 'textarea', description: '用户提示词模板，支持 {{var}} 变量引用', rows: 4, fullWidth: true },
    { key: 'temperature', label: 'Temperature', type: 'slider', description: '控制输出随机性，0-2，值越高越随机', min: 0, max: 2, step: 0.1, default: 0.7 },
    { key: 'top_p', label: 'Top P', type: 'slider', description: '控制输出多样性，0-1，值越小越聚焦', min: 0, max: 1, step: 0.05, default: 1 },
    { key: 'max_tokens', label: 'Max Tokens', type: 'number', description: '最大输出令牌数', min: 1, max: 32768, default: 2048 },
    { key: 'response_format', label: '响应格式', type: 'select', description: '选择输出格式', options: [{ value: 'text', label: 'Text' }, { value: 'json_object', label: 'JSON Object' }] },
    { key: 'presence_penalty', label: 'Presence Penalty', type: 'number', description: '减少重复内容生成', min: -2, max: 2, step: 0.1, default: 0 },
    { key: 'frequency_penalty', label: 'Frequency Penalty', type: 'number', description: '鼓励生成新主题', min: -2, max: 2, step: 0.1, default: 0 },
    { key: 'stream', label: '流式输出', type: 'switch', description: '启用流式响应', default: false },
    { key: 'timeout', label: '超时时间(秒)', type: 'number', description: '请求超时时间', min: 1, max: 600, default: 60 },
  ],
  tool: [
    { key: 'tool_name', label: '工具', type: 'select', description: '选择要调用的工具', options: [] },
    { key: 'params', label: '参数', type: 'json', description: '工具参数，支持 {{var}} 变量引用' },
  ],
  skill: [
    { key: 'skill_id', label: 'Skill', type: 'select', description: '选择要调用的 Skill', options: [], specialHandler: true },
    { key: 'skill_name', label: 'Skill 名称', type: 'text', description: 'Skill 显示名称', readonly: true },
    { key: 'params', label: '参数', type: 'json', description: 'Skill 参数，支持 {{var}} 变量引用' },
  ],
  condition: [
    { key: 'expression', label: '条件表达式', type: 'text', description: '条件判断表达式，支持 ==, !=, >, <, >=, <=, and, or, not 等运算符' },
    { key: 'case_sensitive', label: '大小写敏感', type: 'switch', description: '字符串比较时是否大小写敏感', default: true },
    { key: 'strict_mode', label: '严格模式', type: 'switch', description: '启用后，未定义的变量会抛出错误', default: false },
  ],
  agent: [
    { key: 'agent_name', label: 'Agent', type: 'select', description: '选择要调用的子 Agent', options: [] },
    { key: 'message', label: '消息模板', type: 'textarea', description: '发送给 Agent 的消息模板', rows: 3, fullWidth: true },
    { key: 'timeout', label: '超时时间(秒)', type: 'number', description: 'Agent 执行超时时间', min: 1, max: 600, default: 120 },
    { key: 'max_retries', label: '最大重试次数', type: 'number', description: '执行失败时的重试次数', min: 0, max: 5, default: 0 },
  ],
  code: [
    { key: 'language', label: '编程语言', type: 'select', description: '选择代码执行语言', options: [{ value: 'javascript', label: 'JavaScript' }, { value: 'python', label: 'Python' }] },
    { key: 'code', label: '代码内容', type: 'code', description: '自定义代码，使用 return 返回结果', rows: 8, fullWidth: true },
    { key: 'timeout', label: '执行超时(秒)', type: 'number', description: '代码执行超时时间', min: 1, max: 60, default: 10 },
    { key: 'sandboxed', label: '沙箱模式', type: 'switch', description: '启用沙箱限制代码访问权限', default: true },
  ],
  loop: [
    { key: 'iterate_var', label: '遍历变量', type: 'text', description: '要遍历的列表变量，如 {{input.list}}' },
    { key: 'item_var', label: '迭代项变量名', type: 'text', description: '循环体内引用当前项的变量名', default: 'item' },
    { key: 'max_iterations', label: '最大迭代次数', type: 'number', description: '防止无限循环的安全限制', min: 1, max: 100, default: 10 },
    { key: 'break_on_error', label: '遇错停止', type: 'switch', description: '循环体执行出错时是否立即停止', default: true },
    { key: 'collect_output', label: '收集输出', type: 'switch', description: '是否收集每次迭代的输出结果', default: true },
  ],
  parallel: [
    { key: 'branches', label: '并行分支数', type: 'number', description: '同时执行的分支数量', min: 2, max: 10, default: 2 },
    { key: 'timeout', label: '超时时间(秒)', type: 'number', description: '所有分支完成的超时时间', min: 1, max: 600, default: 120 },
    { key: 'fail_fast', label: '快速失败', type: 'switch', description: '任一分支失败时立即终止所有分支', default: false },
    { key: 'merge_strategy', label: '合并策略', type: 'select', description: '多个分支结果的合并方式', options: [{ value: 'list', label: '列表' }, { value: 'dict', label: '字典' }, { value: 'first', label: '取第一个' }], default: 'list' },
  ],
  transform: [
    { key: 'format', label: '转换格式', type: 'select', description: '目标数据格式', options: [{ value: 'json', label: 'JSON' }, { value: 'yaml', label: 'YAML' }, { value: 'xml', label: 'XML' }, { value: 'text', label: '文本' }] },
    { key: 'mapping', label: '映射规则', type: 'json', description: '数据映射规则，支持 {{var}} 变量引用', fullWidth: true },
    { key: 'pretty', label: '格式化输出', type: 'switch', description: '输出时是否格式化缩进', default: true },
    { key: 'strict', label: '严格模式', type: 'switch', description: '启用后，缺失字段会抛出错误', default: false },
  ],
  delay: [
    { key: 'duration', label: '延迟时长', type: 'number', description: '延迟的时间长度', min: 0, max: 3600, default: 1 },
    { key: 'unit', label: '时间单位', type: 'select', description: '延迟时间的单位', options: [{ value: 'milliseconds', label: '毫秒' }, { value: 'seconds', label: '秒' }, { value: 'minutes', label: '分钟' }, { value: 'hours', label: '小时' }] },
    { key: 'jitter', label: '抖动范围(%)', type: 'number', description: '随机抖动百分比，增加延迟的随机性', min: 0, max: 50, default: 0 },
  ],
  end: [
    { key: 'output_key', label: '输出字段', type: 'text', description: '指定输出的字段路径，留空输出全部上下文' },
    { key: 'format', label: '输出格式', type: 'select', description: '结果输出格式', options: [{ value: 'json', label: 'JSON' }, { value: 'text', label: '纯文本' }], default: 'json' },
    { key: 'include_context', label: '包含上下文', type: 'switch', description: '是否包含完整的工作流上下文', default: false },
  ],
  start: [],
}

const NODE_W = 180
const NODE_H = 72

let _idCounter = 0
function genId(prefix: string) {
  _idCounter++
  return `${prefix}_${Date.now().toString(36)}_${_idCounter}`
}

// 默认节点配置
function defaultConfig(type: string): Record<string, any> {
  switch (type) {
    case 'llm': return { prompt: '{{input}}', system_prompt: '', temperature: 0.7, top_p: 1, max_tokens: 2048, presence_penalty: 0, frequency_penalty: 0, response_format: 'text' }
    case 'tool': return { tool_name: '', params: {} }
    case 'skill': return { skill_id: null, skill_name: '', params: {} }
    case 'condition': return { expression: '' }
    case 'agent': return { agent_name: '', message: '{{input}}' }
    case 'end': return { output_key: '' }
    case 'code': return { code: '# 使用 JavaScript 编写\n// 输入: {{input}}\n// 输出: return result', language: 'javascript' }
    case 'loop': return { iterate_var: '{{input}}', item_var: 'item', max_iterations: 10 }
    case 'parallel': return { branches: [] }
    case 'transform': return { mapping: '{"output": "{{input}}"}', format: 'json' }
    case 'delay': return { duration: 1, unit: 'seconds' }
    default: return {}
  }
}

function defaultName(type: string): string {
  const t = NODE_TYPES.find(n => n.type === type)
  return t ? t.label : type
}

// ===== 组件 =====
export default function WorkflowEditor({ definition, onChange, onSave, onRun, running, savedFingerprint, onDirtyChange, runResult }: WorkflowEditorProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [nodes, setNodes] = useState<WFNode[]>(definition?.nodes || [])
  const [edges, setEdges] = useState<WFEdge[]>(definition?.edges || [])
  const [showConf, setShowConf] = useState(false)
  const [showRunPanel, setShowRunPanel] = useState(false)
  const [runInput, setRunInput] = useState('{}')

  // Undo/Redo 历史栈
  const historyRef = useRef<{ past: WFDefinition[]; future: WFDefinition[] }>({ past: [], future: [] })
  const skipHistoryRef = useRef(false)
  // 指纹比较：避免内部 onChange → 父组件 setDef → 传回 props.definition 触发的"假外部更新"重置历史栈
  const lastEmitFingerprintRef = useRef<string>('')
  const lastExternalFingerprintRef = useRef<string>('')
  const fingerprint = (d: WFDefinition) => JSON.stringify({ nodes: d.nodes, edges: d.edges })


  // 拖拽状态
  const dragRef = useRef<{
    mode: 'node' | 'pan' | 'connect' | 'marquee' | null
    nodeId?: string
    offsetX?: number
    offsetY?: number
    startX?: number
    startY?: number
    fromNodeId?: string
    fromHandle?: string  // 'true' | 'false' | undefined
    tempEdge?: { x1: number; y1: number; x2: number; y2: number }
    marqueeStart?: { x: number; y: number }
    movedNodes?: Map<string, { dx: number; dy: number }>
  }>({ mode: null })
  const [pan, setPan] = useState({ x: 0, y: 0 })
  const [zoom, setZoom] = useState(1)
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [marquee, setMarquee] = useState<{ x: number; y: number; w: number; h: number } | null>(null)
  const [alignGuides, setAlignGuides] = useState<{ v: number[]; h: number[]; snapDx?: number; snapDy?: number }>({ v: [], h: [] })
  const ALIGN_TOLERANCE = 6 // 画布坐标吸附容差
  const [, force] = useState(0)
  const repaint = useCallback(() => force(v => v + 1), [])
  const [hoveredEdgeId, setHoveredEdgeId] = useState<string | null>(null)
  const [snappedPort, setSnappedPort] = useState<{ nodeId: string; x: number; y: number } | null>(null)

  // 右键菜单状态
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; target: 'canvas' | 'node' | 'nodes'; nodeId?: string } | null>(null)

  const selectedId = selectedIds.size === 1 ? Array.from(selectedIds)[0] : null
  const setSelectedId = (id: string | null) => setSelectedIds(id ? new Set([id]) : new Set())

  // 外部 definition 变化 (仅当内容与内部 state 不同、且不是我们自己刚 emit 的回显时才重置)
  useEffect(() => {
    const newFp = fingerprint({ nodes: definition?.nodes || [], edges: definition?.edges || [] })
    const curFp = fingerprint({ nodes, edges })
    if (newFp === lastEmitFingerprintRef.current) return // 自己 emit 的回显, 忽略
    if (newFp === curFp) return                         // 内容没变化 (引用变化但内容相同)
    // 真外部更新 (首次加载 / 保存后 reload / 切换 WF)
    setNodes(definition?.nodes || [])
    setEdges(definition?.edges || [])
    historyRef.current = { past: [], future: [] }
    lastExternalFingerprintRef.current = newFp
    lastEmitFingerprintRef.current = newFp
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [definition])

  // 通知变更
  const emit = useCallback((ns: WFNode[], es: WFEdge[], recordHistory = true) => {
    const entry = ns.find(n => n.type === 'start')?.id || ns[0]?.id
    const def: WFDefinition = { nodes: ns, edges: es, entry }
    if (recordHistory && !skipHistoryRef.current) {
      historyRef.current.past.push({ nodes: [...nodes], edges: [...edges] })
      if (historyRef.current.past.length > 50) historyRef.current.past.shift()
      historyRef.current.future = []
    }
    skipHistoryRef.current = false
    lastEmitFingerprintRef.current = fingerprint(def)
    onChange(def)
  }, [onChange, nodes, edges])

  // dirty 状态：当前编辑内容 != 已保存内容
  const currentFp = fingerprint({ nodes, edges })
  const isDirty = savedFingerprint ? currentFp !== savedFingerprint : historyRef.current.past.length > 0
  useEffect(() => { onDirtyChange?.(isDirty) }, [isDirty, onDirtyChange])

  const undo = useCallback(() => {
    const h = historyRef.current
    if (h.past.length === 0) { toast.error('没有可撤销操作'); return }
    const prev = h.past.pop()!
    h.future.push({ nodes: [...nodes], edges: [...edges] })
    skipHistoryRef.current = true
    setNodes(prev.nodes); setEdges(prev.edges); emit(prev.nodes, prev.edges, false)
  }, [nodes, edges, emit])

  const redo = useCallback(() => {
    const h = historyRef.current
    if (h.future.length === 0) { toast.error('没有可重做操作'); return }
    const next = h.future.pop()!
    h.past.push({ nodes: [...nodes], edges: [...edges] })
    skipHistoryRef.current = true
    setNodes(next.nodes); setEdges(next.edges); emit(next.nodes, next.edges, false)
  }, [nodes, edges, emit])

  // 键盘快捷键：Delete 删除、Ctrl+Z 撤销、Ctrl+Y/Shift+Ctrl+Z 重做、Ctrl+C/V 复制粘贴节点、Ctrl+A 全选
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName
      if (tag === 'INPUT' || tag === 'TEXTAREA') return // 输入框里不抢键
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) { e.preventDefault(); undo(); return }
      if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) { e.preventDefault(); redo(); return }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'c' && selectedIds.size > 0) {
        // 复制所有选中节点（取第一个作标记）
        const first = nodes.find(x => selectedIds.has(x.id))
        if (first) {
          const snap: Record<string, WFNode> = {}
          selectedIds.forEach(id => { const n = nodes.find(x => x.id === id); if (n) snap[id] = n })
          multiClipboardRef.current = snap
          toast.success(`已复制 ${selectedIds.size} 个节点`)
        }
        return
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'v' && multiClipboardRef.current && Object.keys(multiClipboardRef.current).length > 0) {
        e.preventDefault()
        const snap = multiClipboardRef.current
        const oldToNew = new Map<string, string>()
        const newNodes: WFNode[] = []
        Object.values(snap).forEach(n => {
          const nid = genId('n')
          oldToNew.set(n.id, nid)
          newNodes.push({ ...n, id: nid, position: { x: n.position.x + 30, y: n.position.y + 30 }, config: { ...n.config } })
        })
        // 复制这些节点之间的内部连线
        const newEdges: WFEdge[] = []
        edges.forEach(ed => {
          if (snap[ed.source] && snap[ed.target]) {
            newEdges.push({ ...ed, id: genId('e'), source: oldToNew.get(ed.source)!, target: oldToNew.get(ed.target)! })
          }
        })
        const ns = [...nodes, ...newNodes]
        const es = [...edges, ...newEdges]
        setNodes(ns); setEdges(es); emit(ns, es)
        setSelectedIds(new Set(newNodes.map(n => n.id)))
        toast.success(`已粘贴 ${newNodes.length} 个节点`)
        return
      }
      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedIds.size > 0) {
        e.preventDefault()
        const ids = selectedIds
        const hasStart = Array.from(ids).some(id => nodes.find(x => x.id === id)?.type === 'start')
        if (hasStart) { toast.error('不能删除开始节点'); return }
        const ns = nodes.filter(n => !ids.has(n.id))
        const es = edges.filter(ed => !ids.has(ed.source) && !ids.has(ed.target))
        setNodes(ns); setEdges(es); emit(ns, es)
        setSelectedIds(new Set()); setShowConf(false)
      }
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
        e.preventDefault()
        setSelectedIds(new Set(nodes.map(n => n.id)))
      }
      if (e.key === 'Escape') {
        setSelectedIds(new Set()); setShowConf(false)
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nodes, edges, selectedIds, undo, redo])

  // 多选剪贴板
  const multiClipboardRef = useRef<Record<string, WFNode>>({})

  // 滚轮缩放
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (!containerRef.current) return
    e.preventDefault()
    const rect = containerRef.current.getBoundingClientRect()
    const mx = e.clientX - rect.left
    const my = e.clientY - rect.top
    const delta = -e.deltaY * 0.0015
    setZoom(prev => {
      const next = Math.min(2, Math.max(0.3, prev * (1 + delta)))
      // 以鼠标为锚点缩放
      const ratio = next / prev
      setPan(p => ({ x: mx - (mx - p.x) * ratio, y: my - (my - p.y) * ratio }))
      return next
    })
  }, [])

  // ===== 拖拽节点到画布 =====
  const handlePaletteDragStart = (type: string) => (e: React.DragEvent) => {
    e.dataTransfer.setData('node-type', type)
    e.dataTransfer.effectAllowed = 'copy'
  }

  const handleCanvasDrop = (e: React.DragEvent) => {
    e.preventDefault()
    const type = e.dataTransfer.getData('node-type') as WFNode['type']
    if (!type || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const x = (e.clientX - rect.left - pan.x) / zoom - NODE_W / 2
    const y = (e.clientY - rect.top - pan.y) / zoom - NODE_H / 2
    const id = genId('n')
    const newNode: WFNode = {
      id, type, name: defaultName(type), config: defaultConfig(type),
      position: { x: Math.round(x / 10) * 10, y: Math.round(y / 10) * 10 },
    }
    const ns = [...nodes, newNode]
    setNodes(ns); emit(ns, edges)
    setSelectedId(id); setShowConf(true)
  }

  const handleCanvasDragOver = (e: React.DragEvent) => { e.preventDefault(); e.dataTransfer.dropEffect = 'copy' }

  // ===== 节点拖拽移动 =====
  const handleNodeMouseDown = (nodeId: string) => (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.port') || (e.target as HTMLElement).closest('.del-btn')) return
    e.stopPropagation()
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    // 若当前未选中该节点，先设置为单选；否则拖动整个选中组
    let movingSet = selectedIds
    if (!selectedIds.has(nodeId)) {
      movingSet = new Set([nodeId])
      setSelectedIds(movingSet)
    }
    const node = nodes.find(n => n.id === nodeId)!
    // 记录每个被拖动节点相对于鼠标的偏移（画布坐标系）
    const offsetX = (e.clientX - rect.left - pan.x) / zoom - node.position.x
    const offsetY = (e.clientY - rect.top - pan.y) / zoom - node.position.y
    const moved = new Map<string, { dx: number; dy: number }>()
    movingSet.forEach(id => {
      const n = nodes.find(x => x.id === id)
      if (n) moved.set(id, { dx: n.position.x, dy: n.position.y })
    })
    dragRef.current = {
      mode: 'node', nodeId,
      offsetX, offsetY,
      movedNodes: moved,
    }
  }

  // ===== 画布平移 / 框选 =====
  const handleCanvasMouseDown = (e: React.MouseEvent) => {
    if ((e.target as HTMLElement).closest('.wf-node') || (e.target as HTMLElement).closest('.palette') || (e.target as HTMLElement).closest('.canvas-toolbar')) return
    if (e.shiftKey) {
      // 框选
      if (!containerRef.current) return
      const rect = containerRef.current.getBoundingClientRect()
      const sx = (e.clientX - rect.left - pan.x) / zoom
      const sy = (e.clientY - rect.top - pan.y) / zoom
      dragRef.current = { mode: 'marquee', marqueeStart: { x: sx, y: sy } }
      setMarquee({ x: sx, y: sy, w: 0, h: 0 })
      setSelectedIds(new Set())
    } else {
      setSelectedIds(new Set()); setShowConf(false)
      dragRef.current = { mode: 'pan', startX: e.clientX - pan.x, startY: e.clientY - pan.y }
    }
  }

  // ===== 连线 =====
  const handleOutputPortMouseDown = (nodeId: string, handle?: string) => (e: React.MouseEvent) => {
    e.stopPropagation()
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const node = nodes.find(n => n.id === nodeId)!
    // 根据 handle 决定起点 y 坐标
    const isCond = node.type === 'condition'
    let yOffset = NODE_H / 2
    if (isCond && handle === 'true') yOffset = NODE_H / 2 - 8
    else if (isCond && handle === 'false') yOffset = NODE_H / 2 + 8
    dragRef.current = {
      mode: 'connect', fromNodeId: nodeId, fromHandle: handle,
      tempEdge: {
        x1: (node.position.x + NODE_W) * zoom + pan.x,
        y1: (node.position.y + yOffset) * zoom + pan.y,
        x2: e.clientX - rect.left, y2: e.clientY - rect.top,
      },
    }
  }

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const d = dragRef.current
    if (d.mode === 'node' && d.movedNodes) {
      const anchorOrig = d.movedNodes.get(d.nodeId!)
      if (!anchorOrig) return
      let mx = (e.clientX - rect.left - pan.x) / zoom - (d.offsetX || 0)
      let my = (e.clientY - rect.top - pan.y) / zoom - (d.offsetY || 0)
      let dx = mx - anchorOrig.dx
      let dy = my - anchorOrig.dy

      // === 对齐辅助线 + 吸附 ===
      const movingIds = new Set(d.movedNodes.keys())
      const anchor = nodes.find(n => n.id === d.nodeId!)!
      const anchorNewX = anchorOrig.dx + dx
      const anchorNewY = anchorOrig.dy + dy
      // anchor 节点的四条关键边
      const aLeft = anchorNewX, aCenterX = anchorNewX + NODE_W / 2, aRight = anchorNewX + NODE_W
      const aTop = anchorNewY, aCenterY = anchorNewY + NODE_H / 2, aBottom = anchorNewY + NODE_H
      const vGuides: number[] = []
      const hGuides: number[] = []
      let bestDx = 0, bestDy = 0, bestVDist = Infinity, bestHDist = Infinity
      nodes.forEach(n => {
        if (movingIds.has(n.id)) return
        const edges = { l: n.position.x, cx: n.position.x + NODE_W / 2, r: n.position.x + NODE_W,
                        t: n.position.y, cy: n.position.y + NODE_H / 2, b: n.position.y + NODE_H }
        // 垂直方向（x 对齐）比较 aLeft/aCenterX/aRight vs edges.l/cx/r
        ;[['l','l'],['cx','cx'],['r','r'],['l','r'],['r','l']].forEach(([ak, ek]) => {
          const av = (ak === 'l' ? aLeft : ak === 'cx' ? aCenterX : aRight)
          const ev = (ek === 'l' ? edges.l : ek === 'cx' ? edges.cx : edges.r)
          const dist = Math.abs(av - ev)
          if (dist < ALIGN_TOLERANCE && dist < bestVDist) { bestVDist = dist; bestDx = ev - av }
          if (dist < ALIGN_TOLERANCE + 2) vGuides.push(ev)
        })
        // 水平方向（y 对齐）
        ;[['t','t'],['cy','cy'],['b','b'],['t','b'],['b','t']].forEach(([ak, ek]) => {
          const av = (ak === 't' ? aTop : ak === 'cy' ? aCenterY : aBottom)
          const ev = (ek === 't' ? edges.t : ek === 'cy' ? edges.cy : edges.b)
          const dist = Math.abs(av - ev)
          if (dist < ALIGN_TOLERANCE && dist < bestHDist) { bestHDist = dist; bestDy = ev - av }
          if (dist < ALIGN_TOLERANCE + 2) hGuides.push(ev)
        })
      })
      // 应用吸附
      if (bestDx !== 0) dx += bestDx
      if (bestDy !== 0) dy += bestDy
      setAlignGuides({ v: vGuides, h: hGuides, snapDx: bestDx, snapDy: bestDy })

      setNodes(prev => prev.map(n => {
        const orig = d.movedNodes!.get(n.id)
        if (!orig) return n
        return { ...n, position: { x: Math.round((orig.dx + dx) / 10) * 10, y: Math.round((orig.dy + dy) / 10) * 10 } }
      }))
    } else if (d.mode === 'pan') {
      setPan({ x: e.clientX - (d.startX || 0), y: e.clientY - (d.startY || 0) })
    } else if (d.mode === 'marquee' && d.marqueeStart) {
      const cx = (e.clientX - rect.left - pan.x) / zoom
      const cy = (e.clientY - rect.top - pan.y) / zoom
      const x = Math.min(d.marqueeStart.x, cx)
      const y = Math.min(d.marqueeStart.y, cy)
      const w = Math.abs(cx - d.marqueeStart.x)
      const h = Math.abs(cy - d.marqueeStart.y)
      setMarquee({ x, y, w, h })
      // 实时选中
      const hit = new Set<string>()
      nodes.forEach(n => {
        if (n.position.x + NODE_W >= x && n.position.x <= x + w && n.position.y + NODE_H >= y && n.position.y <= y + h) hit.add(n.id)
      })
      setSelectedIds(hit)
    } else if (d.mode === 'connect' && d.tempEdge) {
      let targetX = e.clientX - rect.left
      let targetY = e.clientY - rect.top
      setSnappedPort(null)
      
      // 检测是否靠近输入端口
      const SNAP_DISTANCE = 30
      let closestPortNodeId: string | null = null
      let closestPortX = 0
      let closestPortY = 0
      let minDist = Infinity
      
      nodes.forEach(n => {
        if (n.type === 'start' || n.id === d.fromNodeId) return
        const portX = n.position.x * zoom + pan.x
        const portY = n.position.y * zoom + pan.y + (NODE_H * zoom) / 2
        const dist = Math.sqrt(Math.pow(targetX - portX, 2) + Math.pow(targetY - portY, 2))
        if (dist < SNAP_DISTANCE && dist < minDist) {
          minDist = dist
          closestPortNodeId = n.id
          closestPortX = portX
          closestPortY = portY
        }
      })
      
      if (closestPortNodeId !== null) {
        targetX = closestPortX
        targetY = closestPortY
        setSnappedPort({ nodeId: closestPortNodeId, x: closestPortX, y: closestPortY })
      }
      
      d.tempEdge.x2 = targetX
      d.tempEdge.y2 = targetY
      repaint()
    }
  }, [pan.x, pan.y, zoom, nodes, repaint])

  const handleMouseUp = useCallback((e: MouseEvent) => {
    const d = dragRef.current
    if (d.mode === 'node') {
      setAlignGuides({ v: [], h: [] })
      emit(nodes, edges)
    } else if (d.mode === 'marquee') {
      setMarquee(null)
    } else if (d.mode === 'connect' && d.fromNodeId && containerRef.current) {
      // 检测鼠标是否在某个节点的输入端口上
      const el = document.elementFromPoint(e.clientX, e.clientY) as HTMLElement | null
      const portEl = el?.closest('.input-port') as HTMLElement | null
      if (portEl) {
        const targetId = portEl.getAttribute('data-node')
        if (targetId && targetId !== d.fromNodeId) {
          const exists = edges.some(ed => ed.source === d.fromNodeId && ed.target === targetId && (ed.sourceHandle || '') === (d.fromHandle || ''))
          if (!exists) {
            const srcNode = nodes.find(n => n.id === d.fromNodeId)
            const autoCond = srcNode?.type === 'condition' && d.fromHandle ? d.fromHandle : undefined
            const ne = [...edges, {
              id: genId('e'), source: d.fromNodeId, target: targetId,
              sourceHandle: d.fromHandle,
              condition: autoCond,
            }]
            setEdges(ne); emit(nodes, ne)
          }
        }
      }
    }
    dragRef.current = { mode: null }
    setSnappedPort(null)
    repaint()
  }, [nodes, edges, emit, repaint])

  useEffect(() => {
    window.addEventListener('mousemove', handleMouseMove)
    window.addEventListener('mouseup', handleMouseUp)
    return () => { window.removeEventListener('mousemove', handleMouseMove); window.removeEventListener('mouseup', handleMouseUp) }
  }, [handleMouseMove, handleMouseUp])

  // 点击外部关闭右键菜单
  useEffect(() => {
    const closeMenu = (e: MouseEvent) => {
      if (contextMenu) {
        const menuEl = document.getElementById('wf-context-menu')
        if (menuEl && !menuEl.contains(e.target as Node)) {
          setContextMenu(null)
        }
      }
    }
    window.addEventListener('click', closeMenu)
    return () => window.removeEventListener('click', closeMenu)
  }, [contextMenu])

  // ===== 删除 =====
  const deleteNode = useCallback((id: string) => {
    setNodes(prev => {
      const ns = prev.filter(n => n.id !== id)
      setEdges(prevE => {
        const es = prevE.filter(e => e.source !== id && e.target !== id)
        emit(ns, es)
        return es
      })
      return ns
    })
    setSelectedIds(prev => {
      if (!prev.has(id)) return prev
      const next = new Set(prev); next.delete(id); return next
    })
    setShowConf(s => (selectedIds.size === 1 && selectedIds.has(id)) ? false : s)
  }, [emit, selectedIds])
  const deleteEdge = useCallback((id: string) => {
    setEdges(prev => {
      const es = prev.filter(e => e.id !== id)
      emit(nodes, es)
      return es
    })
  }, [emit, nodes])

  // ===== 更新节点 =====
  const updateNode = useCallback((id: string, patch: Partial<WFNode>) => {
    setNodes(prev => {
      const ns = prev.map(n => n.id === id ? { ...n, ...patch } : n)
      emit(ns, edges)
      return ns
    })
  }, [emit, edges])

  const selectedNode = nodes.find(n => n.id === selectedId) || null

  // 缩放控制
  const zoomBy = useCallback((factor: number) => {
    if (!containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    const cx = rect.width / 2, cy = rect.height / 2
    setZoom(prev => {
      const next = Math.min(2, Math.max(0.3, prev * factor))
      const ratio = next / prev
      setPan(p => ({ x: cx - (cx - p.x) * ratio, y: cy - (cy - p.y) * ratio }))
      return next
    })
  }, [])

  // 适应画布
  const fitView = useCallback(() => {
    if (!containerRef.current || nodes.length === 0) return
    const minX = Math.min(...nodes.map(n => n.position.x)) - 20
    const minY = Math.min(...nodes.map(n => n.position.y)) - 20
    const maxX = Math.max(...nodes.map(n => n.position.x + NODE_W)) + 20
    const maxY = Math.max(...nodes.map(n => n.position.y + NODE_H)) + 20
    const w = maxX - minX, h = maxY - minY
    const rect = containerRef.current.getBoundingClientRect()
    const z = Math.min(1.2, Math.min(rect.width / w, rect.height / h))
    setZoom(z)
    setPan({ x: (rect.width - w * z) / 2 - minX * z, y: (rect.height - h * z) / 2 - minY * z })
  }, [nodes])

  // 清空画布
  const clearCanvas = useCallback(() => {
    if (nodes.length === 0) return
    if (!window.confirm('确定要清空画布吗？所有节点和连线将被删除（开始节点将被保留）。')) return
    const startNode = nodes.find(n => n.type === 'start')
    const newNodes = startNode ? [startNode] : []
    setNodes(newNodes)
    setEdges([])
    emit(newNodes, [])
    setSelectedIds(new Set())
    setShowConf(false)
    setContextMenu(null)
    toast.success('画布已清空')
  }, [nodes, emit])

  // 重命名节点
  const renameNode = useCallback((id: string) => {
    const node = nodes.find(n => n.id === id)
    if (!node) return
    const newName = prompt('输入新的节点名称：', node.name)
    if (newName !== null && newName !== node.name) {
      updateNode(id, { name: newName })
    }
    setContextMenu(null)
  }, [nodes, updateNode])

  // 复制选中节点
  const copySelected = useCallback(() => {
    if (selectedIds.size === 0) {
      toast.error('请先选择节点')
      return
    }
    const snap: Record<string, WFNode> = {}
    selectedIds.forEach(id => { const n = nodes.find(x => x.id === id); if (n) snap[id] = n })
    multiClipboardRef.current = snap
    toast.success(`已复制 ${selectedIds.size} 个节点`)
    setContextMenu(null)
  }, [selectedIds, nodes])

  // 粘贴节点
  const pasteNodes = useCallback(() => {
    if (!multiClipboardRef.current || Object.keys(multiClipboardRef.current).length === 0) {
      toast.error('剪贴板为空')
      return
    }
    const snap = multiClipboardRef.current
    const oldToNew = new Map<string, string>()
    const newNodes: WFNode[] = []
    Object.values(snap).forEach(n => {
      const nid = genId('n')
      oldToNew.set(n.id, nid)
      newNodes.push({ ...n, id: nid, position: { x: n.position.x + 30, y: n.position.y + 30 }, config: { ...n.config } })
    })
    const newEdges: WFEdge[] = []
    edges.forEach(ed => {
      if (snap[ed.source] && snap[ed.target]) {
        newEdges.push({ ...ed, id: genId('e'), source: oldToNew.get(ed.source)!, target: oldToNew.get(ed.target)! })
      }
    })
    const ns = [...nodes, ...newNodes]
    const es = [...edges, ...newEdges]
    setNodes(ns); setEdges(es); emit(ns, es)
    setSelectedIds(new Set(newNodes.map(n => n.id)))
    toast.success(`已粘贴 ${newNodes.length} 个节点`)
    setContextMenu(null)
  }, [nodes, edges, emit])

  // 删除选中节点
  const deleteSelected = useCallback(() => {
    if (selectedIds.size === 0) {
      toast.error('请先选择节点')
      return
    }
    const hasStart = Array.from(selectedIds).some(id => nodes.find(x => x.id === id)?.type === 'start')
    if (hasStart) {
      toast.error('不能删除开始节点')
      return
    }
    const ns = nodes.filter(n => !selectedIds.has(n.id))
    const es = edges.filter(ed => !selectedIds.has(ed.source) && !selectedIds.has(ed.target))
    setNodes(ns); setEdges(es); emit(ns, es)
    setSelectedIds(new Set()); setShowConf(false)
    setContextMenu(null)
    toast.success(`已删除 ${selectedIds.size} 个节点`)
  }, [selectedIds, nodes, edges, emit])

  // 处理右键点击
  const handleContextMenu = useCallback((e: React.MouseEvent, target: 'canvas' | 'node', nodeId?: string) => {
    e.preventDefault()
    if (target === 'canvas') {
      setContextMenu({ x: e.clientX, y: e.clientY, target: selectedIds.size > 1 ? 'nodes' : 'canvas' })
    } else {
      setContextMenu({ x: e.clientX, y: e.clientY, target: 'node', nodeId })
    }
  }, [selectedIds])

  // 自动布局
  const autoLayout = useCallback(() => {
    if (nodes.length === 0) return
    // 基于BFS的层级布局
    const graph = new Map<string, string[]>()
    const reverseGraph = new Map<string, string[]>()
    
    // 构建正向图和反向图
    nodes.forEach(n => { graph.set(n.id, []); reverseGraph.set(n.id, []) })
    edges.forEach(e => {
      const arr = graph.get(e.source) || []
      arr.push(e.target)
      graph.set(e.source, arr)
      const revArr = reverseGraph.get(e.target) || []
      revArr.push(e.source)
      reverseGraph.set(e.target, revArr)
    })

    // 找到所有入度为0的节点作为起点（通常是start节点）
    const startNodes = nodes.filter(n => (reverseGraph.get(n.id) || []).length === 0).map(n => n.id)
    
    // 使用BFS计算层级
    const levelMap = new Map<string, number>()
    const queue = [...startNodes]
    startNodes.forEach(id => levelMap.set(id, 0))
    
    while (queue.length > 0) {
      const id = queue.shift()!
      const currentLevel = levelMap.get(id)!
      ;(graph.get(id) || []).forEach(child => {
        if (!levelMap.has(child) || levelMap.get(child)! < currentLevel + 1) {
          levelMap.set(child, currentLevel + 1)
          queue.push(child)
        }
      })
    }

    // 计算每层节点数
    const levelNodes = new Map<number, string[]>()
    nodes.forEach(n => {
      const level = levelMap.get(n.id) || 0
      const arr = levelNodes.get(level) || []
      arr.push(n.id)
      levelNodes.set(level, arr)
    })

    const maxLevel = Math.max(...Array.from(levelMap.values()), 0)

    const HORIZONTAL_GAP = 100
    const VERTICAL_GAP = 80
    const startX = 50
    const startY = 50

    const newNodes = nodes.map(n => {
      const level = levelMap.get(n.id) || 0
      const levelList = levelNodes.get(level)!
      const idx = levelList.indexOf(n.id)
      const x = startX + level * (NODE_W + HORIZONTAL_GAP)
      const y = startY + idx * (NODE_H + VERTICAL_GAP)
      return { ...n, position: { x: Math.round(x / 10) * 10, y: Math.round(y / 10) * 10 } }
    })

    setNodes(newNodes)
    emit(newNodes, edges)
    toast.success('自动布局完成')
  }, [nodes, edges, emit])

  // ===== 连线条件编辑 =====
  const [editingEdge, setEditingEdge] = useState<WFEdge | null>(null)
  const [edgeCond, setEdgeCond] = useState('')

  const saveEdgeCond = () => {
    if (!editingEdge) return
    const es = edges.map(e => e.id === editingEdge.id ? { ...e, condition: edgeCond || undefined } : e)
    setEdges(es); emit(nodes, es); setEditingEdge(null)
  }

  // ===== 路径生成 =====
  const [edgeMode, setEdgeMode] = useState<'bezier' | 'orthogonal' | 'straight'>(() => {
    return (localStorage.getItem('wf_edge_mode') as any) || 'bezier'
  })
  useEffect(() => { localStorage.setItem('wf_edge_mode', edgeMode) }, [edgeMode])

  const bezierPath = (x1: number, y1: number, x2: number, y2: number) => {
    const dx = Math.abs(x2 - x1) * 0.5
    return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
  }
  const straightPath = (x1: number, y1: number, x2: number, y2: number) => `M ${x1} ${y1} L ${x2} ${y2}`
  const orthogonalPath = (x1: number, y1: number, x2: number, y2: number) => {
    // 直角连线：先水平到中点，再垂直，再水平到终点
    const dx = x2 - x1
    const midX = x1 + dx / 2
    return `M ${x1} ${y1} L ${midX} ${y1} L ${midX} ${y2} L ${x2} ${y2}`
  }
  const edgePath = (x1: number, y1: number, x2: number, y2: number) => {
    if (edgeMode === 'straight') return straightPath(x1, y1, x2, y2)
    if (edgeMode === 'orthogonal') return orthogonalPath(x1, y1, x2, y2)
    return bezierPath(x1, y1, x2, y2)
  }

  const nodeAbsPos = (n: WFNode) => ({
    x: n.position.x * zoom + pan.x,
    y: n.position.y * zoom + pan.y,
  })

  return (
    <div className="flex h-full gap-3 min-h-[600px] flex-col lg:flex-row">
      {/* 左侧面板：节点调色板 */}
      <div className="palette w-full lg:w-48 shrink-0 flex lg:flex-col gap-2 overflow-x-auto lg:overflow-visible">
        <div className="text-xs text-tertiary uppercase tracking-wider px-1 mb-1 hidden lg:block">节点</div>
        <div className="flex lg:flex-col gap-2">
        {NODE_TYPES.map(t => (
          <div
            key={t.type}
            draggable
            onDragStart={handlePaletteDragStart(t.type)}
            className="flex items-center gap-2 p-2.5 rounded-xl bg-card border border hover:bg-hover hover:border cursor-grab active:cursor-grabbing transition-all group shrink-0 min-w-[130px]"
          >
            <div className="w-8 h-8 rounded-lg flex items-center justify-center text-lg shrink-0"
              style={{ background: t.color + '20', border: `1px solid ${t.color}40` }}>
              {t.icon}
            </div>
            <div className="min-w-0 hidden sm:block">
              <div className="text-sm font-medium">{t.label}</div>
              <div className="text-[11px] text-placeholder truncate">{t.desc}</div>
            </div>
          </div>
        ))}
        </div>
        <div className="mt-auto pt-3 border-t border space-y-2 flex lg:block gap-2">
          <Button variant="secondary" className="flex-1 lg:w-full text-sm py-2 relative" onClick={onSave} disabled={nodes.length === 0}>
            💾 保存{isDirty && <span className="absolute top-1.5 right-1.5 w-2 h-2 rounded-full bg-amber-400 animate-pulse" title="有未保存的更改"></span>}
          </Button>
          <Button variant="primary" className="flex-1 lg:w-full text-sm py-2" onClick={() => setShowRunPanel(true)} disabled={nodes.length === 0 || running}>
            {running ? '⏳ 运行中...' : '▶️ 运行'}
          </Button>
        </div>
      </div>

      {/* 中间画布 */}
      <div
        ref={containerRef}
        className="flex-1 relative rounded-2xl bg-black/30 border border overflow-hidden cursor-grab active:cursor-grabbing min-h-[600px]"
        onDrop={handleCanvasDrop}
        onDragOver={handleCanvasDragOver}
        onMouseDown={handleCanvasMouseDown}
        onWheel={handleWheel}
        onContextMenu={(e) => handleContextMenu(e, 'canvas')}
        style={{ backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.06) 1px, transparent 1px)', backgroundSize: `${20 * zoom}px ${20 * zoom}px`, backgroundPosition: `${pan.x}px ${pan.y}px` }}
      >
        {/* SVG 连线层 */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ zIndex: 1 }}>
          <defs>
            <marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="rgba(255,255,255,0.4)" />
            </marker>
            <marker id="arrowhead-active" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">
              <polygon points="0 0, 10 3.5, 0 7" fill="#06B6D4" />
            </marker>
          </defs>
          {edges.map(e => {
            const s = nodes.find(n => n.id === e.source)
            const t = nodes.find(n => n.id === e.target)
            if (!s || !t) return null
            const sp = nodeAbsPos(s), tp = nodeAbsPos(t)
            // 根据 sourceHandle 调整起点 y
            let syOffset = NODE_H / 2
            if (s.type === 'condition' && e.sourceHandle === 'true') syOffset = NODE_H / 2 - 8
            else if (s.type === 'condition' && e.sourceHandle === 'false') syOffset = NODE_H / 2 + 8
            const x1 = sp.x + NODE_W * zoom, y1 = sp.y + syOffset * zoom
            const x2 = tp.x, y2 = tp.y + (NODE_H * zoom) / 2
            const edgeColor = e.condition === 'true' ? '#10B981' : e.condition === 'false' ? '#F43F5E' : (e.condition ? '#EC4899' : 'rgba(255,255,255,0.4)')
            const isHovered = hoveredEdgeId === e.id
            return (
              <g 
                key={e.id} 
                className="pointer-events-auto cursor-pointer transition-all duration-200"
                onMouseEnter={() => setHoveredEdgeId(e.id)}
                onMouseLeave={() => setHoveredEdgeId(null)}
                onDoubleClick={() => { setEditingEdge(e); setEdgeCond(e.condition || '') }} 
                onClick={(ev) => { if (ev.shiftKey) deleteEdge(e.id) }}
              >
                <path d={edgePath(x1, y1, x2, y2)} stroke="transparent" strokeWidth={isHovered ? 24 : 16} fill="none" />
                <path d={edgePath(x1, y1, x2, y2)} stroke={isHovered ? '#06B6D4' : edgeColor} strokeWidth={isHovered ? 3 : 2} fill="none" markerEnd={isHovered ? 'url(#arrowhead-active)' : 'url(#arrowhead)'} />
                {e.condition && (() => {
                  const mx = (x1 + x2) / 2, my = (y1 + y2) / 2
                  const label = e.condition
                  const w = Math.max(28, label.length * 7 + 12)
                  return <g>
                    <rect x={mx - w / 2} y={my - 10} width={w} height={20} rx={6} fill={isHovered ? '#06B6D430' : edgeColor + '30'} stroke={isHovered ? '#06B6D470' : edgeColor + '70'} />
                    <text x={mx} y={my + 4} textAnchor="middle" fill="#fff" fontSize={11}>{label}</text>
                  </g>
                })()}
              </g>
            )
          })}
          {dragRef.current.mode === 'connect' && dragRef.current.tempEdge && (
            <path d={edgePath(dragRef.current.tempEdge.x1, dragRef.current.tempEdge.y1, dragRef.current.tempEdge.x2, dragRef.current.tempEdge.y2)}
              stroke="#06B6D4" strokeWidth={2} strokeDasharray="6 3" fill="none" />
          )}
          {/* 框选矩形 */}
          {marquee && (
            <rect
              x={marquee.x * zoom + pan.x}
              y={marquee.y * zoom + pan.y}
              width={marquee.w * zoom}
              height={marquee.h * zoom}
              fill="rgba(6,182,212,0.1)"
              stroke="#06B6D4"
              strokeWidth={1}
              strokeDasharray="4 3"
            />
          )}
          {/* 对齐辅助线 */}
          {alignGuides.v.map((gx, i) => (
            <line key={`v${i}`} x1={gx * zoom + pan.x} y1={0} x2={gx * zoom + pan.x} y2="100%"
              stroke="#F59E0B" strokeWidth={1} strokeDasharray="4 3" opacity={0.8} pointerEvents="none" />
          ))}
          {alignGuides.h.map((gy, i) => (
            <line key={`h${i}`} x1={0} y1={gy * zoom + pan.y} x2="100%" y2={gy * zoom + pan.y}
              stroke="#F59E0B" strokeWidth={1} strokeDasharray="4 3" opacity={0.8} pointerEvents="none" />
          ))}
        </svg>

        {/* 节点层 */}
        <div className="absolute inset-0 origin-top-left" style={{ zIndex: 2, transform: `translate(${pan.x}px, ${pan.y}px) scale(${zoom})` }}>
          {nodes.map(n => {
            const t = NODE_TYPES.find(nt => nt.type === n.type)
            const isSel = selectedIds.has(n.id)
            return (
              <div
                key={n.id}
                className={`wf-node absolute rounded-xl border transition-all select-none ${isSel ? 'shadow-lg shadow-cyan-500/30' : ''}`}
                style={{
                  left: n.position.x, top: n.position.y, width: NODE_W, height: NODE_H,
                  background: 'rgba(15,23,42,0.9)', backdropFilter: 'blur(12px)',
                  borderColor: isSel ? t?.color : 'rgba(255,255,255,0.15)',
                  borderWidth: isSel ? 2 : 1,
                  cursor: dragRef.current.mode === 'node' ? 'grabbing' : 'grab',
                }}
                onMouseDown={handleNodeMouseDown(n.id)}
                onClick={(e) => {
                  e.stopPropagation()
                  if (e.shiftKey) {
                    setSelectedIds(prev => {
                      const next = new Set(prev)
                      if (next.has(n.id)) next.delete(n.id); else next.add(n.id)
                      return next
                    })
                  } else if (!selectedIds.has(n.id)) {
                    setSelectedIds(new Set([n.id]))
                  }
                }}
                onDoubleClick={() => { setSelectedIds(new Set([n.id])); setShowConf(true) }}
                onContextMenu={(e) => { e.stopPropagation(); handleContextMenu(e, 'node', n.id) }}
              >
                <div className="flex items-center gap-2 p-2.5 h-full">
                  <div className="w-9 h-9 rounded-lg flex items-center justify-center text-lg shrink-0"
                    style={{ background: (t?.color || '#888') + '25', border: `1px solid ${t?.color || '#888'}50` }}>
                    {t?.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{n.name}</div>
                    <div className="text-[11px] text-placeholder truncate">
                      {n.type === 'llm' && (n.config.prompt || '').slice(0, 20)}
                      {n.type === 'tool' && n.config.tool_name}
                      {n.type === 'skill' && n.config.skill_name}
                      {n.type === 'agent' && n.config.agent_name}
                      {n.type === 'condition' && (n.config.expression || '未设置条件')}
                      {n.type === 'start' && '输入入口'}
                      {n.type === 'end' && (n.config.output_key ? n.config.output_key.slice(0, 16) : '输出全部')}
                      {n.type === 'code' && 'JS代码'}
                      {n.type === 'loop' && `遍历 ${n.config.item_var || 'item'}`}
                      {n.type === 'parallel' && `${n.config.branches?.length || 0} 个分支`}
                      {n.type === 'transform' && n.config.format}
                      {n.type === 'delay' && `${n.config.duration}${n.config.unit?.slice(0, 1)}`}
                    </div>
                  </div>
                  <button className="del-btn w-5 h-5 rounded text-placeholder hover:text-red-400 hover:bg-red-500/20 flex items-center justify-center text-xs"
                    onClick={(e) => { e.stopPropagation(); deleteNode(n.id) }}>✕</button>
                </div>
                {/* 输入端口 */}
                {n.type !== 'start' && (
                  <div className={`input-port port absolute rounded-full border-2 cursor-crosshair transition-all ${snappedPort?.nodeId === n.id ? 'w-6 h-6 bg-cyan-400 border-cyan-300 shadow-lg shadow-cyan-400/50 animate-pulse' : 'w-3 h-3 bg-active hover:bg-cyan-400 border-slate-700'}`}
                    data-node={n.id}
                    style={{ left: snappedPort?.nodeId === n.id ? -12 : -6, top: snappedPort?.nodeId === n.id ? NODE_H / 2 - 12 : NODE_H / 2 - 6 }}
                    title="输入端口"
                  />
                )}
                {/* 输出端口：condition 显示 true/false 双端口 */}
                {n.type === 'condition' ? (
                  <>
                    <div className="output-port port absolute w-3 h-3 rounded-full bg-emerald-400/80 hover:bg-emerald-300 border-2 border-slate-700 cursor-crosshair"
                      onMouseDown={handleOutputPortMouseDown(n.id, 'true')}
                      style={{ right: -6, top: NODE_H / 2 - 14 }}
                      title="TRUE 分支（条件为真时走此路）"
                    />
                    <div className="output-port port absolute w-3 h-3 rounded-full bg-rose-400/80 hover:bg-rose-300 border-2 border-slate-700 cursor-crosshair"
                      onMouseDown={handleOutputPortMouseDown(n.id, 'false')}
                      style={{ right: -6, top: NODE_H / 2 + 2 }}
                      title="FALSE 分支（条件为假时走此路）"
                    />
                    <div className="absolute text-[9px] font-mono text-emerald-300 pointer-events-none"
                      style={{ right: 2, top: NODE_H / 2 - 22 }}>T</div>
                    <div className="absolute text-[9px] font-mono text-rose-300 pointer-events-none"
                      style={{ right: 2, top: NODE_H / 2 + 10 }}>F</div>
                  </>
                ) : n.type !== 'end' && (
                  <div className="output-port port absolute w-3 h-3 rounded-full bg-active hover:bg-cyan-400 border-2 border-slate-700 cursor-crosshair"
                    onMouseDown={handleOutputPortMouseDown(n.id)}
                    style={{ right: -6, top: NODE_H / 2 - 6 }}
                    title="拖拽连接到目标节点输入端口"
                  />
                )}
              </div>
            )
          })}
        </div>

        {/* 空状态 */}
        {nodes.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="text-center text-placeholder">
              <div className="text-5xl mb-3">🎨</div>
              <div className="text-lg font-medium">拖拽左侧节点到画布开始编排</div>
              <div className="text-sm mt-1">从节点右侧端口拖到另一节点左侧端口建立连线 · Shift+点击连线删除 · 双击连线设置条件</div>
            </div>
          </div>
        )}

        {/* 操作提示 */}
        <div className="absolute bottom-3 left-3 text-[11px] text-placeholder pointer-events-none">
          💡 滚轮缩放 · Shift+拖框选 · Del/Ctrl+A/C/V/Z · 双击编辑
        </div>
        {/* 画布工具栏：撤销重做 / 缩放 */}
        <div className="canvas-toolbar absolute top-3 right-3 flex items-center gap-1">
          <button onClick={undo} title="撤销 (Ctrl+Z)" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">↶</button>
          <button onClick={redo} title="重做 (Ctrl+Y)" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">↷</button>
          <div className="w-px h-6 bg-hover mx-1" />
          <button onClick={() => zoomBy(1 / 1.2)} title="缩小" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">−</button>
          <span className="text-xs text-tertiary w-12 text-center font-mono" title="重置缩放">{Math.round(zoom * 100)}%</span>
          <button onClick={() => zoomBy(1.2)} title="放大" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">+</button>
          <button onClick={fitView} title="适应画布" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">⛶</button>
          <button onClick={autoLayout} title="自动布局" className="w-8 h-8 rounded-lg bg-hover hover:bg-active text-sm border border transition-colors">📐</button>
          <div className="w-px h-6 bg-hover mx-1" />
          <div className="flex bg-card rounded-lg p-0.5 text-xs" title="连线模式">
            <button onClick={() => setEdgeMode('bezier')}
              className={`px-2 py-1 rounded transition ${edgeMode === 'bezier' ? 'bg-active' : 'text-tertiary hover:text-primary'}`}>⤳贝塞尔</button>
            <button onClick={() => setEdgeMode('orthogonal')}
              className={`px-2 py-1 rounded transition ${edgeMode === 'orthogonal' ? 'bg-active' : 'text-tertiary hover:text-primary'}`}>└直角</button>
            <button onClick={() => setEdgeMode('straight')}
              className={`px-2 py-1 rounded transition ${edgeMode === 'straight' ? 'bg-active' : 'text-tertiary hover:text-primary'}`}>╱直线</button>
          </div>
        </div>

        {/* 右键菜单 */}
        {contextMenu && (
          <div
            id="wf-context-menu"
            className="fixed z-50 bg-card border border rounded-xl shadow-xl py-1 min-w-[160px]"
            style={{
              left: contextMenu.x,
              top: contextMenu.y,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            {contextMenu.target === 'canvas' && (
              <>
                <button onClick={pasteNodes} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>📋</span> 粘贴
                </button>
                <button onClick={autoLayout} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>📐</span> 自动布局
                </button>
                <button onClick={fitView} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>⛶</span> 适应画布
                </button>
                <div className="border-t border my-1" />
                <button onClick={clearCanvas} className="w-full px-3 py-2 text-sm text-left hover:bg-hover text-red-300 flex items-center gap-2">
                  <span>🗑️</span> 清空画布
                </button>
              </>
            )}
            {contextMenu.target === 'node' && contextMenu.nodeId && (
              <>
                <button onClick={() => { setSelectedIds(new Set([contextMenu.nodeId!])); setShowConf(true); setContextMenu(null) }} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>⚙️</span> 编辑配置
                </button>
                <button onClick={() => renameNode(contextMenu.nodeId!)} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>✏️</span> 重命名
                </button>
                <button onClick={() => { setSelectedIds(new Set([contextMenu.nodeId!])); copySelected() }} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>📋</span> 复制
                </button>
                <div className="border-t border my-1" />
                <button onClick={() => { deleteNode(contextMenu.nodeId!); setContextMenu(null) }} className="w-full px-3 py-2 text-sm text-left hover:bg-hover text-red-300 flex items-center gap-2">
                  <span>🗑️</span> 删除
                </button>
              </>
            )}
            {contextMenu.target === 'nodes' && (
              <>
                <button onClick={copySelected} className="w-full px-3 py-2 text-sm text-left hover:bg-hover flex items-center gap-2">
                  <span>📋</span> 复制 ({selectedIds.size})
                </button>
                <button onClick={deleteSelected} className="w-full px-3 py-2 text-sm text-left hover:bg-hover text-red-300 flex items-center gap-2">
                  <span>🗑️</span> 删除 ({selectedIds.size})
                </button>
              </>
            )}
          </div>
        )}

        {/* Minimap 缩略图 */}
        {nodes.length > 0 && containerRef.current && (
          <Minimap
            nodes={nodes}
            pan={pan}
            zoom={zoom}
            viewportW={containerRef.current.clientWidth}
            viewportH={containerRef.current.clientHeight}
            onJump={(nx, ny) => setPan({ x: nx, y: ny })}
          />
        )}
      </div>

      {/* 右侧节点配置面板 */}
      {selectedNode && showConf && (
        <div className="w-full lg:w-80 shrink-0 rounded-2xl bg-card border border p-4 overflow-y-auto max-h-[600px]">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-sm">节点配置</h3>
            <button className="w-6 h-6 rounded hover:bg-hover flex items-center justify-center text-tertiary" onClick={() => setShowConf(false)}>✕</button>
          </div>
          <NodeConfigForm node={selectedNode} onChange={(patch) => updateNode(selectedNode.id, patch)} nodes={nodes} />
        </div>
      )}

      {/* 运行面板 Modal */}
      <Modal isOpen={showRunPanel} onClose={() => setShowRunPanel(false)} title="运行工作流" width="max-w-2xl">
        <div className="space-y-3">
          <div>
            <label className="block text-sm text-secondary mb-1">输入参数 (JSON)</label>
            <textarea value={runInput} onChange={e => setRunInput(e.target.value)} rows={4}
              className="glass-input font-mono text-sm resize-none" placeholder='{"key": "value"}' />
          </div>
          <div className="flex gap-2 justify-end">
            <Button variant="secondary" onClick={() => setShowRunPanel(false)}>取消</Button>
            <Button variant="primary" onClick={() => {
              try { JSON.parse(runInput) } catch { toast.error('JSON 格式错误'); return }
              setShowRunPanel(false); onRun && onRun()
            }}>🚀 运行</Button>
          </div>
        </div>
      </Modal>

      {/* 运行结果 Modal */}
      <Modal isOpen={!!runResult} onClose={() => onRun && null} title="运行结果" width="max-w-3xl">
        {runResult && (
          <div className="space-y-3">
            <div className={`badge ${runResult.status === 'success' ? 'badge-success' : 'badge-error'}`}>
              {runResult.status === 'success' ? '✅ 执行成功' : '❌ 执行失败'}
            </div>
            {runResult.error && <div className="text-red-400 text-sm bg-red-500/10 rounded-lg p-3 border border-red-500/20">{runResult.error}</div>}
            <div>
              <div className="text-sm text-secondary mb-1">执行日志</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-primary max-h-64 overflow-y-auto whitespace-pre-wrap">
                {runResult.logs.join('\n')}
              </pre>
            </div>
            <div>
              <div className="text-sm text-secondary mb-1">输出结果</div>
              <pre className="bg-black/40 rounded-xl p-3 text-xs font-mono text-cyan-300 max-h-48 overflow-y-auto">
                {JSON.stringify(runResult.output, null, 2)}
              </pre>
            </div>
            <div className="flex justify-end">
              <Button variant="secondary" onClick={() => {/* close handled by parent */ }}>关闭</Button>
            </div>
          </div>
        )}
      </Modal>

      {/* 连线条件编辑 Modal */}
      <Modal isOpen={!!editingEdge} onClose={() => setEditingEdge(null)} title="连线条件" width="max-w-md">
        <div className="space-y-3">
          <p className="text-sm text-tertiary">
            填写条件值以实现分支。支持值：
            <br />• <code className="text-pink-300">true</code> / <code className="text-pink-300">truthy</code> — 条件为真时走此分支
            <br />• <code className="text-pink-300">false</code> / <code className="text-pink-300">falsy</code> — 条件为假时走此分支
            <br />• 其他值会与 condition 节点输出比较
          </p>
          <input className="glass-input" placeholder="例如: true" value={edgeCond} onChange={e => setEdgeCond(e.target.value)} />
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setEdgeCond('')}>清除</Button>
            <Button variant="secondary" onClick={() => setEditingEdge(null)}>取消</Button>
            <Button variant="primary" onClick={saveEdgeCond}>确定</Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

// ===== 通用参数渲染组件 =====
function ParamRenderer({ field, value, onChange, options, id }: { 
  field: ParamField; 
  value: any; 
  onChange: (val: any) => void;
  options?: { value: any; label: string }[] 
  id?: string
}) {
  const opts = options || field.options || []
  
  const renderField = () => {
    switch (field.type) {
      case 'text':
        return (
          <input 
            id={id}
            className="glass-input text-sm py-2" 
            placeholder={field.placeholder || ''}
            value={value || ''} 
            onChange={e => onChange(e.target.value)}
            readOnly={field.readonly}
          />
        )
      case 'number':
        return (
          <input 
            type="number" 
            className="glass-input text-sm py-2"
            min={field.min}
            max={field.max}
            step={field.step}
            placeholder={field.placeholder || ''}
            value={value || ''} 
            onChange={e => onChange(e.target.value ? parseFloat(e.target.value) : '')}
          />
        )
      case 'slider':
        const sliderValue = value ?? field.default ?? 0
        return (
          <div>
            <input 
              type="range" 
              min={field.min} 
              max={field.max} 
              step={field.step}
              className="w-full"
              value={sliderValue} 
              onChange={e => onChange(parseFloat(e.target.value))}
            />
            <div className="text-xs text-tertiary mt-1 font-mono">{sliderValue.toFixed(field.step && field.step < 1 ? 2 : 0)}</div>
          </div>
        )
      case 'select':
        return (
          <select 
            className="glass-input text-sm py-2"
            value={value || ''}
            onChange={e => onChange(e.target.value)}
          >
            <option value="">— 请选择 —</option>
            {opts.map(o => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        )
      case 'switch':
        return (
          <button 
            type="button"
            className={`w-12 h-6 rounded-full transition-colors relative ${value ? 'bg-cyan-500' : 'bg-slate-600'}`}
            onClick={() => onChange(!value)}
          >
            <div className={`absolute top-1 w-4 h-4 rounded-full bg-white transition-transform ${value ? 'translate-x-7' : 'translate-x-1'}`} />
          </button>
        )
      case 'textarea':
        return (
          <textarea 
            id={id}
            className="glass-input text-sm py-2 resize-none"
            rows={field.rows || 3}
            placeholder={field.placeholder || ''}
            value={value || ''}
            onChange={e => onChange(e.target.value)}
          />
        )
      case 'json':
        return (
          <textarea 
            className="glass-input text-sm py-2 resize-none font-mono text-xs"
            rows={4}
            placeholder={field.placeholder || '{}'}
            value={typeof value === 'object' ? JSON.stringify(value, null, 2) : (value || '')}
            onChange={e => {
              try { onChange(JSON.parse(e.target.value)) } catch {}
            }}
          />
        )
      case 'code':
        return (
          <textarea 
            className="glass-input text-sm py-2 resize-none font-mono text-xs bg-black/40"
            rows={field.rows || 6}
            placeholder={field.placeholder || ''}
            value={value || ''}
            onChange={e => onChange(e.target.value)}
          />
        )
      default:
        return null
    }
  }

  return (
    <div className="space-y-1">
      <label className="block text-xs text-tertiary">
        {field.label}
        {field.required && <span className="text-red-400 ml-1">*</span>}
      </label>
      {renderField()}
      {field.description && (
        <p className="text-[11px] text-placeholder mt-1">{field.description}</p>
      )}
    </div>
  )
}

// ===== 节点配置表单 =====
function NodeConfigForm({ node, onChange, nodes }: { node: WFNode; onChange: (p: Partial<WFNode>) => void; nodes: WFNode[] }) {
  const cfg = node.config || {}
  const update = (k: string, v: any) => onChange({ config: { ...cfg, [k]: v } })

  // 加载 meta / agents / skills 供下拉使用
  const providers = useMetaStore(s => s.providers)
  const tools = useMetaStore(s => s.tools)
  const [agentList, setAgentList] = useState<Agent[]>([])
  const [skillList, setSkillList] = useState<Skill[]>([])

  useEffect(() => {
    if (node.type === 'agent') {
      agentsApi.list({ enabled_only: true }).then(setAgentList).catch(() => {})
    }
    if (node.type === 'skill') {
      skillApi.list({ is_active: true }).then(setSkillList).catch(() => {})
    }
  }, [node.type])

  // 上游节点（可为变量引用提供候选）
  const upstream = useMemo(() => {
    return nodes.filter(n => n.id !== node.id && n.type !== 'start')
  }, [nodes, node.id])

  // 可用变量插入
  const insertVar = (target: 'prompt' | 'system_prompt' | 'message' | 'expression' | 'output_key', placeholder: string) => {
    const ta = document.getElementById(`wf-cfg-${target}`) as HTMLTextAreaElement | HTMLInputElement | null
    const cur = cfg[target] || ''
    if (ta) {
      const start = ta.selectionStart ?? cur.length
      const newVal = cur.slice(0, start) + placeholder + cur.slice(start)
      update(target, newVal)
      requestAnimationFrame(() => { ta.focus(); ta.setSelectionRange(start + placeholder.length, start + placeholder.length) })
    } else {
      update(target, cur + placeholder)
    }
  }

  // 解析 providers 结构
  const providerList: { key: string; label: string; models: string[] }[] = useMemo(() => {
    if (!providers) return []
    // providers 可能是对象 {giteeai:{models:[]}, ...} 或数组
    if (Array.isArray(providers)) return providers
    return Object.entries(providers as Record<string, any>).map(([k, v]: [string, any]) => ({
      key: k,
      label: v?.label || v?.name || k,
      models: v?.models || v?.model_list || [],
    }))
  }, [providers])

  return (
    <div className="space-y-3">
      <div>
        <label className="block text-xs text-tertiary mb-1">节点名称</label>
        <input className="glass-input text-sm py-2" value={node.name} onChange={e => onChange({ name: e.target.value })} />
      </div>
      <div>
        <label className="block text-xs text-tertiary mb-1">节点ID</label>
        <input className="glass-input text-sm py-2 font-mono text-xs" value={node.id} readOnly />
      </div>

      {/* 输入参数配置 */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="block text-xs text-tertiary">输入参数</label>
          <button type="button" onClick={() => {
            const params = cfg.input_params || []
            params.push({ name: '', type: 'string', default: '', description: '', required: false, validation: {} })
            update('input_params', [...params])
          }} className="text-[11px] text-brand hover:text-cyan-300">+ 添加参数</button>
        </div>
        {(cfg.input_params || []).map((param: any, idx: number) => (
          <div key={idx} className="bg-card rounded-lg p-2 mb-2 space-y-2">
            <div className="grid grid-cols-3 gap-2">
              <input className="glass-input text-sm py-1" placeholder="参数名" value={param.name || ''} onChange={e => {
                const params = cfg.input_params || []
                params[idx] = { ...params[idx], name: e.target.value }
                update('input_params', [...params])
              }} />
              <select className="glass-input text-sm py-1" value={param.type || 'string'} onChange={e => {
                const params = cfg.input_params || []
                params[idx] = { ...params[idx], type: e.target.value }
                update('input_params', [...params])
              }}>
                <option value="string">字符串</option>
                <option value="number">数字</option>
                <option value="boolean">布尔</option>
                <option value="array">数组</option>
                <option value="object">对象</option>
              </select>
              <div className="flex items-center">
                <input type="checkbox" checked={param.required || false} onChange={e => {
                  const params = cfg.input_params || []
                  params[idx] = { ...params[idx], required: e.target.checked }
                  update('input_params', [...params])
                }} />
                <span className="text-[11px] text-tertiary ml-1">必填</span>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input className="glass-input text-sm py-1" placeholder="默认值" value={param.default || ''} onChange={e => {
                const params = cfg.input_params || []
                params[idx] = { ...params[idx], default: e.target.value }
                update('input_params', [...params])
              }} />
              <input className="glass-input text-sm py-1" placeholder="描述" value={param.description || ''} onChange={e => {
                const params = cfg.input_params || []
                params[idx] = { ...params[idx], description: e.target.value }
                update('input_params', [...params])
              }} />
            </div>
            <button type="button" onClick={() => {
              const params = cfg.input_params || []
              params.splice(idx, 1)
              update('input_params', [...params])
            }} className="text-[11px] text-red-300 hover:text-red-200">删除参数</button>
          </div>
        ))}
      </div>

      {/* 输出参数配置 */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <label className="block text-xs text-tertiary">输出参数</label>
          <button type="button" onClick={() => {
            const params = cfg.output_params || []
            params.push({ name: '', type: 'string', description: '' })
            update('output_params', [...params])
          }} className="text-[11px] text-brand hover:text-cyan-300">+ 添加参数</button>
        </div>
        {(cfg.output_params || []).map((param: any, idx: number) => (
          <div key={idx} className="bg-card rounded-lg p-2 mb-2 space-y-2">
            <div className="grid grid-cols-2 gap-2">
              <input className="glass-input text-sm py-1" placeholder="参数名" value={param.name || ''} onChange={e => {
                const params = cfg.output_params || []
                params[idx] = { ...params[idx], name: e.target.value }
                update('output_params', [...params])
              }} />
              <select className="glass-input text-sm py-1" value={param.type || 'string'} onChange={e => {
                const params = cfg.output_params || []
                params[idx] = { ...params[idx], type: e.target.value }
                update('output_params', [...params])
              }}>
                <option value="string">字符串</option>
                <option value="number">数字</option>
                <option value="boolean">布尔</option>
                <option value="array">数组</option>
                <option value="object">对象</option>
              </select>
            </div>
            <input className="glass-input text-sm py-1" placeholder="描述" value={param.description || ''} onChange={e => {
              const params = cfg.output_params || []
              params[idx] = { ...params[idx], description: e.target.value }
              update('output_params', [...params])
            }} />
            <button type="button" onClick={() => {
              const params = cfg.output_params || []
              params.splice(idx, 1)
              update('output_params', [...params])
            }} className="text-[11px] text-red-300 hover:text-red-200">删除参数</button>
          </div>
        ))}
      </div>

      {/* 插入变量工具栏 */}
      {(node.type === 'llm' || node.type === 'agent' || node.type === 'condition' || node.type === 'end') && upstream.length > 0 && (
        <div>
          <label className="block text-xs text-tertiary mb-1">插入变量</label>
          <div className="flex flex-wrap gap-1">
            <button type="button" onClick={() => insertVar(
              node.type === 'llm' ? 'prompt' : node.type === 'agent' ? 'message' : node.type === 'condition' ? 'expression' : 'output_key',
              '{{input}}'
            )} className="px-2 py-0.5 text-[11px] rounded bg-cyan-500/20 text-cyan-300 hover:bg-cyan-500/30 border border-cyan-500/30">{'{{input}}'}</button>
            {upstream.map(u => {
              const field = u.type === 'llm' ? 'text' : u.type === 'tool' ? 'result' : u.type === 'skill' ? 'output' : u.type === 'agent' ? 'reply' : u.type === 'condition' ? 'condition_result' : 'output'
              const v = `{{${u.id}.${field}}}`
              return (
                <button key={u.id} type="button" onClick={() => insertVar(
                  node.type === 'llm' ? 'prompt' : node.type === 'agent' ? 'message' : node.type === 'condition' ? 'expression' : 'output_key',
                  v
                )} className="px-2 py-0.5 text-[11px] rounded bg-card text-secondary hover:bg-hover border border font-mono" title={u.name}>{v}</button>
              )
            })}
          </div>
        </div>
      )}

      {/* 动态参数配置面板 */}
      {(() => {
        const schema = NODE_PARAM_SCHEMAS[node.type] || []
        if (schema.length === 0) {
          if (node.type === 'start') {
            return <p className="text-xs text-placeholder bg-card rounded-lg p-2">开始节点接收工作流输入参数，可通过 {'{{input.field}}'} 在后续节点中引用。</p>
          }
          return null
        }

        // 动态获取选项列表
        const getOptions = (field: ParamField) => {
          if (field.key === 'provider') return providerList.map(p => ({ value: p.key, label: p.label }))
          if (field.key === 'tool_name') return tools.map(t => ({ value: t.name, label: `${t.display_name} (${t.name})` }))
          if (field.key === 'skill_id') return skillList.map(s => ({ value: s.id, label: `${s.name} - ${s.description?.slice(0, 30)}` }))
          if (field.key === 'agent_name') return agentList.map(a => ({ value: a.name, label: a.display_name || a.name }))
          return field.options || []
        }

        // 特殊处理：branches 和 skill_id 字段
        const handleSpecialField = (field: ParamField) => {
          if (field.key === 'branches') {
            return (
              <div className={`space-y-1 ${field.fullWidth ? 'col-span-2' : ''}`}>
                <label className="block text-xs text-tertiary">
                  {field.label}
                  {field.required && <span className="text-red-400 ml-1">*</span>}
                </label>
                <input 
                  type="number" 
                  className="glass-input text-sm py-2"
                  min={field.min}
                  max={field.max}
                  value={cfg.branches?.length || field.default || 2} 
                  onChange={e => update('branches', Array(parseInt(e.target.value)).fill(null))}
                />
                {field.description && <p className="text-[11px] text-placeholder mt-1">{field.description}</p>}
              </div>
            )
          }
          if (field.key === 'skill_id' && field.specialHandler) {
            return (
              <div className="space-y-1">
                <label className="block text-xs text-tertiary">
                  {field.label}
                  {field.required && <span className="text-red-400 ml-1">*</span>}
                </label>
                <select 
                  className="glass-input text-sm py-2"
                  value={cfg.skill_id || ''}
                  onChange={e => {
                    const id = e.target.value ? parseInt(e.target.value) : null
                    const sk = id ? skillList.find(s => s.id === id) : null
                    update('skill_id', id)
                    update('skill_name', sk?.name || '')
                  }}
                >
                  <option value="">— 请选择 Skill —</option>
                  {getOptions(field).map(o => (
                    <option key={o.value} value={o.value}>{o.label}</option>
                  ))}
                </select>
                {field.description && <p className="text-[11px] text-placeholder mt-1">{field.description}</p>}
              </div>
            )
          }
          return null
        }

        // 获取字段的 element id（用于变量插入）
        const getFieldId = (key: string) => {
          if (key === 'prompt' || key === 'system_prompt' || key === 'message' || key === 'expression' || key === 'output_key') {
            return `wf-cfg-${key}`
          }
          return undefined
        }

        // 按组分组渲染
        const groupedFields = schema.reduce((acc, field) => {
          const group = field.group || 'default'
          if (!acc[group]) acc[group] = []
          acc[group].push(field)
          return acc
        }, {} as Record<string, ParamField[]>)

        return Object.entries(groupedFields).map(([group, fields]) => (
          <div key={group}>
            {group !== 'default' && <h4 className="text-sm font-medium text-secondary mb-2">{group}</h4>}
            <div className="grid grid-cols-2 gap-2">
              {fields.map(field => {
                // 检查依赖条件
                if (field.dependsOn && cfg[field.dependsOn.field] !== field.dependsOn.value) {
                  return null
                }

                // 特殊字段处理
                const special = handleSpecialField(field)
                if (special) return special

                // 使用通用渲染器
                return (
                  <div key={field.key} className={field.fullWidth ? 'col-span-2' : ''}>
                    <ParamRenderer
                      field={field}
                      value={cfg[field.key]}
                      onChange={(val) => update(field.key, val)}
                      options={getOptions(field)}
                      id={getFieldId(field.key)}
                    />
                    {/* 工具特殊信息 */}
                    {field.key === 'tool_name' && cfg.tool_name && tools.find(t => t.name === cfg.tool_name)?.description && (
                      <p className="text-[11px] text-placeholder mt-1">{tools.find(t => t.name === cfg.tool_name)?.description}</p>
                    )}
                    {/* 工具参数 Schema */}
                    {field.key === 'tool_name' && cfg.tool_name && tools.find(t => t.name === cfg.tool_name)?.params_schema && (
                      <details className="mt-1">
                        <summary className="text-[11px] text-brand cursor-pointer">查看参数 Schema</summary>
                        <pre className="text-[10px] text-tertiary mt-1 bg-black/30 rounded p-2 overflow-auto">{JSON.stringify(tools.find(t => t.name === cfg.tool_name)?.params_schema, null, 2)}</pre>
                      </details>
                    )}
                    {/* Model datalist */}
                    {field.key === 'model' && cfg.provider && providerList.find(p => p.key === cfg.provider)?.models?.length && (
                      <datalist id="wf-models">
                        {providerList.find(p => p.key === cfg.provider)!.models.map((m: string) => <option key={m} value={m} />)}
                      </datalist>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        ))
      })()}

      {/* 节点使用提示 */}
      {node.type === 'condition' && (
        <div className="mt-2 text-[11px] text-tertiary space-y-1 bg-card rounded p-2">
          <div className="font-medium text-secondary">💡 提示：</div>
          <div>• 从节点右侧 <span className="text-emerald-400">T</span> 端口连线 = true 分支</div>
          <div>• 从节点右侧 <span className="text-rose-400">F</span> 端口连线 = false 分支</div>
          <div>• 可用运算符：== != &gt; &lt; &gt;= &lt;= and or not in len()</div>
          <div>• 支持 {'{{node_id.field}}'} 变量引用，使用上方"插入变量"</div>
        </div>
      )}

      {node.type === 'code' && (
        <div className="mt-2 text-[11px] text-tertiary space-y-1 bg-card rounded p-2">
          <div className="font-medium text-secondary">💡 代码编写提示：</div>
          <div>• 使用 {'{{input}}'} 或 {'{{node_id.field}}'} 引用上游数据</div>
          <div>• JavaScript: 使用 return 返回结果</div>
          <div>• Python: 使用 return 返回结果</div>
        </div>
      )}

      {node.type === 'loop' && (
        <div className="mt-2 text-[11px] text-tertiary space-y-1 bg-card rounded p-2">
          <div className="font-medium text-secondary">💡 使用提示：</div>
          <div>• 将循环体节点连接到循环节点的输出端口</div>
          <div>• 在循环体内使用 {'{{loop.item}}'} 引用当前项</div>
          <div>• 使用 {'{{loop.index}}'} 获取当前索引</div>
        </div>
      )}

      {node.type === 'parallel' && (
        <div className="mt-2 text-[11px] text-tertiary space-y-1 bg-card rounded p-2">
          <div className="font-medium text-secondary">💡 使用提示：</div>
          <div>• 将多个分支节点连接到并行节点的输出端口</div>
          <div>• 所有分支同时执行，等待全部完成后继续</div>
        </div>
      )}

      {node.type === 'transform' && (
        <div className="mt-2 text-[11px] text-tertiary space-y-1 bg-card rounded p-2">
          <div className="font-medium text-secondary">💡 映射示例：</div>
          <div>• JSON: {'{"result": "{{input.data}}"}'}</div>
          <div>• 文本: {'"结果: {{input.value}}"'}</div>
        </div>
      )}
    </div>
  )
}

// ===== Minimap 缩略图 =====
const MINIMAP_W = 180
const MINIMAP_H = 120
function Minimap({ nodes, pan, zoom, viewportW, viewportH, onJump }: {
  nodes: WFNode[]
  pan: { x: number; y: number }
  zoom: number
  viewportW: number
  viewportH: number
  onJump: (x: number, y: number) => void
}) {
  if (nodes.length === 0) return null
  const PAD = 20
  const minX = Math.min(...nodes.map(n => n.position.x)) - PAD
  const minY = Math.min(...nodes.map(n => n.position.y)) - PAD
  const maxX = Math.max(...nodes.map(n => n.position.x + NODE_W)) + PAD
  const maxY = Math.max(...nodes.map(n => n.position.y + NODE_H)) + PAD
  const worldW = maxX - minX, worldH = maxY - minY
  const scale = Math.min(MINIMAP_W / worldW, MINIMAP_H / worldH)
  // 视口在 minimap 上的投影
  const vx = (-pan.x / zoom - minX) * scale
  const vy = (-pan.y / zoom - minY) * scale
  const vw = (viewportW / zoom) * scale
  const vh = (viewportH / zoom) * scale

  const handleClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect()
    const mx = (e.clientX - rect.left) / scale + minX
    const my = (e.clientY - rect.top) / scale + minY
    // 让点击点居中
    onJump(-mx * zoom + viewportW / 2, -my * zoom + viewportH / 2)
  }

  return (
    <div
      className="absolute bottom-3 right-3 rounded-lg bg-black/50 border border backdrop-blur overflow-hidden cursor-crosshair"
      style={{ width: MINIMAP_W, height: MINIMAP_H, zIndex: 3 }}
      onClick={handleClick}
      title="点击跳转视口"
    >
      {nodes.map(n => {
        const t = NODE_TYPES.find(nt => nt.type === n.type)
        return (
          <div key={n.id}
            className="absolute rounded-sm"
            style={{
              left: (n.position.x - minX) * scale,
              top: (n.position.y - minY) * scale,
              width: NODE_W * scale,
              height: NODE_H * scale,
              background: (t?.color || '#888') + '80',
              border: `1px solid ${t?.color || '#888'}`,
            }}
          />
        )
      })}
      <div className="absolute border border-cyan-400/80 bg-cyan-400/10 pointer-events-none"
        style={{ left: vx, top: vy, width: vw, height: vh }} />
    </div>
  )
}
