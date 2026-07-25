import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import { authApi, User } from '@/api'
import { useAuthStore } from '@/store/auth'

type EditMode = 'basic' | 'email' | 'password'

export default function Me() {
  const user = useAuthStore(s => s.user)
  const updateUser = useAuthStore(s => s.updateUser)
  const [edit, setEdit] = useState<EditMode | null>(null)
  const [editingAvatar, setEditingAvatar] = useState(false)

  if (!user) return <p className="text-tertiary">加载中...</p>

  const roleLabel: Record<string, string> = {
    super_admin: '超级管理员', admin: '管理员', user: '普通用户',
  }
  const roleColor: Record<string, string> = {
    super_admin: 'from-purple-500 to-pink-500',
    admin: 'from-blue-500 to-cyan-500',
    user: 'from-slate-500 to-slate-400',
  }

  const joinDate = user.created_at ? new Date(user.created_at).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }) : '-'
  const birthday = user.birthday ? new Date(user.birthday).toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric' }) : ''

  // 用户首字母（无头像时用）
  const initial = (user.username || user.account || 'U').slice(0, 1).toUpperCase()

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold">⚙️ 个人中心</h1>
        <p className="text-tertiary text-sm mt-1">管理你的个人资料、账号安全与偏好设置</p>
      </div>

      {/* === 顶部资料卡片（带封面）=== */}
      <div className="relative bg-card border border rounded-2xl overflow-hidden">
        {/* 封面渐变 */}
        <div className="h-32 bg-gradient-to-r from-purple-600/40 via-fuchsia-500/30 to-cyan-500/40 relative">
          <div className="absolute inset-0" style={{ backgroundImage: 'radial-gradient(circle at 20% 50%, rgba(139,92,246,0.3) 0%, transparent 50%), radial-gradient(circle at 80% 50%, rgba(6,182,212,0.3) 0%, transparent 50%)' }} />
        </div>
        <div className="px-6 pb-6 -mt-12 relative">
          <div className="flex items-end gap-4 flex-wrap">
            {/* 头像 + 悬浮编辑 */}
            <div className="relative group">
              <div className="w-24 h-24 rounded-2xl overflow-hidden bg-gradient-to-br from-purple-500 to-cyan-500 flex items-center justify-center text-3xl font-bold text-primary shadow-md shadow-purple-500/20 ring-4 ring-slate-900">
                {user.avatar_url
                  ? <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
                  : initial}
              </div>
              <button
                onClick={() => setEditingAvatar(true)}
                className="absolute inset-0 rounded-2xl bg-black/50 opacity-0 group-hover:opacity-100 transition flex items-center justify-center text-xs text-primary font-medium cursor-pointer"
              >
                📷 更换头像
              </button>
            </div>
            <div className="flex-1 min-w-0 pb-1">
              <div className="flex items-center gap-2 flex-wrap">
                <h2 className="text-2xl font-bold truncate">{user.username || user.account}</h2>
                <span className={`px-2 py-0.5 rounded-full text-[11px] font-medium text-primary bg-gradient-to-r ${roleColor[user.role] || roleColor.user}`}>
                  {roleLabel[user.role] || user.role}
                </span>
              </div>
              {(user.title || user.company) ? (
                <div className="text-secondary text-sm mt-0.5 truncate">
                  {user.title}{user.title && user.company && ' · '}{user.company}{user.department && ` · ${user.department}`}
                </div>
              ) : null}
              <div className="flex items-center gap-3 mt-2 text-xs text-tertiary flex-wrap gap-y-1">
                <span>🔗 @{user.account}</span>
                <span>📧 {user.email}</span>
                {user.location && <span>📍 {user.location}</span>}
                {user.birthday && <span>🎂 {birthday}</span>}
                <span>📅 加入于 {joinDate}</span>
              </div>
            </div>
            <button
              onClick={() => setEdit('basic')}
              className="px-4 py-2 rounded-lg bg-hover hover:bg-active border border text-sm transition"
            >
              ✏️ 编辑资料
            </button>
          </div>

          {/* 个人简介 */}
          {user.bio ? (
            <div className="mt-4 pt-4 border-t border">
              <p className="text-sm text-primary whitespace-pre-wrap leading-relaxed">{user.bio}</p>
            </div>
          ) : (
            <button
              onClick={() => setEdit('basic')}
              className="mt-4 text-sm text-placeholder hover:text-tertiary transition italic"
            >
              + 添加个人简介，让别人更了解你
            </button>
          )}
        </div>
      </div>

      {/* === 信息栅格 === */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* 基本信息卡片 */}
        <InfoCard title="基本信息" icon="👤">
          <InfoRow icon="💼" label="职位" value={user.title} onEdit={() => setEdit('basic')} />
          <InfoRow icon="🏢" label="公司/组织" value={user.company} onEdit={() => setEdit('basic')} />
          <InfoRow icon="🗂️" label="部门" value={user.department} onEdit={() => setEdit('basic')} />
          <InfoRow icon="📍" label="所在地" value={user.location} onEdit={() => setEdit('basic')} />
          <InfoRow icon="🎂" label="生日" value={birthday} onEdit={() => setEdit('basic')} />
        </InfoCard>

        {/* 联系方式卡片 */}
        <InfoCard title="联系方式" icon="📇">
          <InfoRow icon="📧" label="邮箱" value={user.email} onEdit={() => setEdit('email')} />
          <InfoRow icon="📱" label="电话" value={user.phone} onEdit={() => setEdit('basic')} />
          <InfoRow icon="🌐" label="个人网站"
            value={user.website ? (() => {
              const display = user.website.replace(/^https?:\/\//, '')
              return <a href={user.website!.startsWith('http') ? user.website : `https://${user.website}`} target="_blank" rel="noreferrer" className="text-cyan-300 hover:underline">{display}</a>
            })() : ''}
            onEdit={() => setEdit('basic')} isLink />
        </InfoCard>

        {/* 账号信息卡片 */}
        <InfoCard title="账号信息" icon="🔐">
          <InfoRow icon="🆔" label="账号 ID" value={`#${user.user_id}`} />
          <InfoRow icon="🔑" label="登录账号" value={user.account} />
          <InfoRow icon="🛡️" label="角色" value={roleLabel[user.role] || user.role} />
          <InfoRow icon="📅" label="注册时间" value={joinDate} />
        </InfoCard>

        {/* 安全操作卡片 */}
        <InfoCard title="安全设置" icon="🛡️">
          <div className="p-4 space-y-3">
            <button
              onClick={() => setEdit('password')}
              className="w-full flex items-center justify-between p-3 rounded-lg bg-card hover:bg-hover border border transition group"
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">🔒</span>
                <div className="text-left">
                  <div className="text-sm font-medium">修改密码</div>
                  <div className="text-xs text-placeholder">定期更换密码以保护账号安全</div>
                </div>
              </div>
              <span className="text-placeholder group-hover:text-tertiary transition">→</span>
            </button>
            <button
              onClick={() => setEditingAvatar(true)}
              className="w-full flex items-center justify-between p-3 rounded-lg bg-card hover:bg-hover border border transition group"
            >
              <div className="flex items-center gap-3">
                <span className="text-xl">🖼️</span>
                <div className="text-left">
                  <div className="text-sm font-medium">更换头像</div>
                  <div className="text-xs text-placeholder">上传本地图片或填写 URL</div>
                </div>
              </div>
              <span className="text-placeholder group-hover:text-tertiary transition">→</span>
            </button>
          </div>
        </InfoCard>
      </div>

      {edit === 'basic' && (
        <EditProfileModal user={user} onClose={() => setEdit(null)} onSaved={(u) => { updateUser(u); setEdit(null); toast.success('资料已更新') }} />
      )}
      {edit === 'email' && (
        <EditEmailModal user={user} onClose={() => setEdit(null)} onSaved={(u) => { updateUser(u); setEdit(null); toast.success('邮箱已更新') }} />
      )}
      {edit === 'password' && (
        <EditPasswordModal onClose={() => setEdit(null)} />
      )}
      {editingAvatar && (
        <EditAvatarModal user={user} onClose={() => setEditingAvatar(false)} onSaved={(u) => { updateUser(u); setEditingAvatar(false); toast.success('头像已更新') }} />
      )}
    </div>
  )
}

