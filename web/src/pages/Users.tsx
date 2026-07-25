import { useEffect, useMemo, useState } from 'react'
import toast from 'react-hot-toast'
import { userApi, User, UserTreeNode, UserUpdateIn } from '@/api'
import { useAuthStore } from '@/store/auth'
import Modal from '@/components/ui/Modal'
import Button from '@/components/ui/Button'
import Input from '@/components/ui/Input'

type ViewMode = 'tree' | 'table'

export default function Users() {
  const me = useAuthStore(s => s.user)
  const isSuper = me?.role === 'super_admin'
  const isAdmin = isSuper || me?.role === 'admin'
  const [tree, setTree] = useState<UserTreeNode[]>([])
  const [keyword, setKeyword] = useState('')
  const [collapsed, setCollapsed] = useState<Set<number>>(new Set())
  const [view, setView] = useState<ViewMode>('tree')
  const [editing, setEditing] = useState<User | null>(null)
  const [creating, setCreating] = useState(false)

  const load = async () => {
    const t = await userApi.tree({ keyword: keyword || undefined })
    setTree(t)
  }
  useEffect(() => { load() }, [keyword])

  const total = useMemo(() => {
    let n = 0
    const walk = (nodes: UserTreeNode[]) => { nodes.forEach(x => { n++; walk(x.children) }) }
    walk(tree); return n
  }, [tree])

  const toggleCollapse = (id: number) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id); else next.add(id)
      return next
    })
  }

  const expandAll = () => setCollapsed(new Set())
  const collapseAll = () => {
    const all = new Set<number>()
    const walk = (nodes: UserTreeNode[]) => nodes.forEach(n => { all.add(n.user_id); walk(n.children) })
    walk(tree); setCollapsed(all)
  }

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between gap-4 flex-wrap">
        <div>
          <h1 className="text-2xl font-bold">👥 用户管理</h1>
          <p className="text-tertiary text-sm mt-1">
            {isSuper ? '超级管理员视图 · 全公司组织树' : '管理员视图 · 你管理的用户'}
            {keyword && ` · 搜索 "${keyword}"`} · 共 {total} 人
          </p>
        </div>
        {isAdmin && (
          <Button onClick={() => setCreating(true)}>➕ 创建用户</Button>
        )}
      </div>

      {/* 工具栏 */}
      <div className="flex items-center gap-3 flex-wrap">
        <input
          value={keyword} onChange={e => setKeyword(e.target.value)}
          placeholder="搜索用户名/账号/邮箱/职位/部门..."
          className="flex-1 min-w-[200px] px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 text-sm"
        />
        <div className="flex rounded-lg bg-card border border p-0.5 text-sm">
          <button onClick={() => setView('tree')}
            className={`px-3 py-1.5 rounded-md transition ${view === 'tree' ? 'bg-hover text-primary' : 'text-tertiary hover:text-primary'}`}>
            🌳 树状
          </button>
          <button onClick={() => setView('table')}
            className={`px-3 py-1.5 rounded-md transition ${view === 'table' ? 'bg-hover text-primary' : 'text-tertiary hover:text-primary'}`}>
            📋 表格
          </button>
        </div>
        {view === 'tree' && (
          <>
            <button onClick={expandAll} className="text-xs px-2.5 py-1.5 rounded-lg bg-card hover:bg-hover border border text-secondary">全部展开</button>
            <button onClick={collapseAll} className="text-xs px-2.5 py-1.5 rounded-lg bg-card hover:bg-hover border border text-secondary">全部折叠</button>
          </>
        )}
      </div>

      {/* 内容 */}
      {view === 'tree' ? (
        <div className="bg-card border border rounded-xl p-3 space-y-1">
          {tree.length === 0 ? (
            <div className="py-12 text-center text-placeholder text-sm">暂无用户</div>
          ) : tree.map(n => (
            <TreeNode key={n.user_id} node={n} depth={0} me={me!}
              collapsed={collapsed}
              onToggle={toggleCollapse}
              onEdit={(u) => setEditing(u)}
              onRefresh={load}
              isAdmin={isAdmin} isSuper={isSuper} />
          ))}
        </div>
      ) : (
        <FlatTable users={tree} me={me!} isAdmin={isAdmin} isSuper={isSuper} onEdit={u => setEditing(u)} onRefresh={load} />
      )}

      {/* 创建用户 */}
      {creating && (
        <UserEditModal
          mode="create"
          onClose={() => setCreating(false)}
          onSaved={() => { setCreating(false); load() }}
          isSuper={isSuper}
        />
      )}
      {/* 编辑用户 */}
      {editing && (
        <UserEditModal
          mode="edit"
          user={editing}
          onClose={() => setEditing(null)}
          onSaved={() => { setEditing(null); load() }}
          isSuper={isSuper}
        />
      )}
    </div>
  )
}

