import { useEffect, useRef, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { ragApi, KB, DocItem, Chunk, QueryHit } from '@/api'
import { useMetaStore } from '@/store/meta'

export default function KBDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const kbId = Number(id)
  const { loaders, splitters, config: cfg } = useMetaStore()
  const [kb, setKb] = useState<KB | null>(null)
  const [docs, setDocs] = useState<DocItem[]>([])
  const [tab, setTab] = useState<'docs'|'query'>('docs')
  const [showUpload, setShowUpload] = useState(false)
  const [viewingDoc, setViewingDoc] = useState<DocItem | null>(null)  // 查看 chunks 模式
  const pollTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  const loadKb = async () => {
    try { setKb(await ragApi.getKb(kbId)) } catch { nav('/rag') }
  }
  const stopPoll = () => {
    if (pollTimer.current) { clearInterval(pollTimer.current); pollTimer.current = null }
  }
  const loadDocs = async () => {
    const ds = await ragApi.listDocs(kbId)
    setDocs(ds)
    if (ds.some(d => d.status === 'pending' || d.status === 'processing')) {
      if (!pollTimer.current) {
        pollTimer.current = setInterval(loadDocs, 2000)
        setTimeout(stopPoll, 60000)
      }
    } else {
      stopPoll()
    }
  }
  useEffect(() => { loadKb(); loadDocs(); return stopPoll }, [kbId])

  const delDoc = async (d: DocItem) => {
    if (!confirm(`删除文档 "${d.display_name}" 及其所有 chunks?`)) return
    await ragApi.removeDoc(d.id); toast.success('已删除'); loadDocs(); loadKb()
  }
  const renameDoc = async (d: DocItem) => {
    const name = prompt('显示名称', d.display_name)
    if (name?.trim()) { await ragApi.updateDoc(d.id, { display_name: name.trim() }); loadDocs() }
  }
  const delKb = async () => {
    if (!confirm(`删除知识库 "${kb?.name}"?\n所有文档和向量将被永久删除!`)) return
    await ragApi.removeKb(kbId); toast.success('已删除'); nav('/rag')
  }

  if (!kb) return <p className="text-tertiary">加载中...</p>

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <button onClick={()=>nav('/rag')} className="text-tertiary hover:text-primary text-sm mb-1">← 返回</button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            {kb.icon_url ? <img src={kb.icon_url} className="w-8 h-8 rounded" onError={(e)=>(e.currentTarget.style.display='none')} /> : <span>📚</span>}
            {kb.name}
          </h1>
          <p className="text-tertiary text-sm mt-1">{kb.description || '无描述'}</p>
        </div>
        <div className="text-right">
          <div className="text-sm">📄 文档 <b>{kb.document_count}</b> · 🧩 切块 <b>{kb.total_chunks}</b></div>
          <button onClick={delKb} className="mt-2 text-xs text-red-400 hover:bg-red-500/20 px-3 py-1 rounded">删除知识库</button>
        </div>
      </div>

      {/* 查看某文档 chunks 模式 */}
      {viewingDoc ? (
        <ChunksView doc={viewingDoc} onBack={()=>setViewingDoc(null)} />
      ) : (
        <>
          <div className="flex gap-1 border-b border">
            <button onClick={()=>setTab('docs')}
              className={`px-4 py-2 text-sm ${tab==='docs'?'border-b-2 border-emerald-400 text-primary':'text-tertiary hover:text-primary'}`}>
              📄 文档
            </button>
            <button onClick={()=>setTab('query')}
              className={`px-4 py-2 text-sm ${tab==='query'?'border-b-2 border-emerald-400 text-primary':'text-tertiary hover:text-primary'}`}>
              🔍 检索测试
            </button>
            <div className="ml-auto">
              <button onClick={()=>setShowUpload(!showUpload)}
                className="px-4 py-2 text-sm rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-primary font-medium hover:opacity-90">
                ➕ 上传文档
              </button>
            </div>
          </div>

          {showUpload && <UploadPanel kb={kb} onUploaded={()=>{setShowUpload(false); loadDocs(); loadKb()}} />}

          {tab==='docs' && (
            <div className="space-y-2">
              {docs.map(d => (
                <DocCard key={d.id} doc={d} loaders={loaders} splitters={splitters}
                  onRename={()=>renameDoc(d)} onDelete={()=>delDoc(d)}
                  onViewChunks={()=>setViewingDoc(d)} />
              ))}
              {docs.length===0 && !showUpload && <p className="text-center text-placeholder py-10">还没有文档，点右上角「上传文档」开始</p>}
            </div>
          )}
          {tab==='query' && <QueryPanel kbId={kbId} />}
        </>
      )}
    </div>
  )
}