// ========== 小组件 ==========

function InfoCard({ title, icon, children }: { title: string; icon: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border flex items-center gap-2">
        <span>{icon}</span>
        <h3 className="text-sm font-medium text-primary">{title}</h3>
      </div>
      <div className="divide-y divide-white/5">{children}</div>
    </div>
  )
}

function InfoRow({ icon, label, value, onEdit, isLink }: { icon: string; label: string; value: React.ReactNode; onEdit?: () => void; isLink?: boolean }) {
  const isEmpty = value === '' || value === null || value === undefined
  return (
    <div className="px-4 py-3 flex items-center gap-3 group">
      <span className="text-base opacity-70">{icon}</span>
      <div className="flex-1 min-w-0">
        <div className="text-[11px] text-placeholder uppercase tracking-wider">{label}</div>
        <div className={`text-sm truncate ${isEmpty ? 'text-placeholder italic' : isLink ? '' : 'text-primary'}`}>
          {isEmpty ? '未设置' : value}
        </div>
      </div>
      {onEdit && (
        <button
          onClick={onEdit}
          className="opacity-0 group-hover:opacity-100 text-xs px-2 py-1 rounded bg-hover hover:bg-active transition"
        >
          修改
        </button>
      )}
    </div>
  )
}

// ========== Modal 基础 ==========

