import { useEffect, useState, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { groupApi, agentsApi, ragApi, workflowApi, skillApi, userApi, Member, GroupAgent, GroupKB, GroupMsg, GroupNotice } from '@/api'
import { useAuthStore } from '@/store/auth'

export default function GroupDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const gid = Number(id)
  const currentUserId = useAuthStore(s => s.user?.user_id)
  const [tab, setTab] = useState<'chat'|'members'|'shared'|'notices'>('chat')
  const [subTab, setSubTab] = useState<'agents'|'kbs'|'wfs'|'skills'>('agents')
  const [group, setGroup] = useState<any>(null)
  const [me, setMe] = useState<Member|null>(null)
  const [members, setMembers] = useState<Member[]>([])
  const [agents, setAgents] = useState<GroupAgent[]>([])
  const [kbs, setKbs] = useState<GroupKB[]>([])
  const [wfs, setWfs] = useState<any[]>([])
  const [skills, setSkills] = useState<any[]>([])
  const [msgs, setMsgs] = useState<GroupMsg[]>([])
  const [unreadNotices, setUnreadNotices] = useState(0)

  const reload = async () => {
    const [ms, gs, ks, ws, ss, allGroups] = await Promise.all([
      groupApi.listMembers(gid), groupApi.listAgents(gid), groupApi.listKBs(gid),
      groupApi.listWorkflows(gid), groupApi.listSkills(gid),
      groupApi.list(),
    ])
    setGroup(allGroups.find((g:any)=>g.id===gid) || null)
    setMembers(ms); setAgents(gs); setKbs(ks); setWfs(ws); setSkills(ss)
    const me0 = ms.find(m => m.user_id === currentUserId) || null
    setMe(me0)
  }
  const reloadMsgs = async () => {
    const list = await groupApi.listMsgs(gid, { limit: 100 })
    setMsgs(list.sort((a,b)=>a.id-b.id))
  }
  const reloadUnread = async () => {
    try {
      const ns = await groupApi.listNotices(gid)
      setUnreadNotices(ns.filter(n => !n.is_read).length)
    } catch {}
  }
  useEffect(() => {
    reload(); reloadMsgs(); reloadUnread()
    const t = setInterval(() => { reloadMsgs(); reloadUnread() }, 5000)
    return () => clearInterval(t)
  }, [gid])

  const myRole = me?.role
  const isOwner = myRole === 'owner'
  const onlineCount = members.filter(m => m.online).length

  return <div className="space-y-4">
    <div className="flex items-center gap-3 border-b border pb-2">
      {/* 左侧：群名 + 在线人数 */}
      <button onClick={()=>nav('/groups')} className="text-tertiary hover:text-primary text-sm shrink-0" title="返回">←</button>
      <div className="min-w-0 flex-1">
        <div className="font-semibold truncate">{group?.name || '群组'}</div>
        <div className="text-xs text-tertiary">
          <span className="text-emerald-400">●</span> 在线 {onlineCount}
          <span className="mx-1.5 text-placeholder">/</span>
          共 {members.length} 人
          {unreadNotices>0 && <span className="ml-2 text-pink-300">· {unreadNotices} 条未读公告</span>}
        </div>
      </div>
      {/* 右侧：三按钮菜单 */}
      <details className="relative shrink-0">
        <summary className="list-none cursor-pointer w-8 h-8 rounded-lg bg-card hover:bg-hover flex items-center justify-center text-secondary select-none">
          ☰
        </summary>
        <div className="absolute right-0 top-full mt-1 bg-card/95 border border rounded-lg p-1 z-30 shadow-md min-w-[150px]">
          <button onClick={()=>{setTab('chat'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded ${tab==='chat'?'text-pink-300':'text-primary'}`}>💬 群聊</button>
          <button onClick={()=>{setTab('notices'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded flex items-center justify-between ${tab==='notices'?'text-pink-300':'text-primary'}`}>
            📢 公告 {unreadNotices>0 && <span className="bg-pink-500 text-primary rounded-full px-1.5 text-[10px]">{unreadNotices}</span>}
          </button>
          <button onClick={()=>{setTab('members'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded ${tab==='members'?'text-pink-300':'text-primary'}`}>👥 成员</button>
          <div className="h-px bg-hover my-1" />
          <div className="px-3 py-1 text-[10px] text-placeholder">📦 共享资源</div>
          <button onClick={()=>{setTab('shared'); setSubTab('agents'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5 ${tab==='shared'&&subTab==='agents'?'text-pink-300':'text-primary'}`}>
              🤖 Agent {agents.length>0 && <span className="text-placeholder">({agents.length})</span>}
          </button>
          <button onClick={()=>{setTab('shared'); setSubTab('wfs'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5 ${tab==='shared'&&subTab==='wfs'?'text-pink-300':'text-primary'}`}>
              ⚡ 工作流 {wfs.length>0 && <span className="text-placeholder">({wfs.length})</span>}
          </button>
          <button onClick={()=>{setTab('shared'); setSubTab('skills'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5 ${tab==='shared'&&subTab==='skills'?'text-pink-300':'text-primary'}`}>
              🧩 技能 {skills.length>0 && <span className="text-placeholder">({skills.length})</span>}
          </button>
          <button onClick={()=>{setTab('shared'); setSubTab('kbs'); const el=document.activeElement as HTMLElement; el?.blur()}}
            className={`block w-full text-left px-3 py-1.5 text-xs hover:bg-hover rounded pl-5 ${tab==='shared'&&subTab==='kbs'?'text-pink-300':'text-primary'}`}>
              📚 知识库 {kbs.length>0 && <span className="text-placeholder">({kbs.length})</span>}
          </button>
        </div>
      </details>
    </div>
    {tab==='members' && <MembersTab members={members} gid={gid} isOwner={isOwner} onReload={reload} />}
    {tab==='shared' && (
      <div className="space-y-3">
        <div className="flex gap-1 text-xs">
          {[
            ['agents', `🤖 Agent (${agents.length})`],
            ['wfs', `⚡ 工作流 (${wfs.length})`],
            ['skills', `🧩 技能 (${skills.length})`],
            ['kbs', `📚 知识库 (${kbs.length})`],
          ].map(([k,l]) => (
            <button key={k} onClick={()=>setSubTab(k as any)}
              className={`px-3 py-1.5 rounded-lg transition ${subTab===k?'bg-pink-500/30 text-pink-200':'bg-card hover:bg-hover text-secondary'}`}>
              {l}
            </button>
          ))}
        </div>
        {subTab==='agents' && <AgentsTab shared={agents} gid={gid} isOwner={isOwner} onReload={reload} />}
        {subTab==='kbs' && <KBTab shared={kbs} gid={gid} isOwner={isOwner} onReload={reload} />}
        {subTab==='wfs' && <WorkflowsTab shared={wfs} gid={gid} isOwner={isOwner} onReload={reload} />}
        {subTab==='skills' && <SkillsTab shared={skills} gid={gid} isOwner={isOwner} onReload={reload} />}
      </div>
    )}
    {tab==='chat' && <ChatTab gid={gid} msgs={msgs} agents={agents} me={me} onReload={reloadMsgs} />}
    {tab==='notices' && <NoticesTab gid={gid} isOwner={isOwner} onUnreadChange={reloadUnread} />}
  </div>
}

function MembersTab({ members, gid, isOwner, onReload }:{members:Member[];gid:number;isOwner:boolean;onReload:()=>void}) {
  const [showInvite, setShowInvite] = useState(false)
  const [allUsers, setAllUsers] = useState<any[]>([])
  const [inviteId, setInviteId] = useState<number|null>(null)
  const [transferId, setTransferId] = useState<number|null>(null)

  useEffect(() => {
    if (isOwner) {
      // 管理员/超管能拉所有用户列表，否则只能加已知
      userApi.list().then(setAllUsers).catch(()=>{})
    }
  }, [isOwner])

  const kick = async (uid: number) => {
    if (!confirm('踢出该成员? 该成员共享的资源也会被移除')) return
    try { await groupApi.kickMember(gid, uid); toast.success('已踢出'); onReload() } catch {}
  }
  const invite = async () => {
    if (!inviteId) return
    try { await groupApi.inviteMember(gid, inviteId); toast.success('已邀请加入'); setShowInvite(false); setInviteId(null); onReload() } catch {}
  }
  const transfer = async (uid: number) => {
    const target = members.find(m => m.user_id === uid)
    if (!confirm(`将群主转让给 ${target?.username}? 你将降级为普通成员`)) return
    try { await groupApi.transferOwner(gid, uid); toast.success('群主已转让'); onReload() } catch {}
  }

  const existingIds = new Set(members.map(m => m.user_id))
  const candidates = allUsers.filter(u => !existingIds.has(u.user_id))

  return <div className="space-y-3">
    {isOwner && (
      <div className="flex gap-2">
        <button onClick={()=>setShowInvite(!showInvite)} className="px-3 py-1.5 text-sm rounded-lg bg-pink-500/20 text-pink-200 hover:bg-pink-500/30">
          ➕ 邀请成员
        </button>
      </div>
    )}
    {showInvite && isOwner && (
      <div className="bg-card rounded-xl p-3 flex gap-2">
        <select value={inviteId||''} onChange={e=>setInviteId(Number(e.target.value))} className="flex-1 px-3 py-2 rounded bg-hover border border text-sm">
          <option value="">-- 选择用户 --</option>
          {candidates.map(u => <option key={u.user_id} value={u.user_id}>{u.username} (@{u.account}) · {u.role}</option>)}
          {candidates.length === 0 && <option value="" disabled>没有可邀请的用户</option>}
        </select>
        <button onClick={invite} disabled={!inviteId} className="px-4 py-2 rounded bg-pink-500/30 text-pink-200 disabled:opacity-50 text-sm">邀请</button>
      </div>
    )}
    <div className="space-y-2">
      {members.map(m=>(
        <div key={m.user_id} className="bg-card border border rounded-xl p-3 flex items-center gap-3">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-pink-500 to-rose-500 flex items-center justify-center">
            {(m.username||'U')[0].toUpperCase()}
          </div>
          <div className="flex-1">
            <div className="flex items-center gap-2">
              <span className="font-medium">{m.username}</span>
              <span className={`text-xs px-2 py-0.5 rounded ${m.role==='owner'?'bg-pink-500/30 text-pink-200':'bg-hover'}`}>
                {m.role==='owner'?'群主':'成员'}
              </span>
              {m.online && <span className="w-2 h-2 rounded-full bg-green-400" />}
            </div>
            <div className="text-xs text-placeholder">最后活跃: {m.last_active_at ? new Date(m.last_active_at).toLocaleString() : '-'}</div>
          </div>
          {isOwner && m.role!=='owner' && (
            <div className="flex gap-1">
              <button onClick={()=>transfer(m.user_id)} className="px-2 py-1 text-xs rounded text-amber-400 hover:bg-amber-500/20" title="转让群主">👑</button>
              <button onClick={()=>kick(m.user_id)} className="px-2 py-1 text-xs rounded text-red-400 hover:bg-red-500/20">踢出</button>
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
}

function AgentsTab({ shared, gid, isOwner, onReload }:{shared:GroupAgent[];gid:number;isOwner:boolean;onReload:()=>void}) {
  const [all, setAll] = useState<any[]>([])
  const [sel, setSel] = useState<number|null>(null)
  useEffect(()=>{ agentsApi.list({enabled_only:true}).then(setAll).catch(()=>{}) }, [])
  const myId = shared.map(s=>s.agent_id)
  const available = all.filter(a=>!myId.includes(a.id))

  const share = async () => { if (!sel) return; await groupApi.shareAgent(gid, sel); toast.success('已共享'); setSel(null); onReload() }
  const unshare = async (aid: number) => { if(!confirm('取消共享?')) return; await groupApi.unshareAgent(gid, aid); onReload() }
  return <div className="space-y-3">
    {available.length>0 && <div className="bg-card rounded-xl p-3 flex gap-2">
      <select value={sel||''} onChange={e=>setSel(Number(e.target.value))} className="flex-1 px-3 py-2 rounded bg-hover border border">
        <option value="">-- 选择我的 Agent 共享 --</option>
        {available.map(a=><option key={a.id} value={a.id}>{a.display_name||a.name}</option>)}
      </select>
      <button onClick={share} disabled={!sel} className="px-4 py-2 rounded bg-pink-500/30 text-pink-200 disabled:opacity-50">共享</button>
    </div>}
    {shared.map(s=>(
      <div key={s.agent_id} className="bg-card border border rounded-xl p-3 flex justify-between items-center">
        <div><div className="font-medium">{s.name}</div><div className="text-xs text-tertiary">{s.description} · 共享者 #{s.shared_by}</div></div>
        <button onClick={()=>unshare(s.agent_id)} className="px-3 py-1 text-xs rounded text-red-400 hover:bg-red-500/20">取消</button>
      </div>
    ))}
    {shared.length===0 && <p className="text-placeholder text-center py-8">暂无共享 Agent</p>}
  </div>
}

function KBTab({ shared, gid, isOwner, onReload }:{shared:GroupKB[];gid:number;isOwner:boolean;onReload:()=>void}) {
  const [all, setAll] = useState<any[]>([])
  const [sel, setSel] = useState<number|null>(null)
  useEffect(()=>{ ragApi.listKb().then(setAll).catch(()=>{}) }, [])
  const myIds = shared.map(s=>s.kb_id)
  const available = all.filter(k=>!myIds.includes(k.id))
  const share = async () => { if(!sel)return; await groupApi.shareKB(gid, sel); toast.success('已共享'); setSel(null); onReload() }
  const unshare = async (kid: number) => { if(!confirm('取消共享?'))return; await groupApi.unshareKB(gid, kid); onReload() }
  return <div className="space-y-3">
    {available.length>0 && <div className="bg-card rounded-xl p-3 flex gap-2">
      <select value={sel||''} onChange={e=>setSel(Number(e.target.value))} className="flex-1 px-3 py-2 rounded bg-hover border border">
        <option value="">-- 选择我的知识库共享 --</option>
        {available.map(k=><option key={k.id} value={k.id}>{k.name}</option>)}
      </select>
      <button onClick={share} disabled={!sel} className="px-4 py-2 rounded bg-pink-500/30 text-pink-200 disabled:opacity-50">共享</button>
    </div>}
    {shared.map(k=>(
      <div key={k.kb_id} className="bg-card border border rounded-xl p-3 flex justify-between items-center">
        <div><div className="font-medium">{k.name}</div><div className="text-xs text-tertiary">{k.description} · 共享者 #{k.shared_by}</div></div>
        <button onClick={()=>unshare(k.kb_id)} className="px-3 py-1 text-xs rounded text-red-400 hover:bg-red-500/20">取消</button>
      </div>
    ))}
    {shared.length===0 && <p className="text-placeholder text-center py-8">暂无共享知识库</p>}
  </div>
}

function WorkflowsTab({ shared, gid, isOwner, onReload }:{shared:any[];gid:number;isOwner:boolean;onReload:()=>void}) {
  const [all, setAll] = useState<any[]>([])
  const [sel, setSel] = useState<number|null>(null)
  useEffect(()=>{ workflowApi.list().then(setAll).catch(()=>{}) }, [])
  const myIds = shared.map(s=>s.workflow_id)
  const available = all.filter(w=>!myIds.includes(w.id))
  const share = async () => { if(!sel)return; await groupApi.shareWorkflow(gid, sel); toast.success('已共享'); setSel(null); onReload() }
  const unshare = async (id: number) => { if(!confirm('取消共享?'))return; await groupApi.unshareWorkflow(gid, id); onReload() }
  return <div className="space-y-3">
    {available.length>0 && <div className="bg-card rounded-xl p-3 flex gap-2">
      <select value={sel||''} onChange={e=>setSel(Number(e.target.value))} className="flex-1 px-3 py-2 rounded bg-hover border border">
        <option value="">-- 选择我的工作流共享 --</option>
        {available.map(w=><option key={w.id} value={w.id}>{w.display_name || w.name}{w.category ? ` · ${w.category}` : ''}</option>)}
      </select>
      <button onClick={share} disabled={!sel} className="px-4 py-2 rounded bg-pink-500/30 text-pink-200 disabled:opacity-50">共享</button>
    </div>}
    {shared.map(w=>(
      <div key={w.workflow_id} className="bg-card border border rounded-xl p-3 flex justify-between items-center">
        <div className="min-w-0 flex-1">
          <div className="font-medium">⚡ {w.display_name || w.name}</div>
          <div className="text-xs text-tertiary truncate">{w.description || '无描述'}{w.category ? ` · ${w.category}` : ''} · 共享者 #{w.shared_by}</div>
        </div>
        <button onClick={()=>unshare(w.workflow_id)} className="px-3 py-1 text-xs rounded text-red-400 hover:bg-red-500/20">取消</button>
      </div>
    ))}
    {shared.length===0 && <p className="text-placeholder text-center py-8">暂无共享工作流</p>}
  </div>
}

function SkillsTab({ shared, gid, isOwner, onReload }:{shared:any[];gid:number;isOwner:boolean;onReload:()=>void}) {
  const [all, setAll] = useState<any[]>([])
  const [sel, setSel] = useState<number|null>(null)
  useEffect(()=>{ skillApi.list().then(setAll).catch(()=>{}) }, [])
  const myIds = shared.map(s=>s.skill_id)
  const available = all.filter(s=>!myIds.includes(s.id))
  const share = async () => { if(!sel)return; await groupApi.shareSkill(gid, sel); toast.success('已共享'); setSel(null); onReload() }
  const unshare = async (id: number) => { if(!confirm('取消共享?'))return; await groupApi.unshareSkill(gid, id); onReload() }
  return <div className="space-y-3">
    {available.length>0 && <div className="bg-card rounded-xl p-3 flex gap-2">
      <select value={sel||''} onChange={e=>setSel(Number(e.target.value))} className="flex-1 px-3 py-2 rounded bg-hover border border">
        <option value="">-- 选择技能共享 --</option>
        {available.map(s=><option key={s.id} value={s.id}>{s.display_name || s.name}{s.is_builtin ? ' (内置)' : ''}</option>)}
      </select>
      <button onClick={share} disabled={!sel} className="px-4 py-2 rounded bg-pink-500/30 text-pink-200 disabled:opacity-50">共享</button>
    </div>}
    {shared.map(s=>(
      <div key={s.skill_id} className="bg-card border border rounded-xl p-3 flex justify-between items-center">
        <div className="min-w-0 flex-1">
          <div className="font-medium flex items-center gap-2">
            🧩 {s.display_name || s.name}
            {s.is_builtin && <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-500/20 text-cyan-300">内置</span>}
          </div>
          <div className="text-xs text-tertiary truncate">{s.description || '无描述'}{s.category ? ` · ${s.category}` : ''}</div>
        </div>
        {!s.is_builtin && <button onClick={()=>unshare(s.skill_id)} className="px-3 py-1 text-xs rounded text-red-400 hover:bg-red-500/20">取消</button>}
      </div>
    ))}
    {shared.length===0 && <p className="text-placeholder text-center py-8">暂无共享技能</p>}
  </div>
}

function ChatTab({ gid, msgs, agents, me, onReload }:{gid:number;msgs:GroupMsg[];agents:GroupAgent[];me:Member|null;onReload:()=>void}) {
  const [content, setContent] = useState('')
  const [agentSel, setAgentSel] = useState('')
  const [sending, setSending] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)
  useEffect(()=>{ scrollRef.current?.scrollTo({top:scrollRef.current.scrollHeight, behavior:'smooth'}) }, [msgs])

  const send = async () => {
    if (!content.trim()||sending) return
    setSending(true)
    try {
      await groupApi.sendMsg(gid, { content: content.trim(), agent_name: agentSel||undefined })
      setContent(''); setAgentSel(''); onReload()
    } finally { setSending(false) }
  }
  const del = async (mid:number) => {
    if(!confirm('撤回?')) return; await groupApi.deleteMsg(gid, mid); onReload()
  }

  return <div className="flex flex-col h-[70vh] bg-card border border rounded-xl overflow-hidden">
    <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-3">
      {msgs.map(m=>{
        const mine = m.user_id === me?.user_id
        return <div key={m.id} className={`flex ${mine?'justify-end':'justify-start'}`}>
          <div className={`max-w-[70%] ${m.role==='bot'?'bg-gradient-to-r from-purple-600/40 to-cyan-600/40':'bg-hover'} rounded-xl px-3 py-2`}>
            <div className="text-xs text-tertiary mb-0.5">
              {m.role==='bot'?`🤖 ${m.agent_name||'Bot'}`:m.username}
            </div>
            <div className="whitespace-pre-wrap">{m.content}</div>
            {(mine||me?.role==='owner') && <button onClick={()=>del(m.id)} className="text-xs text-placeholder hover:text-tertiary mt-1">撤回</button>}
          </div>
        </div>
      })}
      {msgs.length===0 && <p className="text-center text-placeholder py-10">还没有消息,发一条吧</p>}
    </div>
    <div className="p-3 border-t border flex gap-2 items-center">
      <select value={agentSel} onChange={e=>setAgentSel(e.target.value)}
        className="px-2 py-2 rounded bg-hover border border text-sm">
        <option value="">普通消息</option>
        {agents.map(a=><option key={a.agent_id} value={a.name}>@{a.name}</option>)}
      </select>
      <input value={content} onChange={e=>setContent(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}}
        placeholder={agentSel?`@${agentSel} 会回复...`:'输入消息...'}
        className="flex-1 px-3 py-2 rounded bg-hover border border" />
      <button onClick={send} disabled={sending||!content.trim()}
        className="px-4 py-2 rounded bg-gradient-to-r from-pink-500 to-rose-500 disabled:opacity-50">发送</button>
    </div>
  </div>
}

// ========== 公告 Tab ==========
function NoticesTab({ gid, isOwner, onUnreadChange }: { gid: number; isOwner: boolean; onUnreadChange: () => void }) {
  const [notices, setNotices] = useState<GroupNotice[]>([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [pinned, setPinned] = useState(false)
  const [saving, setSaving] = useState(false)

  const load = async () => {
    setLoading(true)
    try { setNotices(await groupApi.listNotices(gid)) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [gid])

  const markRead = async (n: GroupNotice) => {
    if (n.is_read) return
    try {
      await groupApi.markNoticeRead(gid, n.id)
      setNotices(prev => prev.map(x => x.id === n.id ? { ...x, is_read: true, read_count: x.read_count + 1 } : x))
      onUnreadChange()
    } catch {}
  }

  const publish = async () => {
    if (!content.trim()) { toast.error('请填写公告内容'); return }
    setSaving(true)
    try {
      await groupApi.createNotice(gid, { title: title.trim(), content: content.trim(), pinned })
      toast.success('公告已发布')
      setShowForm(false); setTitle(''); setContent(''); setPinned(false)
      load(); onUnreadChange()
    } finally { setSaving(false) }
  }

  const del = async (n: GroupNotice) => {
    if (!confirm(`删除公告 "${n.title || n.content.slice(0, 20)}" ?`)) return
    try { await groupApi.deleteNotice(gid, n.id); toast.success('已删除'); load() } catch {}
  }

  const togglePin = async (n: GroupNotice) => {
    try { await groupApi.toggleNoticePin(gid, n.id, !n.pinned); load() } catch {}
  }

  if (loading) return <p className="text-tertiary text-sm py-8 text-center">加载中...</p>

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-bold">📢 群公告</h3>
          <p className="text-tertiary text-xs mt-0.5">置顶公告对群内所有成员展示，成员需标记已读</p>
        </div>
        {isOwner && (
          <button onClick={() => setShowForm(v => !v)}
            className="px-3 py-1.5 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 text-sm">
            {showForm ? '取消' : '➕ 发布公告'}
          </button>
        )}
      </div>

      {showForm && (
        <div className="bg-card border border rounded-xl p-4 space-y-3">
          <input value={title} onChange={e => setTitle(e.target.value)} placeholder="公告标题（可选）"
            className="w-full px-3 py-2 rounded-lg bg-hover border border text-sm" />
          <textarea value={content} onChange={e => setContent(e.target.value)}
            placeholder="公告内容..."
            className="w-full px-3 py-2 rounded-lg bg-hover border border text-sm resize-none min-h-[100px]" />
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
              <input type="checkbox" checked={pinned} onChange={e => setPinned(e.target.checked)} />
              📌 置顶
            </label>
            <button onClick={publish} disabled={saving}
              className="px-4 py-1.5 rounded-lg bg-gradient-to-r from-pink-500 to-rose-500 text-sm disabled:opacity-50">
              {saving ? '发布中...' : '发布'}
            </button>
          </div>
        </div>
      )}

      {notices.length === 0 ? (
        <div className="py-12 text-center text-placeholder text-sm">暂无公告</div>
      ) : (
        <div className="space-y-3">
          {notices.map(n => (
            <div key={n.id} onClick={() => markRead(n)}
              className={`rounded-xl border p-4 cursor-pointer transition ${
                n.is_read ? 'bg-card border' : 'bg-amber-500/5 border-amber-500/30 ring-1 ring-amber-500/20'
              }`}>
              <div className="flex items-start gap-3">
                {n.author_avatar
                  ? <img src={n.author_avatar} alt="" className="w-9 h-9 rounded-full object-cover shrink-0" />
                  : <div className="w-9 h-9 rounded-full bg-gradient-to-br from-purple-500 to-pink-500 flex items-center justify-center text-sm font-bold text-primary shrink-0">{n.author_name.slice(0,1).toUpperCase()}</div>
                }
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    {n.pinned && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/30 text-amber-200">📌 置顶</span>}
                    {!n.is_read && <span className="text-[10px] px-1.5 py-0.5 rounded bg-red-500/30 text-red-200">未读</span>}
                    {n.title && <span className="font-semibold">{n.title}</span>}
                    <span className="text-xs text-placeholder">
                      {n.author_name} · {new Date(n.created_at).toLocaleString('zh-CN')}
                    </span>
                  </div>
                  <div className="text-sm text-primary whitespace-pre-wrap mt-1.5 leading-relaxed">{n.content}</div>
                  <div className="flex items-center justify-between mt-2">
                    <div className="text-xs text-placeholder">👁 {n.read_count} 人已读</div>
                    {isOwner && (
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100" onClick={e => e.stopPropagation()}>
                        <button onClick={() => togglePin(n)} className="text-xs px-2 py-0.5 rounded hover:bg-hover text-tertiary">
                          {n.pinned ? '取消置顶' : '置顶'}
                        </button>
                        <button onClick={() => del(n)} className="text-xs px-2 py-0.5 rounded hover:bg-red-500/20 text-red-300">删除</button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