function DocCard({ doc, loaders, splitters, onRename, onDelete, onViewChunks }:{
  doc: DocItem; loaders: {key:string;label:string}[]; splitters: {key:string;label:string}[]
  onRename:()=>void; onDelete:()=>void; onViewChunks:()=>void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const h = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false) }
    if (menuOpen) document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [menuOpen])

  const statusCls: Record<string,string> = {
    pending:'bg-gray-500/20 text-gray-300', processing:'bg-blue-500/20 text-blue-300',
    indexed:'bg-emerald-500/20 text-emerald-300', failed:'bg-red-500/20 text-red-300' }
  const statusLabel: Record<string,string> = { pending:'排队中', processing:'处理中...', indexed:'已索引', failed:'失败' }

  const m = doc.metadata_ || {}
  const loaderLabel = loaders.find(l=>l.key===m.loader)?.label || m.loader || ''
  const splitterLabel = splitters.find(s=>s.key===m.splitter_type)?.label || m.splitter_type || ''

  return (
    <div className="bg-card border border rounded-xl p-4 flex items-center gap-4">
      <div className="text-3xl">📄</div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium truncate">{doc.display_name}</span>
          <span className={`text-xs px-2 py-0.5 rounded ${statusCls[doc.status]||'bg-hover'}`} title={m.error||''}>
            {statusLabel[doc.status]||doc.status}
          </span>
        </div>
        <div className="text-xs text-tertiary mt-1">
          🧩 {doc.chunk_count} chunks · {(doc.file_size/1024).toFixed(1)} KB
          {loaderLabel && <span className="ml-2 px-1.5 py-0.5 bg-card rounded">{loaderLabel}</span>}
          {splitterLabel && <span className="ml-1 px-1.5 py-0.5 bg-card rounded">{splitterLabel}</span>}
          {m.chunk_size && <span className="ml-1 px-1.5 py-0.5 bg-card rounded">{m.chunk_size}/{m.chunk_overlap||0}</span>}
        </div>
      </div>
      <button onClick={onViewChunks}
        className="px-3 py-1.5 text-xs rounded bg-purple-500/20 text-brand hover:bg-purple-500/30"
        disabled={doc.status!=='indexed'} title={doc.status!=='indexed'?'索引完成后可查看':''}>
        Chunks
      </button>
      <div ref={menuRef} className="relative">
        <button onClick={()=>setMenuOpen(!menuOpen)}
          className="w-8 h-8 rounded flex items-center justify-center text-tertiary hover:text-primary hover:bg-hover">
          <span className="text-xl leading-none">⋯</span>
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-9 bg-card border border rounded-lg shadow-md py-1 min-w-[100px] z-10">
            <button onClick={()=>{setMenuOpen(false); onRename()}} className="w-full px-3 py-1.5 text-left text-sm hover:bg-hover">✏️ 改名</button>
            <button onClick={()=>{setMenuOpen(false); onDelete()}} className="w-full px-3 py-1.5 text-left text-sm text-red-400 hover:bg-red-500/20">🗑 删除</button>
          </div>
        )}
      </div>
    </div>
  )
}

