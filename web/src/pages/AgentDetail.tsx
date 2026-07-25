import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { oneDark } from 'react-syntax-highlighter/dist/esm/styles/prism'
import { agentsApi, chatApi, Agent, ChatOut, ChatThread, Citation } from '@/api'

interface Msg {
  role: string
  content: string
  thinking?: string
  tool_calls?: any[]
  steps?: any[]
  streaming?: boolean
  /** 时序分块（仅 assistant 消息）：按执行顺序排列 */
  blocks?: Block[]
  /** RAG 引用来源 */
  citations?: Citation[]
}

type Block =
  | { type: 'thinking'; iter: number; text: string }
  | { type: 'tool'; iter: number; name: string; args: any; result: string; done: boolean }
  | { type: 'reply'; iter: number; text: string }

export default function AgentDetail() {
  const { name } = useParams()
  const nav = useNavigate()
  const [agent, setAgent] = useState<Agent | null>(null)
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [tid, setTid] = useState('')
  const [messages, setMessages] = useState<Msg[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [showThreads, setShowThreads] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!name) return
    agentsApi.get(name).then(setAgent).catch(()=>toast.error('Agent 不存在'))
    chatApi.threads(name).then(setThreads).catch(()=>{})
  }, [name])

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })
  }, [messages])

  const loadThread = async (t: ChatThread) => {
    setTid(t.thread_id)
    setShowThreads(false)
    try {
      const detail = await chatApi.threadDetail(t.thread_id)
      setMessages(detail.messages.map(m => ({ role: m.role, content: m.content })))
    } catch {}
  }

  const newThread = () => {
    setTid(''); setMessages([])
  }

  const exportChat = (format: 'json' | 'markdown' | 'txt') => {
    if (messages.length === 0) { toast.error('当前没有对话内容'); return }
    let content = ''
    let mime = 'text/plain'
    let ext = 'txt'
    const agentName = agent?.display_name || agent?.name || 'agent'
    if (format === 'json') {
      content = JSON.stringify({ agent: agent?.name, thread_id: tid, exported_at: new Date().toISOString(), messages }, null, 2)
      mime = 'application/json'; ext = 'json'
    } else if (format === 'markdown') {
      content = `# 与 ${agentName} 的对话\n\n导出时间: ${new Date().toLocaleString()}\n\n`
      messages.forEach(m => {
        const role = m.role === 'user' ? '🧑 用户' : '🤖 助手'
        content += `## ${role}\n\n${m.content}\n\n`
        if (m.thinking) content += `> **思考**: ${m.thinking}\n\n`
      })
      mime = 'text/markdown'; ext = 'md'
    } else {
      content = messages.map(m => `[${m.role === 'user' ? '用户' : '助手'}]\n${m.content}`).join('\n\n---\n\n')
      ext = 'txt'
    }
    const blob = new Blob([content], { type: mime })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `chat_${agentName}_${new Date().toISOString().slice(0,10)}.${ext}`
    a.click()
    URL.revokeObjectURL(url)
    toast.success('对话已导出')
  }

  const copyMsg = async (text: string) => {
    try { await navigator.clipboard.writeText(text); toast.success('已复制') } catch { toast.error('复制失败') }
  }

  const renameThread = async (t: ChatThread) => {
    const title = prompt('会话名称', t.title)
    if (title?.trim()) { await chatApi.rename(t.thread_id, title.trim()); refreshThreads() }
  }
  const delThread = async (t: ChatThread) => {
    if (confirm('删除该会话?')) { await chatApi.remove(t.thread_id); refreshThreads(); if (tid===t.thread_id) newThread() }
  }
  const refreshThreads = async () => {
    if (!name) return
    const ts = await chatApi.threads(name); setThreads(ts)
  }

  const send = async () => {
    if (!input.trim() || sending || !agent) return
    const text = input.trim(); setInput('')
    const useStream = agent.llm_config?.stream !== false
    setMessages(m => [...m, { role: 'user', content: text }])

    if (!useStream) {
      // 非流式(兜底)
      setSending(true)
      try {
        const r: ChatOut = await agentsApi.chat({ agent_name: agent.name, message: text, thread_id: tid || undefined })
        setTid(r.thread_id)
        setMessages(m => [...m, { role: 'assistant', content: r.reply, thinking: r.thinking, tool_calls: r.tool_calls, steps: r.steps, citations: r.citations }])
        refreshThreads()
      } catch (e: any) {
        setMessages(m => [...m, { role: 'assistant', content: `⚠️ ${e.message || '请求失败'}` }])
      } finally { setSending(false) }
      return
    }

    // 流式 SSE - 按 iter 维护 blocks
    setSending(true)
    const assistantIdx = messages.length + 1
    // blocks 按到达顺序排列；同 iter 的 thinking/tool/reply 连续出现
    const blocks: Block[] = []
    let finalCitations: Citation[] = []
    let finalThinking = ''
    // 辅助：获取/创建当前 thinking 块
    const ensureThinking = (iter: number) => {
      const last = blocks[blocks.length - 1]
      if (last && last.type === 'thinking' && last.iter === iter) return last
      const nb: Block = { type: 'thinking', iter, text: '' }
      blocks.push(nb)
      return nb
    }
    const ensureReply = (iter: number) => {
      const last = blocks[blocks.length - 1]
      if (last && last.type === 'reply' && last.iter === iter) return last
      const nb: Block = { type: 'reply', iter, text: '' }
      blocks.push(nb)
      return nb
    }
    const addTool = (iter: number, name: string, args: any, result: string) => {
      blocks.push({ type: 'tool', iter, name, args, result, done: true })
    }

    const flush = (extra?: { citations?: Citation[]; streaming?: boolean }) => {
      const reply = blocks.filter(b => b.type === 'reply').map(b => (b as any).text).join('')
      const thinking = blocks.filter(b => b.type === 'thinking').map(b => (b as any).text).join('\n')
      const tool_calls = blocks.filter(b => b.type === 'tool').map(b => ({
        tool: (b as any).name, args: (b as any).args, result: (b as any).result,
      }))
      setMessages(m => m.map((msg, i) => i === assistantIdx
        ? { ...msg, blocks: [...blocks], content: reply, thinking, tool_calls, citations: extra?.citations, streaming: extra?.streaming ?? true }
        : msg))
    }

    let finalTid = tid
    try {
      const resp = await agentsApi.chatStream({ agent_name: agent.name, message: text, thread_id: tid || undefined })
      if (!resp.ok || !resp.body) throw new Error(`HTTP ${resp.status}`)
      const reader = resp.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''
        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed.startsWith('data:')) continue
          const payload = trimmed.slice(5).trim()
          if (payload === '[DONE]') continue
          try {
            const ev = JSON.parse(payload)
            const iter = ev.iter ?? 1
            switch (ev.type) {
              case 'meta':
                if (ev.thread_id && !finalTid) { finalTid = ev.thread_id; setTid(ev.thread_id) }
                break
              case 'thinking':
                ensureThinking(iter).text += ev.delta || ''
                flush()
                break
              case 'delta':
                ensureReply(iter).text += ev.delta || ''
                flush()
                break
              case 'tool':
                addTool(iter, ev.tool, ev.args, ev.result || '')
                flush()
                break
              case 'error':
                blocks.push({ type: 'reply', iter: 999, text: `⚠️ ${ev.msg || '错误'}` })
                flush()
                break
              case 'done':
                if (Array.isArray(ev.citations)) finalCitations = ev.citations
                if (typeof ev.thinking === 'string') finalThinking = ev.thinking
                break
            }
          } catch {}
        }
      }
      const finalReply = blocks.filter(b => b.type === 'reply').map(b => (b as any).text).join('')
      setMessages(m => m.map((msg, i) => i === assistantIdx
        ? { ...msg, blocks: [...blocks], content: finalReply, thinking: finalThinking, citations: finalCitations, streaming: false }
        : msg))
      refreshThreads()
    } catch (e: any) {
      blocks.push({ type: 'reply', iter: 999, text: `⚠️ ${e.message || '请求失败'}` })
      setMessages(m => m.map((msg, i) => i === assistantIdx
        ? { ...msg, blocks: [...blocks], content: (e.message || '请求失败'), streaming: false }
        : msg))
    } finally {
      setSending(false)
    }
  }

  if (!agent) return <p className="text-tertiary">加载中...</p>
  if (agent.architecture === 'skill') {
    return <div className="text-center py-20">
      <p className="text-2xl mb-2">🤖</p>
      <p className="text-secondary">这是技能(Skill)类型 Agent，不能直接对话。</p>
      <button onClick={()=>nav('/agents')} className="mt-4 px-4 py-2 rounded bg-hover hover:bg-active">返回列表</button>
    </div>
  }

  return (
    <div className="flex gap-4 h-[calc(100vh-8rem)]">
      {/* 会话抽屉 */}
      {showThreads && (
        <div className="w-64 bg-card border border rounded-xl p-3 overflow-y-auto">
          <div className="flex justify-between items-center mb-3">
            <span className="text-sm font-medium">会话列表</span>
            <button onClick={newThread} className="text-xs text-brand hover:text-purple-200">+ 新对话</button>
          </div>
          {threads.map(t => (
            <div key={t.thread_id} onClick={()=>loadThread(t)}
              className={`p-2 rounded cursor-pointer mb-1 group ${tid===t.thread_id?'bg-active':'hover:bg-hover'}`}>
              <div className="text-sm truncate">{t.title || '新对话'}</div>
              <div className="text-xs text-placeholder">{new Date(t.updated_at).toLocaleString()}</div>
              <div className="flex gap-2 mt-1 opacity-0 group-hover:opacity-100">
                <button onClick={e=>{e.stopPropagation();renameThread(t)}} className="text-xs text-tertiary hover:text-primary">改名</button>
                <button onClick={e=>{e.stopPropagation();delThread(t)}} className="text-xs text-red-400">删除</button>
              </div>
            </div>
          ))}
          {threads.length===0 && <p className="text-placeholder text-xs text-center py-4">暂无会话</p>}
        </div>
      )}

      {/* 左侧 Agent 信息 */}
      <div className="w-72 bg-card border border rounded-xl p-4 overflow-y-auto">
        <h2 className="text-lg font-bold mb-1">{agent.display_name || agent.name}</h2>
        <p className="text-xs text-placeholder mb-3">{agent.name}</p>
        <p className="text-sm text-secondary mb-4">{agent.description || '无描述'}</p>
        <Info label="架构" value={agent.architecture} />
        {agent.framework && <Info label="框架" value={agent.framework} />}
        <Info label="最大步数" value={String(agent.max_iterations)} />
        <Info label="Temperature" value={String(agent.llm_config?.temperature ?? 1.0)} />
        <div className="flex gap-2 mt-2 text-xs">
          {agent.llm_config?.stream !== false && <span className="px-2 py-0.5 bg-cyan-500/20 text-cyan-300 rounded">流式</span>}
          {agent.llm_config?.thinking !== false && <span className="px-2 py-0.5 bg-purple-500/20 text-brand rounded">思考</span>}
        </div>
        <div className="mt-4">
          <div className="text-xs text-tertiary mb-1">绑定工具</div>
          <div className="flex flex-wrap gap-1">
            {agent.tools?.length ? agent.tools.map(t =>
              <span key={t} className="text-xs px-2 py-0.5 bg-card rounded">{t}</span>)
              : <span className="text-placeholder text-xs">无</span>}
          </div>
        </div>
        <div className="mt-3">
          <div className="text-xs text-tertiary mb-1">绑定知识库</div>
          <div className="text-sm text-secondary">{agent.rag_kb_ids?.length ? agent.rag_kb_ids.length + ' 个' : '无'}</div>
        </div>
        {agent.system_prompt && (
          <div className="mt-4">
            <div className="text-xs text-tertiary mb-1">System Prompt</div>
            <div className="text-xs text-tertiary bg-black/20 p-2 rounded whitespace-pre-wrap">{agent.system_prompt}</div>
          </div>
        )}
      </div>

      {/* 聊天区 */}
      <div className="flex-1 flex flex-col bg-card border border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border flex items-center justify-between">
          <span className="font-medium">对话</span>
          <details className="relative">
            <summary className="text-xs px-2 py-1 rounded bg-card hover:bg-hover cursor-pointer list-none select-none">
              ⋯ 操作
            </summary>
            <div className="absolute right-0 top-full mt-1 bg-card/95 border border rounded-lg p-1 z-20 shadow-md min-w-[140px]">
              <button onClick={() => { setShowThreads(!showThreads); const el = document.activeElement as HTMLElement; el?.blur() }}
                className="block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded">☰ 会话列表</button>
              <button onClick={newThread}
                className="block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded">＋ 新对话</button>
              <div className="h-px bg-hover my-1" />
              <div className="px-3 py-1 text-[10px] text-placeholder">导出</div>
              <button onClick={()=>exportChat('markdown')} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5">📝 Markdown</button>
              <button onClick={()=>exportChat('json')} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5">🔧 JSON</button>
              <button onClick={()=>exportChat('txt')} className="block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5">📄 纯文本</button>
            </div>
          </details>
        </div>
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map((m, i) => (
            <div key={i}>
              {m.role === 'user' ? (
                <div className="flex justify-end">
                  <div className="max-w-[70%] px-4 py-2 rounded-xl bg-gradient-to-r from-purple-600 to-cyan-600 text-primary">{m.content}</div>
                </div>
              ) : (
                <div className="flex justify-start group">
                  <div className="max-w-[85%] px-4 py-3 rounded-xl bg-hover text-primary relative">
                    <button onClick={()=>copyMsg(m.content)} title="复制"
                      className="absolute -top-2 -right-2 w-6 h-6 rounded-full bg-hover hover:bg-active text-xs opacity-0 group-hover:opacity-100 transition flex items-center justify-center">📋</button>
                    {/* 新时序分块渲染 */}
                    {m.blocks && m.blocks.length > 0 ? (
                      <div className="space-y-2">
                        {m.blocks.map((b, bi) => {
                          if (b.type === 'thinking') {
                            return <ThinkingBlock key={bi} iter={b.iter} text={b.text} streaming={!!m.streaming} isLast={bi === m.blocks!.length - 1} />
                          }
                          if (b.type === 'tool') {
                            return <ToolBlock key={bi} iter={b.iter} name={b.name} args={b.args} result={b.result} />
                          }
                          if (b.type === 'reply') {
                            return <div key={bi} className="markdown-body">
                              {b.text
                                ? <StreamingMarkdown content={b.text} streaming={!!m.streaming && bi === m.blocks!.length - 1} citations={m.citations} />
                                : (m.streaming && bi === m.blocks!.length - 1 ? null : '')}
                            </div>
                          }
                          return null
                        })}
                        {/* 流式等待指示 */}
                        {m.streaming && (() => {
                          const last = m.blocks![m.blocks!.length - 1]
                          if (last && last.type === 'tool') return <div className="text-placeholder text-xs">⌛ 分析结果中...</div>
                          return null
                        })()}
                      </div>
                    ) : (
                      // 旧格式/历史消息/非流式 fallback
                      <>
                        {m.thinking && (
                          <details className="mb-2 text-xs">
                            <summary className="cursor-pointer text-brand select-none">🧠 思考过程</summary>
                            <div className="mt-1 p-2 bg-purple-500/10 rounded text-purple-200/80 whitespace-pre-wrap font-mono">{m.thinking}</div>
                          </details>
                        )}
                        <div className="markdown-body">
                          {m.content ? (
                            <StreamingMarkdown content={m.content} streaming={!!m.streaming} citations={m.citations} />
                          ) : (m.streaming ? <span className="text-placeholder">思考中...</span> : '')}
                        </div>
                        {m.tool_calls && m.tool_calls.length>0 && (
                          <details className="mt-2 text-xs">
                            <summary className="cursor-pointer text-cyan-300">🔧 调用了 {m.tool_calls.length} 个工具</summary>
                            <div className="mt-1 space-y-1">
                              {m.tool_calls.map((tc, ti) => (
                                <div key={ti} className="bg-black/30 rounded p-2">
                                  <div className="font-mono text-cyan-300">{tc.tool}({JSON.stringify(tc.args)})</div>
                                  <div className="text-secondary mt-1 whitespace-pre-wrap">{String(tc.result).slice(0,500)}</div>
                                </div>
                              ))}
                            </div>
                          </details>
                        )}
                      </>
                    )}
                    {/* 引用来源列表 */}
                    {!m.streaming && m.citations && m.citations.length > 0 && (
                      <CitationsList citations={m.citations} />
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
          {messages.length===0 && <div className="text-center text-placeholder py-20">在下方输入消息开始对话</div>}
        </div>
        <div className="p-3 border-t border flex gap-2">
          <input value={input} onChange={e=>setInput(e.target.value)}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}
            placeholder="输入消息 (Enter 发送, Shift+Enter 换行)"
            className="flex-1 px-3 py-2 rounded-lg bg-hover border border focus:outline-none" />
          <button onClick={send} disabled={sending || !input.trim()}
            className="px-4 py-2 rounded-lg bg-gradient-to-r from-brand to-brand-700 disabled:opacity-50">
            {sending?'...':'发送'}
          </button>
        </div>
      </div>
    </div>
  )
}

function Info({ label, value }: { label: string; value: string }) {
  return <div className="flex justify-between text-sm py-1">
    <span className="text-tertiary">{label}</span><span>{value}</span>
  </div>
}

// ====== 思考块：流式时默认展开，结束后默认折叠 ======
function ThinkingBlock({ iter, text, streaming, isLast }: { iter: number; text: string; streaming: boolean; isLast: boolean }) {
  // 流式时最后一个 thinking 块展开，否则折叠
  const [open, setOpen] = useState(streaming && isLast)
  useEffect(() => { if (streaming && isLast) setOpen(true) }, [streaming, isLast])
  if (!text) return null
  return (
    <details open={open} className="text-xs" onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer text-brand/80 select-none list-none flex items-center gap-1.5 py-0.5 hover:text-purple-200 transition">
        <span className="text-[10px] opacity-60">{open ? '▼' : '▶'}</span>
        <span>💭 思考 #{iter}</span>
        {!open && <span className="text-placeholder truncate ml-2 max-w-[300px]">{text.slice(0, 60)}{text.length>60?'…':''}</span>}
        {streaming && isLast && <span className="w-1.5 h-3 bg-purple-300/70 animate-pulse ml-1" />}
      </summary>
      <div className="mt-1 p-2 bg-purple-500/10 border border-purple-500/20 rounded text-purple-100/80 whitespace-pre-wrap font-mono text-[11px] leading-relaxed">{text}</div>
    </details>
  )
}

// ====== 工具调用块：始终折叠，点击展开查看参数和结果 ======
function ToolBlock({ iter, name, args, result }: { iter: number; name: string; args: any; result: string }) {
  const [open, setOpen] = useState(false)
  const argsStr = JSON.stringify(args ?? {}, null, 2)
  const resultShort = result.length > 120 ? result.slice(0, 120) + '…' : result
  return (
    <details open={open} className="text-xs" onToggle={e => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer select-none list-none flex items-center gap-1.5 py-1 px-2 bg-cyan-500/10 hover:bg-cyan-500/15 rounded border border-cyan-500/20 transition">
        <span className="text-[10px]">{open ? '▼' : '▶'}</span>
        <span className="text-cyan-300">🔧 第{iter}轮 · {name}</span>
        <span className="text-cyan-200/50 font-mono truncate max-w-[280px]">({Object.keys(args ?? {}).slice(0,3).map(k=>`${k}=${String(args[k]).slice(0,20)}`).join(', ')}{Object.keys(args ?? {}).length>3?'…':''})</span>
      </summary>
      <div className="mt-1 space-y-1 p-2 bg-black/40 rounded border border">
        <div>
          <div className="text-placeholder text-[10px] mb-0.5">参数</div>
          <pre className="text-cyan-200 font-mono text-[11px] whitespace-pre-wrap break-words bg-black/30 p-1.5 rounded">{argsStr}</pre>
        </div>
        <div>
          <div className="text-placeholder text-[10px] mb-0.5">返回</div>
          <pre className="text-green-200/90 font-mono text-[11px] whitespace-pre-wrap break-words bg-black/30 p-1.5 rounded max-h-60 overflow-y-auto">{result}</pre>
        </div>
      </div>
    </details>
  )
}

/**
 * 流式 Markdown 渲染器：
 * - 流式阶段（streaming=true）：节流 80ms 更新；未闭合代码块用轻量 <pre> 渲染避免每 token 重算高亮；闭合的代码块正常高亮。
 * - 流结束后：完整高亮渲染。
 * - 支持 citations：把正文中的 [n] 角标替换为可点击的 sup 标签（hover 显示文档名），仅在非 code 区域替换。
 */
function StreamingMarkdown({ content, streaming, citations }: { content: string; streaming: boolean; citations?: Citation[] }) {
  const [throttled, setThrottled] = useState(content)
  const lastFlush = useRef(0)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  useEffect(() => {
    if (!streaming) {
      setThrottled(content)
      if (timer.current) { clearTimeout(timer.current); timer.current = null }
      return
    }
    const now = Date.now()
    const elapsed = now - lastFlush.current
    if (elapsed >= 80) {
      lastFlush.current = now
      setThrottled(content)
    } else if (!timer.current) {
      timer.current = setTimeout(() => {
        lastFlush.current = Date.now()
        timer.current = null
        setThrottled(content)
      }, 80 - elapsed)
    }
    return () => {
      if (timer.current) { clearTimeout(timer.current); timer.current = null }
    }
  }, [content, streaming])

  // 对流式中尚未闭合的最后一个代码块，交给 react-markdown 但 code 组件检测并降级
  const renderContent = streaming ? throttled : content

  // 计算未闭合代码块标记
  const processed = useMemo(() => {
    if (!streaming) return renderContent
    const fences = renderContent.match(/```/g)
    if (!fences || fences.length % 2 === 0) return renderContent
    return renderContent + '\n```'
  }, [renderContent, streaming])

  // 构造 citations 索引
  const citeMap = useMemo(() => {
    const m = new Map<number, Citation>()
    ;(citations || []).forEach(c => m.set(c.idx, c))
    return m
  }, [citations])

  // 文本节点渲染：替换 [n] 为角标
  const renderText = (text: string, keyPrefix = '') => {
    if (!citeMap.size) return text
    const parts: (string | JSX.Element)[] = []
    const re = /\[(\d+)\]/g
    let last = 0, m: RegExpExecArray | null
    let k = 0
    while ((m = re.exec(text)) !== null) {
      const idx = parseInt(m[1], 10)
      const cite = citeMap.get(idx)
      if (m.index > last) parts.push(text.slice(last, m.index))
      if (cite) {
        parts.push(
          <sup key={`${keyPrefix}c${k++}`}
            title={`${cite.document_name || '未知来源'}${cite.content ? ' — ' + cite.content.slice(0, 120) + (cite.content.length > 120 ? '...' : '') : ''}`}
            className="mx-0.5 px-1 rounded bg-cyan-500/20 text-cyan-200 text-[0.7em] font-semibold cursor-help align-baseline hover:bg-cyan-500/30">
            [{idx}]
          </sup>
        )
      } else {
        parts.push(m[0])
      }
      last = m.index + m[0].length
    }
    if (last < text.length) parts.push(text.slice(last))
    return parts
  }

  // 递归处理 children，把字符串里的 [n] 替换为角标；遇到 code/pre/inline code 直接原样
  const renderChildren = (children: any, inCode = false, keyPrefix = ''): any => {
    if (children == null) return children
    if (typeof children === 'string') return inCode ? children : renderText(children, keyPrefix)
    if (Array.isArray(children)) return children.map((c, i) => renderChildren(c, inCode, `${keyPrefix}a${i}_`))
    return children
  }

  // 通用包装：渲染 props.children 前处理文本
  const wrap = (Tag: any, cls: string) => ({ node, children, ...p }: any) => {
    const inCode = Tag === 'code' || Tag === 'pre'
    return <Tag className={cls} {...p}>{renderChildren(children, inCode)}</Tag>
  }

  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={{
      p: wrap('p', 'my-1.5 leading-relaxed'),
      pre: ({node, ...p}) => <pre className="my-2 p-3 bg-black/40 rounded-lg overflow-x-auto text-xs border border" {...p} />,
      code({node, className, children, ...p}: any) {
        const match = /language-(\w+)/.exec(className || '')
        const isInline = !match
        const codeText = String(children).replace(/\n$/, '')
        if (isInline) {
          return <code className="px-1.5 py-0.5 mx-0.5 rounded bg-cyan-500/20 text-cyan-200 text-[0.85em] font-mono" {...p}>{children}</code>
        }
        // 流式中未闭合的代码块：纯文本渲染
        const isLastUnclosed = streaming && codeText.length > 0 && (() => {
          const tail = renderContent.slice(-codeText.length - 6)
          return tail.includes(codeText.slice(-Math.min(40, codeText.length)))
        })()
        if (isLastUnclosed) {
          return (
            <div className="relative group my-2">
              <div className="absolute top-2 left-3 z-10 text-[10px] text-placeholder font-mono pointer-events-none">{match[1]} <span className="text-placeholder">(streaming)</span></div>
              <pre className="my-0 p-3 pt-7 bg-black/40 rounded-lg overflow-x-auto text-xs border border text-primary font-mono whitespace-pre">{codeText}</pre>
            </div>
          )
        }
        return (
          <div className="relative group my-2">
            <button
              onClick={() => { navigator.clipboard.writeText(codeText).then(() => toast.success('代码已复制'), () => toast.error('复制失败')) }}
              className="absolute top-2 right-2 z-10 px-2 py-1 rounded text-[11px] bg-hover hover:bg-active text-secondary hover:text-primary opacity-0 group-hover:opacity-100 transition border border"
              title="复制代码"
            >📋 复制</button>
            <div className="absolute top-2 left-3 z-10 text-[10px] text-placeholder font-mono pointer-events-none">{match[1]}</div>
            <SyntaxHighlighter
              style={oneDark} language={match[1]} PreTag="div"
              customStyle={{margin:0,borderRadius:'0.5rem',fontSize:'0.8em',background:'rgba(0,0,0,0.4)',paddingTop:'1.8rem'}}
            >{codeText}</SyntaxHighlighter>
          </div>
        )
      },
      ul: wrap('ul', 'my-2 pl-5 list-disc space-y-1 marker:text-brand/60'),
      ol: wrap('ol', 'my-2 pl-5 list-decimal space-y-1 marker:text-brand/60'),
      li: wrap('li', 'leading-relaxed pl-0.5'),
      h1: wrap('h1', 'text-lg font-bold my-2'),
      h2: wrap('h2', 'text-base font-bold my-2'),
      h3: wrap('h3', 'text-sm font-semibold my-1.5'),
      h4: wrap('h4', 'text-sm font-semibold my-1 text-primary'),
      hr: () => <hr className="my-3 border" />,
      strong: wrap('strong', 'font-semibold text-primary'),
      em: wrap('em', 'italic text-primary'),
      blockquote: wrap('blockquote', 'border-l-2 border-cyan-400/50 pl-3 my-2 text-secondary italic'),
      a: ({node, ...p}) => <a className="text-cyan-300 underline hover:text-cyan-200" target="_blank" rel="noreferrer" {...p} />,
      table: ({node, ...p}) => (
        <div className="my-2 overflow-x-auto rounded-lg border border">
          <table className="border-collapse text-sm w-full" {...p} />
        </div>
      ),
      thead: wrap('thead', 'bg-card'),
      th: wrap('th', 'border-b border px-3 py-1.5 text-left font-semibold text-primary'),
      td: wrap('td', 'border-b border px-3 py-1.5'),
    }}>{processed}</ReactMarkdown>
  )
}

/** 引用来源列表 - 消息底部展示 */
function CitationsList({ citations }: { citations: Citation[] }) {
  const [open, setOpen] = useState(false)
  const [active, setActive] = useState<Citation | null>(null)
  return (
    <div className="mt-3 pt-2 border-t border">
      <button onClick={() => setOpen(v => !v)}
        className="flex items-center gap-1.5 text-xs text-cyan-300/80 hover:text-cyan-200 transition">
        <span>{open ? '▼' : '▶'}</span>
        📚 参考来源 ({citations.length})
      </button>
      {open && (
        <div className="mt-2 space-y-1.5">
          {citations.map(c => (
            <div key={c.idx} className="p-2 rounded bg-black/20 border border text-xs">
              <div className="flex items-start gap-2">
                <span className="shrink-0 px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-200 font-semibold">[{c.idx}]</span>
                <div className="flex-1 min-w-0">
                  <div className="text-primary font-medium truncate">{c.document_name || '未知来源'}</div>
                  {c.content && (
                    <>
                      <div className="text-tertiary mt-0.5 line-clamp-2">{c.content.slice(0, 240)}{c.content.length > 240 ? '...' : ''}</div>
                      <button onClick={() => setActive(active?.idx === c.idx ? null : c)}
                        className="text-[10px] text-cyan-300/70 hover:text-cyan-200 mt-0.5">
                        {active?.idx === c.idx ? '收起' : '展开原文'}
                      </button>
                      {active?.idx === c.idx && (
                        <pre className="mt-1 p-2 bg-black/40 rounded text-[11px] text-secondary whitespace-pre-wrap max-h-48 overflow-auto">{c.content}</pre>
                      )}
                    </>
                  )}
                  {typeof c.score === 'number' && c.score > 0 && (
                    <div className="text-placeholder mt-0.5">相关度: {(c.score * 100).toFixed(1)}%</div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
