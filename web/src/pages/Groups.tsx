import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { groupApi, Group } from '@/api'

export default function Groups() {
  const nav = useNavigate()
  const [groups, setGroups] = useState<Group[]>([])
  const [show, setShow] = useState(false)
  const [joinShow, setJoinShow] = useState(false)
  const [f, setF] = useState({ name:'', description:'' })
  const [gid, setGid] = useState('')

  const load = async () => setGroups(await groupApi.list())
  useEffect(() => { load() }, [])

  const create = async () => {
    if (!f.name.trim()) { toast.error('请填群名'); return }
    await groupApi.create(f); toast.success('已创建'); setShow(false); load()
    setF({ name:'', description:'' })
  }
  const join = async () => {
    if (!gid.trim()) return
    try { await groupApi.join(Number(gid)); toast.success('已加入'); setJoinShow(false); load() } catch {}
  }
  const leave = async (g: Group) => {
    if (!confirm(`退出 "${g.name}"?`)) return
    await groupApi.leave(g.id); load()
  }
  const disband = async (g: Group) => {
    if (!confirm(`解散 "${g.name}"?`)) return
    await groupApi.disband(g.id); toast.success('已解散'); load()
  }

  return <div className="space-y-5">
    <div className="flex items-center justify-between">
      <div>
        <h1 className="text-2xl font-bold">👥 协作群组</h1>
        <p className="text-tertiary text-sm mt-1">与团队共享 Agent 和知识库</p>
      </div>
      <div className="flex gap-2">
        <button onClick={()=>setJoinShow(true)} className="px-4 py-2 rounded-lg bg-hover hover:bg-active">🔗 加入群</button>
        <button onClick={()=>setShow(true)} className="px-4 py-2 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 text-primary">➕ 创建群</button>
      </div>
    </div>

    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      {groups.map(g=>(
        <div key={g.id} className="bg-card border border rounded-xl p-4">
          <div className="flex items-start gap-3">
            <div className="w-12 h-12 rounded-xl bg-gradient-to-br from-pink-500/30 to-rose-500/30 flex items-center justify-center text-2xl relative">
              👥
              {g.unread_notices ? <span className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full bg-red-500 text-primary text-[10px] flex items-center justify-center font-bold">{g.unread_notices}</span> : null}
            </div>
            <div className="flex-1">
              <h3 className="font-semibold">{g.name}</h3>
              <p className="text-sm text-tertiary line-clamp-2">{g.description || '无描述'}</p>
              <p className="text-xs text-placeholder mt-1">成员 {g.member_count ?? '-'} · ID: {g.id}{g.unread_notices ? ` · 📢 ${g.unread_notices} 条未读公告` : ''}</p>
            </div>
          </div>
          <div className="flex gap-2 mt-3 pt-3 border-t border">
            <button onClick={()=>nav(`/groups/${g.id}`)} className="flex-1 py-1.5 text-sm rounded bg-pink-500/20 text-pink-300 hover:bg-pink-500/30">进入</button>
            <button onClick={()=>{ if (confirm(`解散群 "${g.name}"?`)) disband(g) }}
              className="px-3 py-1.5 text-sm rounded text-red-400 hover:bg-red-500/20">解散</button>
          </div>
        </div>
      ))}
      {groups.length===0 && <p className="col-span-full text-center text-placeholder py-8">暂无群组</p>}
    </div>

    {show && <Modal title="创建群组" onClose={()=>setShow(false)}>
      <In label="群名" value={f.name} onChange={v=>setF({...f,name:v})} />
      <div className="mt-3">
        <label className="block text-sm text-secondary mb-1">描述</label>
        <textarea value={f.description} onChange={e=>setF({...f,description:e.target.value})} rows={2}
          className="w-full px-3 py-2 rounded bg-hover border border resize-none" />
      </div>
      <div className="flex justify-end gap-3 mt-4">
        <button onClick={()=>setShow(false)} className="px-4 py-2 rounded bg-hover">取消</button>
        <button onClick={create} className="px-4 py-2 rounded bg-gradient-to-r from-pink-500 to-rose-500">创建</button>
      </div>
    </Modal>}
    {joinShow && <Modal title="加入群组" onClose={()=>setJoinShow(false)}>
      <In label="群组 ID" value={gid} onChange={setGid} />
      <p className="text-xs text-placeholder mt-2">向群主获取 ID</p>
      <div className="flex justify-end gap-3 mt-4">
        <button onClick={()=>setJoinShow(false)} className="px-4 py-2 rounded bg-hover">取消</button>
        <button onClick={join} className="px-4 py-2 rounded bg-gradient-to-r from-pink-500 to-rose-500">加入</button>
      </div>
    </Modal>}
  </div>
}

function Modal({ title, children, onClose }:{ title:string; children:React.ReactNode; onClose:()=>void }) {
  return <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
    <div className="bg-card border border rounded-2xl w-full max-w-md p-6" onClick={e=>e.stopPropagation()}>
      <h2 className="text-xl font-bold mb-4">{title}</h2>{children}
    </div>
  </div>
}
function In({label,value,onChange}:{label:string;value:string;onChange:(v:string)=>void}){
  return <div><label className="block text-sm text-secondary mb-1">{label}</label>
    <input value={value} onChange={e=>onChange(e.target.value)} className="w-full px-3 py-2 rounded bg-hover border border" /></div>
}