function UploadPanel({ kb, onUploaded }:{ kb: KB; onUploaded:()=>void }) {
  const { loaders, splitters } = useMetaStore()
  const [file, setFile] = useState<File|null>(null)
  const [loader, setLoader] = useState(kb.loader||'auto')
  const [splitter, setSplitter] = useState(kb.splitter_type||'sentence')
  const [size, setSize] = useState(kb.chunk_size||500)
  const [overlap, setOverlap] = useState(kb.chunk_overlap||50)
  const [regex, setRegex] = useState('')
  const [uploading, setUploading] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const pick = (f: File) => {
    if (f.size > (useMetaStore.getState().config.max_upload_mb||50)*1024*1024) {
      toast.error(`文件超过 ${useMetaStore.getState().config.max_upload_mb}MB`); return
    }
    setFile(f)
  }
  const upload = async () => {
    if (!file) return
    setUploading(true)
    try {
      await ragApi.uploadDoc(kb.id, file, { loader, splitter_type: splitter, chunk_size: size, chunk_overlap: overlap, splitter_regex: regex||undefined })
      toast.success('已上传，后台索引中...')
      onUploaded()
      setFile(null); if (fileRef.current) fileRef.current.value=''
    } finally { setUploading(false) }
  }

  return <div className="bg-card border border rounded-xl p-4 space-y-3">
    <h3 className="font-semibold">📤 上传文档</h3>
    <div className="grid md:grid-cols-2 gap-3">
      <div className="md:col-span-2">
        <input ref={fileRef} type="file" onChange={e=>pick(e.target.files![0])}
          className="text-sm text-secondary file:mr-3 file:px-3 file:py-1.5 file:rounded file:border-0 file:bg-hover file:text-primary hover:file:bg-active" />
        {file && <div className="text-xs text-tertiary mt-1">{file.name} ({(file.size/1024).toFixed(1)} KB)</div>}
      </div>
      <Select label="加载器" value={loader} onChange={setLoader}
        options={loaders.map(l=>({value:l.key,label:l.label}))} />
      <Select label="分块方式" value={splitter} onChange={setSplitter}
        options={splitters.map(s=>({value:s.key,label:s.label}))} />
      {splitter==='regex' && (
        <div className="md:col-span-2">
          <label className="block text-xs text-tertiary mb-1">正则分隔符</label>
          <input value={regex} onChange={e=>setRegex(e.target.value)} placeholder="例: [,.;，。；]"
            className="w-full px-3 py-2 rounded bg-hover border border" />
        </div>
      )}
      <div>
        <label className="block text-xs text-tertiary mb-1">块大小</label>
        <input type="number" value={size} onChange={e=>setSize(Number(e.target.value))}
          className="w-full px-3 py-2 rounded bg-hover border border" />
      </div>
      <div>
        <label className="block text-xs text-tertiary mb-1">重叠大小</label>
        <input type="number" value={overlap} onChange={e=>setOverlap(Number(e.target.value))}
          className="w-full px-3 py-2 rounded bg-hover border border" />
      </div>
    </div>
    <button onClick={upload} disabled={!file||uploading}
      className="px-4 py-2 rounded bg-gradient-to-r from-emerald-500 to-teal-500 disabled:opacity-50">
      {uploading?'上传中...':'上传'}
    </button>
  </div>
}

function ChunksView({ doc, onBack }:{ doc: DocItem; onBack:()=>void }) {
  const [chunks, setChunks] = useState<Chunk[]>([])
  const [showAdd, setShowAdd] = useState(false)
  const [newContent, setNewContent] = useState('')
  const [adding, setAdding] = useState(false)
  useEffect(() => { ragApi.listChunks(doc.id).then(setChunks) }, [doc.id])

  const saveChunk = async (c: Chunk, content: string) => {
    await ragApi.updateChunk(c.id, content); toast.success('已保存(会重新 embed)')
    setChunks(chunks.map(x=>x.id===c.id?{...x, content}:x))
  }
  const delChunk = async (c: Chunk) => {
    if (!confirm(`删除 chunk #${c.chunk_index}?`)) return
    await ragApi.removeChunk(c.id); setChunks(chunks.filter(x=>x.id!==c.id))
  }
  const addChunk = async () => {
    if (!newContent.trim()) return
    setAdding(true)
    try {
      const c = await ragApi.createChunk(doc.id, newContent.trim())
      setChunks([...chunks, c]); setNewContent(''); setShowAdd(false)
    } finally { setAdding(false) }
  }

  return <div className="space-y-3">
    <div className="flex items-center justify-between">
      <button onClick={onBack} className="text-tertiary hover:text-primary text-sm">← 返回文档列表</button>
      <button onClick={()=>setShowAdd(true)}
        className="px-3 py-1.5 text-sm rounded bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30">+ 新增 chunk</button>
    </div>
    <h2 className="text-xl font-bold">🧩 {doc.display_name} 的 Chunks ({chunks.length})</h2>
    {chunks.map(c => <ChunkCard key={c.id} c={c} onSave={(v)=>saveChunk(c,v)} onDelete={()=>delChunk(c)} />)}

    {showAdd && (
      <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" onClick={()=>setShowAdd(false)}>
        <div className="bg-card border border rounded-2xl w-full max-w-xl p-6" onClick={e=>e.stopPropagation()}>
          <h3 className="text-lg font-bold mb-3">新增 chunk</h3>
          <textarea value={newContent} onChange={e=>setNewContent(e.target.value)} rows={6} autoFocus
            placeholder="输入 chunk 内容..." className="w-full px-3 py-2 rounded bg-hover border border resize-none" />
          <div className="flex justify-end gap-3 mt-4">
            <button onClick={()=>setShowAdd(false)} className="px-4 py-2 rounded bg-hover hover:bg-active">取消</button>
            <button onClick={addChunk} disabled={!newContent.trim()||adding}
              className="px-4 py-2 rounded bg-gradient-to-r from-emerald-500 to-teal-500 disabled:opacity-50">
              {adding?'添加中...':'添加'}
            </button>
          </div>
        </div>
      </div>
    )}
  </div>
}