// ========== 角色徽章 ==========
function RoleBadge({ role }: { role: string }) {
  const map: Record<string, { label: string; cls: string }> = {
    super_admin: { label: '超级管理员', cls: 'bg-gradient-to-r from-amber-500/30 to-orange-500/30 text-amber-200 border-amber-500/40' },
    admin: { label: '管理员', cls: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40' },
    user: { label: '成员', cls: 'bg-hover text-secondary border' },
  }
  const m = map[role] || map.user
  return <span className={`px-1.5 py-0.5 rounded text-[10px] border ${m.cls}`}>{m.label}</span>
}

function StatusDot({ enabled, online }: { enabled: boolean; online?: boolean }) {
  if (!enabled) return <span className="w-2 h-2 rounded-full bg-gray-500 inline-block" title="已禁用" />
  if (online) return <span className="w-2 h-2 rounded-full bg-green-400 inline-block shadow-sm shadow-green-400/50" title="在线" />
  return <span className="w-2 h-2 rounded-full bg-active inline-block" title="离线" />
}

function UserAvatar({ u, size = 36 }: { u: { avatar_url?: string; username?: string; account?: string }; size?: number }) {
  const initial = (u.username || u.account || 'U').slice(0, 1).toUpperCase()
  return (
    <div className="rounded-full bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center font-semibold text-primary shrink-0 overflow-hidden"
      style={{ width: size, height: size, fontSize: size * 0.4 }}>
      {u.avatar_url ? <img src={u.avatar_url} alt="" className="w-full h-full object-cover" /> : initial}
    </div>
  )
}

// ========== 树节点 ==========
function TreeNode({ node, depth, me, collapsed, onToggle, onEdit, onRefresh, isAdmin, isSuper }: {
  node: UserTreeNode; depth: number; me: User
  collapsed: Set<number>; onToggle: (id: number) => void
  onEdit: (u: User) => void; onRefresh: () => void
  isAdmin: boolean; isSuper: boolean
}) {
  const isCollapsed = collapsed.has(node.user_id)
  const hasChildren = node.children.length > 0
  const isSelf = node.user_id === me.user_id
  const canManage = isAdmin && (isSuper || node.manager_id === me.user_id || isInMySubtree(node, me.user_id))

  const online = node.last_active_at ? (Date.now() - new Date(node.last_active_at).getTime() < 60000) : false

  const del = async () => {
    if (isSelf) { toast.error('不能删除自己'); return }
    if (!confirm(`确定删除用户 ${node.username}?`)) return
    try { await userApi.remove(node.user_id); toast.success('已删除'); onRefresh() } catch {}
  }
  const toggleEnabled = async () => {
    if (isSelf) { toast.error('不能修改自己的状态'); return }
    try { await userApi.setEnabled(node.user_id, !node.enabled); toast.success(node.enabled ? '已禁用' : '已启用'); onRefresh() } catch {}
  }

  return (
    <div>
      <div
        className={`flex items-center gap-2 py-2 px-2 rounded-lg group hover:bg-card transition ${isSelf ? 'bg-purple-500/10' : ''}`}
        style={{ paddingLeft: depth * 20 + 8 }}
      >
        {/* 展开/折叠按钮 */}
        <button
          onClick={() => hasChildren && onToggle(node.user_id)}
          className={`w-5 h-5 flex items-center justify-center rounded text-placeholder hover:text-primary hover:bg-hover transition ${hasChildren ? 'cursor-pointer' : 'invisible'}`}
        >
          <span className={`transition-transform text-xs ${isCollapsed ? '' : 'rotate-90'}`}>▶</span>
        </button>

        {/* 头像 */}
        <UserAvatar u={node} size={32} />

        {/* 信息 */}
        <div className="flex-1 min-w-0 flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 min-w-0">
            <StatusDot enabled={node.enabled} online={online} />
            <span className="font-medium truncate">{node.username}</span>
            {isSelf && <span className="text-[10px] px-1.5 py-0.5 bg-purple-500/40 text-purple-100 rounded">我</span>}
            <RoleBadge role={node.role} />
          </div>
          {(node.title || node.department) && (
            <div className="text-xs text-tertiary truncate">
              {node.title}{node.title && node.department && ' · '}{node.department}
            </div>
          )}
          <div className="text-xs text-placeholder">@{node.account}</div>
        </div>

        {/* 操作 */}
        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition">
          {canManage && !isSelf && (
            <>
              <button onClick={() => onEdit(node)} className="text-xs px-2 py-1 rounded hover:bg-hover text-secondary">编辑</button>
              <button onClick={toggleEnabled} className="text-xs px-2 py-1 rounded hover:bg-hover text-secondary">{node.enabled ? '禁用' : '启用'}</button>
              {isSuper && node.role !== 'super_admin' && (
                <button onClick={del} className="text-xs px-2 py-1 rounded hover:bg-red-500/20 text-red-300">删除</button>
              )}
            </>
          )}
        </div>
      </div>

      {/* 子节点 */}
      {hasChildren && !isCollapsed && (
        <div>
          {node.children.map(c => (
            <TreeNode key={c.user_id} node={c} depth={depth + 1} me={me}
              collapsed={collapsed} onToggle={onToggle} onEdit={onEdit} onRefresh={onRefresh}
              isAdmin={isAdmin} isSuper={isSuper} />
          ))}
        </div>
      )}
    </div>
  )
}

function isInMySubtree(node: UserTreeNode, myId: number): boolean {
  if (node.user_id === myId) return true
  return node.children.some(c => isInMySubtree(c, myId))
}

// ========== 扁平表 ==========
function FlatTable({ users, me, isAdmin, isSuper, onEdit, onRefresh }: {
  users: UserTreeNode[]; me: User; isAdmin: boolean; isSuper: boolean
  onEdit: (u: User) => void; onRefresh: () => void
}) {
  const flat: User[] = []
  const walk = (nodes: UserTreeNode[]) => nodes.forEach(n => {
    const { children, ...rest } = n
    flat.push(rest as User); walk(children)
  })
  walk(users)

  return (
    <div className="bg-card border border rounded-xl overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="bg-card text-tertiary text-xs uppercase tracking-wider">
          <tr>
            <th className="px-4 py-3 text-left">用户</th>
            <th className="px-4 py-3 text-left">部门 / 职位</th>
            <th className="px-4 py-3 text-left">账号/邮箱</th>
            <th className="px-4 py-3 text-left">角色</th>
            <th className="px-4 py-3 text-left">上级</th>
            <th className="px-4 py-3 text-left">状态</th>
            {isAdmin && <th className="px-4 py-3 text-left">操作</th>}
          </tr>
        </thead>
        <tbody>
          {flat.map(u => {
            const isSelf = u.user_id === me.user_id
            const mgr = u.manager_id ? flat.find(x => x.user_id === u.manager_id) : null
            return (
              <tr key={u.user_id} className={`border-t border hover:bg-card ${isSelf ? 'bg-purple-500/10' : ''}`}>
                <td className="px-4 py-2.5">
                  <div className="flex items-center gap-2.5">
                    <UserAvatar u={u} size={32} />
                    <div className="min-w-0">
                      <div className="font-medium flex items-center gap-1.5">
                        {u.username}
                        {isSelf && <span className="text-[10px] px-1 py-0.5 bg-purple-500/40 text-purple-100 rounded">我</span>}
                      </div>
                    </div>
                  </div>
                </td>
                <td className="px-4 py-2.5 text-tertiary text-xs">
                  {u.department && <div>{u.department}</div>}
                  {u.title && <div className="text-placeholder">{u.title}</div>}
                </td>
                <td className="px-4 py-2.5">
                  <div className="text-secondary text-xs">@{u.account}</div>
                  <div className="text-placeholder text-xs">{u.email}</div>
                </td>
                <td className="px-4 py-2.5"><RoleBadge role={u.role} /></td>
                <td className="px-4 py-2.5 text-tertiary text-xs">{mgr ? mgr.username : '-'}</td>
                <td className="px-4 py-2.5">
                  <span className={`inline-flex items-center gap-1.5 text-xs ${u.enabled ? 'text-green-300' : 'text-gray-400'}`}>
                    <span className={`w-1.5 h-1.5 rounded-full ${u.enabled ? 'bg-green-400' : 'bg-gray-500'}`} />
                    {u.enabled ? '启用' : '禁用'}
                  </span>
                </td>
                {isAdmin && (
                  <td className="px-4 py-2.5">
                    <div className="flex gap-1">
                      {!isSelf && (isSuper || u.role !== 'super_admin') && (
                        <>
                          <button onClick={() => onEdit(u)} className="text-xs px-2 py-1 rounded hover:bg-hover text-secondary">编辑</button>
                          <button onClick={async () => {
                            try { await userApi.setEnabled(u.user_id, !u.enabled); onRefresh() } catch {}
                          }} className="text-xs px-2 py-1 rounded hover:bg-hover text-secondary">{u.enabled ? '禁用' : '启用'}</button>
                          {isSuper && u.role !== 'super_admin' && (
                            <button onClick={async () => {
                              if (!confirm(`删除 ${u.username}?`)) return
                              try { await userApi.remove(u.user_id); toast.success('已删除'); onRefresh() } catch {}
                            }} className="text-xs px-2 py-1 rounded hover:bg-red-500/20 text-red-300">删除</button>
                          )}
                        </>
                      )}
                    </div>
                  </td>
                )}
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}

// ========== 编辑/创建弹窗 ==========
function UserEditModal({ mode, user, onClose, onSaved, isSuper }: {
  mode: 'create' | 'edit'; user?: User; onClose: () => void; onSaved: () => void; isSuper: boolean
}) {
  const [f, setF] = useState({
    username: user?.username || '',
    account: user?.account || '',
    email: user?.email || '',
    password: mode === 'create' ? 'abc123' : '',
    role: (user?.role as 'admin' | 'user') || 'user',
    manager_id: user?.manager_id ?? null as number | null,
    department: user?.department || '',
    title: user?.title || '',
    enabled: user?.enabled ?? true,
  })
  const [candidates, setCandidates] = useState<Array<User & { depth?: number }>>([])
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    userApi.flat().then(setCandidates).catch(() => {})
  }, [])

  const set = <K extends keyof typeof f>(k: K, v: any) => setF(p => ({ ...p, [k]: v }))

  const save = async () => {
    if (!f.username || !f.account || !f.email) { toast.error('请填写必填字段'); return }
    if (mode === 'create' && f.password.length < 6) { toast.error('密码至少6位'); return }
    setSaving(true)
    try {
      if (mode === 'create') {
        await userApi.create({
          username: f.username, account: f.account, email: f.email, password: f.password,
          role: isSuper ? f.role : 'user',
          manager_id: f.manager_id || null,
          department: f.department, title: f.title,
        })
        toast.success('用户已创建')
      } else if (user) {
        const payload: UserUpdateIn = {
          username: f.username, email: f.email,
          department: f.department, title: f.title,
          manager_id: f.manager_id,
          enabled: f.enabled,
        }
        if (isSuper) payload.role = f.role
        if (f.password) payload.password = f.password
        await userApi.update(user.user_id, payload)
        toast.success('已更新')
      }
      onSaved()
    } finally { setSaving(false) }
  }

  // 过滤掉自己和自己的子树（避免环路）
  const managerOptions = useMemo(() => {
    if (mode === 'edit' && user) {
      const forbidden = new Set<number>([user.user_id])
      // 自己的子树也不能选
      const walk = (id: number) => {
        candidates.filter(c => c.manager_id === id).forEach(c => { forbidden.add(c.user_id); walk(c.user_id) })
      }
      walk(user.user_id)
      return candidates.filter(c => !forbidden.has(c.user_id) && c.role !== 'user')
    }
    return candidates.filter(c => c.role !== 'user')
  }, [candidates, mode, user])

  return (
    <Modal isOpen={true} onClose={onClose} title={mode === 'create' ? '创建用户' : `编辑用户: ${user?.username}`} width="max-w-lg">
      <div className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <Field label="用户名 *">
            <Input value={f.username} onChange={e => set('username', e.target.value)} />
          </Field>
          <Field label="账号 *">
            <Input value={f.account} onChange={e => set('account', e.target.value)} disabled={mode === 'edit'} />
          </Field>
        </div>
        <Field label="邮箱 *">
          <Input type="email" value={f.email} onChange={e => set('email', e.target.value)} />
        </Field>
        <Field label={mode === 'create' ? '初始密码' : '新密码（留空不改）'}>
          <Input type="password" value={f.password} onChange={e => set('password', e.target.value)} placeholder={mode === 'create' ? '至少6位' : '留空则不修改'} />
        </Field>

        <div className="grid grid-cols-2 gap-3">
          {isSuper && (
            <Field label="角色">
              <select value={f.role} onChange={e => set('role', e.target.value as any)}
                className="w-full px-3 py-2 rounded-lg bg-card border border text-sm">
                <option value="user">成员</option>
                <option value="admin">管理员</option>
              </select>
            </Field>
          )}
          <Field label="直属上级">
            <select value={f.manager_id ?? ''} onChange={e => set('manager_id', e.target.value ? Number(e.target.value) : null)}
              className="w-full px-3 py-2 rounded-lg bg-card border border text-sm">
              <option value="">无上级（根节点）</option>
              {managerOptions.map(c => (
                <option key={c.user_id} value={c.user_id}>
                  {c.username} (@{c.account}){c.title ? ` - ${c.title}` : ''}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <Field label="部门">
            <Input value={f.department} onChange={e => set('department', e.target.value)} placeholder="如：研发部" />
          </Field>
          <Field label="职位">
            <Input value={f.title} onChange={e => set('title', e.target.value)} placeholder="如：工程师" />
          </Field>
        </div>

        {mode === 'edit' && (
          <label className="flex items-center gap-2 text-sm text-secondary cursor-pointer">
            <input type="checkbox" checked={f.enabled} onChange={e => set('enabled', e.target.checked)} />
            账号启用（禁用后该用户无法登录）
          </label>
        )}
      </div>
      <div className="flex justify-end gap-3 mt-5 pt-4 border-t border">
        <button onClick={onClose} className="px-4 py-2 rounded-lg bg-hover hover:bg-active text-sm">取消</button>
        <button onClick={save} disabled={saving}
          className="px-5 py-2 rounded-lg bg-gradient-to-r from-brand to-brand-700 text-sm font-medium disabled:opacity-50">
          {saving ? '保存中...' : (mode === 'create' ? '创建' : '保存')}
        </button>
      </div>
    </Modal>
  )
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <div>
    <label className="block text-xs text-tertiary mb-1.5 font-medium">{label}</label>
    {children}
  </div>
}