function ModalShell({ title, onClose, children, maxWidth = 'max-w-md' }: { title: string; onClose: () => void; children: React.ReactNode; maxWidth?: string }) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60  p-4" onClick={onClose}>
      <div className={`bg-card border border rounded-2xl w-full ${maxWidth} p-6 max-h-[90vh] overflow-y-auto`} onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-bold">{title}</h3>
          <button onClick={onClose} className="text-tertiary hover:text-primary text-xl leading-none w-8 h-8 flex items-center justify-center rounded-lg hover:bg-hover transition">×</button>
        </div>
        {children}
      </div>
    </div>
  )
}

function Field({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) {
  return <div className="mb-3">
    <label className="block text-xs text-tertiary mb-1.5 font-medium">{label}</label>
    {children}
    {hint && <div className="text-[11px] text-placeholder mt-1">{hint}</div>}
  </div>
}

const inputCls = "w-full px-3 py-2 rounded-lg bg-card border border focus:outline-none focus:border-cyan-400/50 focus:bg-hover text-sm transition"
const textareaCls = inputCls + " resize-none min-h-[80px]"

function FooterBtns({ onClose, onSave, saving = false, saveText = '保存' }: { onClose: () => void; onSave: () => void; saving?: boolean; saveText?: string }) {
  return (
    <div className="flex justify-end gap-3 mt-5 pt-4 border-t border">
      <button onClick={onClose} className="px-4 py-2 rounded-lg bg-hover hover:bg-active text-sm transition">取消</button>
      <button onClick={onSave} disabled={saving}
        className="px-5 py-2 rounded-lg bg-gradient-to-r from-brand to-brand-700 text-sm font-medium hover:opacity-90 disabled:opacity-50 transition">
        {saving ? '保存中...' : saveText}
      </button>
    </div>
  )
}

// ========== 编辑：基本资料 ==========

function EditProfileModal({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: (u: User) => void }) {
  const [form, setForm] = useState({
    username: user.username || '',
    title: user.title || '',
    company: user.company || '',
    department: user.department || '',
    location: user.location || '',
    phone: user.phone || '',
    website: user.website || '',
    bio: user.bio || '',
    birthday: user.birthday ? user.birthday.slice(0, 10) : '',
  })
  const [saving, setSaving] = useState(false)

  const set = <K extends keyof typeof form>(k: K, v: string) => setForm(f => ({ ...f, [k]: v }))

  const save = async () => {
    if (!form.username.trim()) { toast.error('用户名不能为空'); return }
    if (form.website && !/^https?:\/\//.test(form.website) && form.website.trim()) {
      // 自动补 https://
      form.website = 'https://' + form.website.trim()
    }
    setSaving(true)
    try {
      const u = await authApi.updateMe({
        username: form.username.trim(),
        title: form.title.trim(),
        company: form.company.trim(),
        department: form.department.trim(),
        location: form.location.trim(),
        phone: form.phone.trim(),
        website: form.website.trim(),
        bio: form.bio,
        birthday: form.birthday || null,
      })
      onSaved(u)
    } finally { setSaving(false) }
  }

  return (
    <ModalShell title="编辑个人资料" onClose={onClose} maxWidth="max-w-lg">
      <Field label="昵称 / 用户名">
        <input value={form.username} onChange={e => set('username', e.target.value)} className={inputCls} maxLength={64} autoFocus />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="职位 / 头衔">
          <input value={form.title} onChange={e => set('title', e.target.value)} className={inputCls} placeholder="如：产品经理" maxLength={64} />
        </Field>
        <Field label="公司 / 组织">
          <input value={form.company} onChange={e => set('company', e.target.value)} className={inputCls} placeholder="如：XX科技" maxLength={128} />
        </Field>
      </div>
      <Field label="所属部门">
        <input value={form.department} onChange={e => set('department', e.target.value)} className={inputCls} placeholder="如：研发部" maxLength={64} />
      </Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="所在地">
          <input value={form.location} onChange={e => set('location', e.target.value)} className={inputCls} placeholder="如：北京" maxLength={64} />
        </Field>
        <Field label="生日">
          <input type="date" value={form.birthday} onChange={e => set('birthday', e.target.value)} className={inputCls} />
        </Field>
      </div>
      <div className="grid grid-cols-2 gap-3">
        <Field label="联系电话">
          <input value={form.phone} onChange={e => set('phone', e.target.value)} className={inputCls} maxLength={32} />
        </Field>
        <Field label="个人网站">
          <input value={form.website} onChange={e => set('website', e.target.value)} className={inputCls} placeholder="example.com" maxLength={256} />
        </Field>
      </div>
      <Field label="个人简介" hint="简短介绍你自己，支持换行">
        <textarea value={form.bio} onChange={e => set('bio', e.target.value)} className={textareaCls} maxLength={500} placeholder="写点什么介绍自己..." />
      </Field>
      <FooterBtns onClose={onClose} onSave={save} saving={saving} />
    </ModalShell>
  )
}

// ========== 编辑：邮箱 ==========

function EditEmailModal({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: (u: User) => void }) {
  const [email, setEmail] = useState(user.email || '')
  const [saving, setSaving] = useState(false)
  const save = async () => {
    if (!email.trim() || !email.includes('@')) { toast.error('请输入有效邮箱'); return }
    setSaving(true)
    try {
      const u = await authApi.updateMe({ email: email.trim() })
      onSaved(u)
    } finally { setSaving(false) }
  }
  return (
    <ModalShell title="修改邮箱" onClose={onClose}>
      <Field label="邮箱地址">
        <input type="email" value={email} onChange={e => setEmail(e.target.value)} className={inputCls} autoFocus />
      </Field>
      <FooterBtns onClose={onClose} onSave={save} saving={saving} />
    </ModalShell>
  )
}

// ========== 编辑：密码 ==========

function EditPasswordModal({ onClose }: { onClose: () => void }) {
  const [oldPw, setOldPw] = useState('')
  const [newPw, setNewPw] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)
  const save = async () => {
    if (!oldPw || !newPw) { toast.error('请填写完整'); return }
    if (newPw !== confirm) { toast.error('两次密码不一致'); return }
    if (newPw.length < 6) { toast.error('密码至少6位'); return }
    if (newPw === oldPw) { toast.error('新密码不能与旧密码相同'); return }
    setSaving(true)
    try {
      await authApi.updateMe({ old_password: oldPw, new_password: newPw })
      toast.success('密码已修改'); onClose()
    } finally { setSaving(false) }
  }
  return (
    <ModalShell title="修改密码" onClose={onClose}>
      <Field label="当前密码">
        <input type="password" value={oldPw} onChange={e => setOldPw(e.target.value)} className={inputCls} autoFocus />
      </Field>
      <Field label="新密码" hint="至少 6 位">
        <input type="password" value={newPw} onChange={e => setNewPw(e.target.value)} className={inputCls} />
      </Field>
      <Field label="确认新密码">
        <input type="password" value={confirm} onChange={e => setConfirm(e.target.value)} className={inputCls} />
      </Field>
      <FooterBtns onClose={onClose} onSave={save} saving={saving} saveText="修改密码" />
    </ModalShell>
  )
}