function ChunkCard({ c, onSave, onDelete }:{ c: Chunk; onSave:(v:string)=>void; onDelete:()=>void }) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(c.content)
  return <div className="bg-card border border rounded-xl p-3">
    <div className="flex items-center justify-between mb-2">
      <span className="text-xs text-tertiary">
        #{c.chunk_index} · {c.metadata_?.type==='image'?'🖼️ 图片':'📝 文本'}{c.metadata_?.page?` · p.${c.metadata_.page}`:''}
      </span>
      <div className="flex gap-2">
        {editing
          ? <><button onClick={()=>{onSave(val); setEditing(false)}} className="text-xs text-emerald-400 hover:underline">保存</button>
             <button onClick={()=>{setVal(c.content); setEditing(false)}} className="text-xs text-tertiary hover:underline">取消</button></>
          : <><button onClick={()=>setEditing(true)} className="text-xs text-blue-400 hover:underline">编辑</button>
             <button onClick={onDelete} className="text-xs text-red-400 hover:underline">删除</button></>}
      </div>
    </div>
    {editing
      ? <textarea value={val} onChange={e=>setVal(e.target.value)} rows={3}
          className="w-full px-2 py-1 rounded bg-hover border border text-sm" />
      : <div className="text-sm whitespace-pre-wrap">{c.metadata_?.type==='image'?'[IMAGE 第'+(c.metadata_.page||'?')+'页]':c.content}</div>}
  </div>
}

function QueryPanel({ kbId }:{ kbId:number }) {
  const [mode, setMode] = useState<'single'|'batch'>('single')
  return <div className="space-y-3">
    <div className="flex gap-1">
      <button onClick={()=>setMode('single')} className={`px-3 py-1 text-sm rounded ${mode==='single'?'bg-purple-500/30 text-primary':'bg-card text-tertiary hover:text-primary'}`}>单条检索</button>
      <button onClick={()=>setMode('batch')} className={`px-3 py-1 text-sm rounded ${mode==='batch'?'bg-purple-500/30 text-primary':'bg-card text-tertiary hover:text-primary'}`}>批量检索</button>
    </div>
    {mode==='single' ? <SingleQuery kbId={kbId} /> : <BatchQuery kbId={kbId} />}
  </div>
}

function SingleQuery({ kbId }:{ kbId:number }) {
  const [q, setQ] = useState('')
  const [topK, setTopK] = useState(5)
  const [hits, setHits] = useState<QueryHit[]>([])
  const [loading, setLoading] = useState(false)
  const search = async () => {
    if (!q.trim()) return
    setLoading(true)
    try { setHits(await ragApi.query({ kb_id: kbId, query: q, top_k: topK, rerank: true, return_content: true })) }
    finally { setLoading(false) }
  }
  return <div className="space-y-3">
    <div className="bg-card border border rounded-xl p-4 flex gap-2">
      <input value={q} onChange={e=>setQ(e.target.value)} onKeyDown={e=>e.key==='Enter'&&search()}
        placeholder="输入问题检索..." className="flex-1 px-3 py-2 rounded bg-hover border border" />
      <input type="number" min={1} max={20} value={topK} onChange={e=>setTopK(Number(e.target.value))}
        className="w-20 px-3 py-2 rounded bg-hover border border" title="top_k" />
      <button onClick={search} disabled={loading}
        className="px-4 py-2 rounded bg-gradient-to-r from-brand to-brand-700 disabled:opacity-50">
        {loading?'检索中':'检索'}
      </button>
    </div>
    <div className="space-y-2">
      {hits.map((h,i)=>(
        <div key={h.chunk_id} className="bg-card border border rounded-xl p-3">
          <div className="flex justify-between items-center mb-1">
            <span className="text-xs text-tertiary">#{i+1} · {h.document_name||'?'} · chunk #{h.chunk_index}</span>
            <span className="text-xs text-brand">score: {h.score?.toFixed(3)}</span>
          </div>
          <p className="text-sm whitespace-pre-wrap">{h.content}</p>
        </div>
      ))}
      {hits.length===0 && !loading && <p className="text-center text-placeholder py-8">输入问题开始检索</p>}
    </div>
  </div>
}

