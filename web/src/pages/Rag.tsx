import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { ragApi, KB } from '@/api'
import { useMetaStore } from '@/store/meta'

export default function Rag() {
  const nav = useNavigate()
  const { loaders, splitters } = useMetaStore()
  const [kbs, setKbs] = useState<KB[]>([])
  const [loading, setLoading] = useState(true)
  const [show, setShow] = useState(false)
  const [f, setF] = useState({ name:'', description:'', loader:'auto', splitter_type:'sentence', chunk_size:500, chunk_overlap:50 })
  const [iconFile, setIconFile] = useState<File|null>(null)
  const [iconPreview, setIconPreview] = useState<string>('')
  const iconRef = useRef<HTMLInputElement>(null)

  const load = async () => {
    setLoading(true)
    try { setKbs(await ragApi.listKb()) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  // 命令面板事件监听
  useEffect(() => {
    const h = () => {
      setF({ name:'', description:'', loader:'auto', splitter_type:'sentence', chunk_size:500, chunk_overlap:50 })
      setShow(true)
    }
    window.addEventListener('cmd-new-kb', h)
    return () => window.removeEventListener('cmd-new-kb', h)
  }, [])

  const onIcon = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    if (iconPreview) URL.revokeObjectURL(iconPreview)
    setIconFile(file); setIconPreview(URL.createObjectURL(file))
  }

  const create = async () => {
    if (!f.name.trim()) { toast.error('请填写名称'); return }
    const kb = await ragApi.createKb({
      name: f.name.trim(), description: f.description,
      loader: f.loader, splitter_type: f.splitter_type,
      chunk_size: Number(f.chunk_size), chunk_overlap: Number(f.chunk_overlap),
    })
    if (iconFile) {
      try { await ragApi.uploadIcon(kb.id, iconFile) }
      catch { toast.error('图标上传失败') }
    }
    if (iconPreview) URL.revokeObjectURL(iconPreview)
    toast.success('已创建'); setShow(false); load()
    setF({ name:'', description:'', loader:'auto', splitter_type:'sentence', chunk_size:500, chunk_overlap:50 })
    setIconFile(null); setIconPreview('')
  }

  const del = async (kb: KB) => {
    if (!confirm(`确定删除知识库 "${kb.name}"?\n所有文档和向量将被永久删除,此操作不可恢复。`)) return
    await ragApi.removeKb(kb.id); toast.success('已删除'); load()
  }

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">📚 知识库管理</h1>
          <p className="text-tertiary text-sm mt-1">上传文档构建向量知识库，为 Agent 提供检索增强能力</p>
        </div>
        <button onClick={()=>setShow(true)}
          className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-primary font-medium hover:opacity-90">
          ➕ 新建知识库
        </button>
      </div>

      {loading ? <p className="text-tertiary">加载中...</p> : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {kbs.map(kb => (
            <KBCard key={kb.id} kb={kb}
              onOpen={()=>nav(`/rag/${kb.id}`)} onDelete={()=>del(kb)} />
          ))}
          {kbs.length===0 && <p className="col-span-full text-center text-placeholder py-8">暂无知识库</p>}
        </div>
      )}

      {show && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" onClick={()=>setShow(false)}>
          <div className="bg-card border border rounded-2xl w-full max-w-xl p-6" onClick={e=>e.stopPropagation()}>
            <h2 className="text-xl font-bold mb-4">新建知识库</h2>
            <div className="space-y-3">
              <Field label="名称 *">
                <input value={f.name} onChange={e=>setF({...f,name:e.target.value})}
                  className="w-full px-3 py-2 rounded-lg bg-hover border border" />
              </Field>
              <Field label="描述">
                <textarea value={f.description} onChange={e=>setF({...f,description:e.target.value})} rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-hover border border resize-none" />
              </Field>
              <Field label="图标">
                <input ref={iconRef} type="file" accept="image/*" onChange={onIcon} className="text-sm" />
                {iconPreview && <img src={iconPreview} className="mt-2 w-16 h-16 rounded-lg object-cover" />}
              </Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="加载器">
                  <select value={f.loader} onChange={e=>setF({...f,loader:e.target.value})}
                    className="w-full px-3 py-2 rounded-lg bg-hover border border">
                    {loaders.map(l=><option key={l.key} value={l.key}>{l.label}</option>)}
                  </select>
                </Field>
                <Field label="分块方式">
                  <select value={f.splitter_type} onChange={e=>setF({...f,splitter_type:e.target.value})}
                    className="w-full px-3 py-2 rounded-lg bg-hover border border">
                    {splitters.map(s=><option key={s.key} value={s.key}>{s.label}</option>)}
                  </select>
                </Field>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <Field label="块大小">
                  <input type="number" value={f.chunk_size} onChange={e=>setF({...f,chunk_size:Number(e.target.value)})}
                    className="w-full px-3 py-2 rounded-lg bg-hover border border" />
                </Field>
                <Field label="重叠大小">
                  <input type="number" value={f.chunk_overlap} onChange={e=>setF({...f,chunk_overlap:Number(e.target.value)})}
                    className="w-full px-3 py-2 rounded-lg bg-hover border border" />
                </Field>
              </div>
            </div>
            <div className="flex justify-end gap-3 mt-5 pt-4 border-t border">
              <button onClick={()=>setShow(false)} className="px-4 py-2 rounded-lg bg-hover hover:bg-active">取消</button>
              <button onClick={create} className="px-4 py-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500">创建</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function KBCard({ kb, onOpen, onDelete }:{
  kb: KB; onOpen: ()=>void; onDelete: ()=>void
}) {
  const [menuOpen, setMenuOpen] = useState(false)
  const [imgErr, setImgErr] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    const handler = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false) }
    if (menuOpen) document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [menuOpen])

  return (
    <div className="bg-card border border rounded-xl p-4 hover:bg-hover transition relative group">
      {/* 三点菜单 */}
      <div ref={menuRef} className="absolute top-3 right-3">
        <button onClick={()=>setMenuOpen(!menuOpen)}
          className="w-8 h-8 rounded-lg flex items-center justify-center text-tertiary hover:text-primary hover:bg-hover transition">
          <span className="text-xl leading-none">⋯</span>
        </button>
        {menuOpen && (
          <div className="absolute right-0 top-9 bg-card border border rounded-lg shadow-md py-1 min-w-[100px] z-10">
            <button onClick={()=>{setMenuOpen(false); onOpen()}}
              className="w-full px-3 py-1.5 text-left text-sm hover:bg-hover">📂 进入</button>
            <button onClick={()=>{setMenuOpen(false); onDelete()}}
              className="w-full px-3 py-1.5 text-left text-sm text-red-400 hover:bg-red-500/20">🗑 删除</button>
          </div>
        )}
      </div>

      <div onClick={onOpen} className="cursor-pointer">
        <div className="flex items-start gap-3 mb-3 pr-8">
          {kb.icon_url && !imgErr ? (
            <img src={kb.icon_url} onError={()=>setImgErr(true)} className="w-12 h-12 rounded-lg object-cover" />
          ) : (
            <div className="w-12 h-12 rounded-lg bg-gradient-to-br from-emerald-500/30 to-teal-500/30 flex items-center justify-center text-2xl">📚</div>
          )}
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold truncate">{kb.name}</h3>
            <p className="text-sm text-tertiary line-clamp-2">{kb.description || '无描述'}</p>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-2">
          <div className="bg-card rounded p-2 text-center">
            <div className="font-bold">{kb.document_count ?? '-'}</div>
            <div className="text-xs text-tertiary">文档</div>
          </div>
          <div className="bg-card rounded p-2 text-center">
            <div className="font-bold">{kb.total_chunks ?? '-'}</div>
            <div className="text-xs text-tertiary">切块</div>
          </div>
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }: { label:string; children: React.ReactNode }) {
  return <div><label className="block text-sm text-secondary mb-1">{label}</label>{children}</div>
}