// ========== 编辑：头像 ==========

function EditAvatarModal({ user, onClose, onSaved }: { user: User; onClose: () => void; onSaved: (u: User) => void }) {
  const [url, setUrl] = useState((user.avatar_url || '').startsWith('data:') ? '' : (user.avatar_url || ''))
  const [localPreview, setLocalPreview] = useState<string>('')
  const [pendingFile, setPendingFile] = useState<File | null>(null)
  const [saving, setSaving] = useState(false)
  const fileRef = useRef<HTMLInputElement>(null)

  const MAX_SIZE = 2 * 1024 * 1024

  const onFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0]
    if (!f) return
    if (!f.type.startsWith('image/')) { toast.error('请选择图片文件'); return }
    if (f.size > MAX_SIZE) { toast.error('图片不能超过 2MB'); return }
    setPendingFile(f); setUrl('')
    const reader = new FileReader()
    reader.onload = () => setLocalPreview(reader.result as string)
    reader.readAsDataURL(f)
  }

  const clearLocal = () => { setPendingFile(null); setLocalPreview(''); if (fileRef.current) fileRef.current.value = '' }

  const save = async () => {
    setSaving(true)
    try {
      let u: User
      if (pendingFile) {
        u = await authApi.uploadAvatar(pendingFile)
        toast.success('头像已上传')
      } else if (url.trim() || url === '') {
        // url==='' 表示清除头像
        u = await authApi.updateMe({ avatar_url: url.trim() })
        toast.success('头像已更新')
      } else {
        return
      }
      onSaved(u)
    } finally { setSaving(false) }
  }

  const displaySrc = localPreview || url
  const canSave = pendingFile || url.trim() !== (user.avatar_url || '') || (localPreview && pendingFile)

  return (
    <ModalShell title="更换头像" onClose={onClose}>
      <div className="flex items-center gap-5 mb-4">
        <div className="w-24 h-24 rounded-2xl overflow-hidden bg-hover flex items-center justify-center shrink-0 border border shadow-lg">
          {displaySrc
            ? <img src={displaySrc} alt="preview" className="w-full h-full object-cover" />
            : <span className="text-4xl text-placeholder">👤</span>}
        </div>
        <div className="flex-1 space-y-2 min-w-0">
          <button onClick={() => fileRef.current?.click()}
            className="w-full px-3 py-2 rounded-lg bg-gradient-to-r from-brand to-brand-700 text-sm hover:opacity-90 transition">
            📁 从本地选择图片
          </button>
          <button onClick={() => { setUrl(''); clearLocal() }}
            disabled={!displaySrc && !user.avatar_url}
            className="w-full px-3 py-2 rounded-lg bg-hover hover:bg-active text-sm disabled:opacity-40 disabled:cursor-not-allowed transition">
            🗑️ 清除头像（使用默认）
          </button>
          <input ref={fileRef} type="file" accept="image/*" className="hidden" onChange={onFile} />
          {pendingFile && <div className="text-xs text-tertiary truncate">📎 {pendingFile.name} ({(pendingFile.size / 1024).toFixed(0)} KB)</div>}
        </div>
      </div>

      <Field label="或填写头像 URL">
        <input
          value={pendingFile ? '' : url}
          onChange={e => { setUrl(e.target.value); clearLocal() }}
          placeholder="https://..."
          className={inputCls}
          disabled={!!pendingFile}
        />
      </Field>

      <div className="text-[11px] text-placeholder px-1">
        支持 PNG / JPG / GIF / WebP，最大 2MB
      </div>

      <FooterBtns onClose={onClose} onSave={save} saving={saving} />
    </ModalShell>
  )
}