function BatchQuery({ kbId }:{ kbId:number }) {
  const [text, setText] = useState('')
  const [topK, setTopK] = useState(3)
  const [loading, setLoading] = useState(false)
  const [results, setResults] = useState<{ query: string; hits: QueryHit[] }[]>([])
  const [elapsed, setElapsed] = useState(0)
  const run = async () => {
    const queries = text.split(/\n+/).map(s=>s.trim()).filter(Boolean)
    if (queries.length === 0) { toast.error('请输入至少一个问题'); return }
    if (queries.length > 20) { toast.error('单次最多 20 个 query'); return }
    setLoading(true); const t0 = Date.now()
    try {
      const res = await ragApi.batchQuery(queries.map(q => ({ kb_id: kbId, query: q, top_k: topK, rerank: true, return_content: true })))
      setResults(queries.map((q, i) => ({ query: q, hits: res[i] || [] })))
      setElapsed(Date.now() - t0)
    } catch (e:any) {
      toast.error(e?.message || '批量检索失败')
    } finally { setLoading(false) }
  }
  const exportJSON = () => {
    const blob = new Blob([JSON.stringify(results, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob); const a = document.createElement('a')
    a.href = url; a.download = `batch-query-${Date.now()}.json`; a.click(); URL.revokeObjectURL(url)
  }
  return <div className="space-y-3">
    <div className="bg-card border border rounded-xl p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <label className="text-xs text-tertiary">每行一个 query（最多 20 个）：</label>
        <input type="number" min={1} max={10} value={topK} onChange={e=>setTopK(Number(e.target.value))}
          className="w-20 px-2 py-1 text-sm rounded bg-hover border border" title="每个 query top_k" />
        <div className="ml-auto flex gap-2">
          {results.length>0 && <button onClick={exportJSON} className="px-3 py-1.5 text-sm rounded bg-hover hover:bg-active">📥 导出 JSON</button>}
          <button onClick={run} disabled={loading}
            className="px-4 py-1.5 text-sm rounded bg-gradient-to-r from-brand to-brand-700 disabled:opacity-50">
            {loading?'批量检索中...':'🚀 批量检索'}
          </button>
        </div>
      </div>
      <textarea value={text} onChange={e=>setText(e.target.value)} rows={6}
        placeholder={'问题1\n问题2\n问题3'}
        className="w-full px-3 py-2 rounded bg-hover border border text-sm font-mono resize-y" />
      {elapsed>0 && <div className="text-xs text-placeholder">耗时 {elapsed}ms · 共 {results.length} 个 query</div>}
    </div>
    <div className="space-y-3">
      {results.map((r,i)=>(
        <div key={i} className="bg-card border border rounded-xl p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="text-sm font-medium">
              <span className="text-brand mr-2">Q{i+1}.</span>{r.query}
            </div>
            <span className="text-xs text-placeholder">{r.hits.length} hits</span>
          </div>
          <div className="space-y-1.5">
            {r.hits.slice(0, topK).map((h,j)=>(
              <div key={h.chunk_id} className="bg-black/20 rounded p-2 text-xs">
                <div className="flex justify-between text-tertiary mb-1">
                  <span>#{j+1} · {h.document_name||'?'} · chunk #{h.chunk_index}</span>
                  <span className="text-brand">{h.score?.toFixed(3)}</span>
                </div>
                <div className="text-primary line-clamp-3 whitespace-pre-wrap">{h.content}</div>
              </div>
            ))}
            {r.hits.length===0 && <p className="text-placeholder text-xs">无结果</p>}
          </div>
        </div>
      ))}
    </div>
  </div>
}

function Select({ label, value, onChange, options }:{
  label:string; value:string; onChange:(v:string)=>void; options:{value:string;label:string}[]
}) {
  return <div>
    <label className="block text-xs text-tertiary mb-1">{label}</label>
    <select value={value} onChange={e=>onChange(e.target.value)}
      className="w-full px-3 py-2 rounded bg-hover border border">
      {options.map(o=><option key={o.value} value={o.value}>{o.label}</option>)}
    </select>
  </div>
}
