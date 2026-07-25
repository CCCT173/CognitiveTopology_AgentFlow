import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/store/auth'
import { useMetaStore } from '@/store/meta'
import { userApi } from '@/api'

export default function Login() {
  const nav = useNavigate()
  const token = useAuthStore(s => s.token)
  useEffect(() => { if (token) nav('/', { replace: true }) }, [token])
  useEffect(() => { document.title = '登录 · AgentFlow' }, [])
  const [mode, setMode] = useState<'login' | 'register'>('login')
  const [loading, setLoading] = useState(false)
  const [form, setForm] = useState({ username: '', account: '', email: '', password: '', bind_admin_id: '' as string | number | '' })
  const [admins, setAdmins] = useState<{user_id:number;username:string;account:string;role:string}[]>([])
  const login = useAuthStore(s => s.login)
  const register = useAuthStore(s => s.register)
  const loadMeta = useMetaStore(s => s.load)

  useEffect(() => {
    if (mode === 'register' && admins.length === 0) {
      userApi.admins().then(setAdmins).catch(() => {})
    }
  }, [mode])

  const submit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    if (!form.account || !form.password) { toast.error('请填写账号和密码'); return }
    if (mode === 'register' && (!form.username || !form.email)) { toast.error('请填写用户名和邮箱'); return }
    setLoading(true)
    try {
      if (mode === 'login') {
        await login(form.account, form.password)
      } else {
        const bindId = form.bind_admin_id === '' ? undefined : Number(form.bind_admin_id)
        await register({
          username: form.username, account: form.account, email: form.email, password: form.password,
          bind_admin_id: bindId,
        })
      }
      await loadMeta()
      toast.success(mode === 'login' ? '登录成功' : '注册成功')
      nav('/')
    } catch (e: any) {
      // 错误已被 http 拦截器 toast
    } finally { setLoading(false) }
  }

  return (
    <div className="min-h-screen flex bg-app">
      {/* 左侧品牌区 */}
      <div className="hidden lg:flex flex-1 items-center justify-center bg-gradient-to-br from-brand-500 via-brand-600 to-brand-700 relative overflow-hidden">
        <div className="absolute inset-0 opacity-10">
          <div className="absolute top-20 left-20 w-72 h-72 rounded-full bg-active blur-3xl" />
          <div className="absolute bottom-20 right-20 w-96 h-96 rounded-full bg-hover blur-3xl" />
        </div>
        <div className="relative z-10 text-primary max-w-md">
          <div className="w-16 h-16 rounded-2xl bg-active backdrop-blur flex items-center justify-center text-3xl font-bold mb-8">A</div>
          <h1 className="text-4xl font-bold mb-4">AgentFlow</h1>
          <p className="text-lg text-primary leading-relaxed">
            多智能体 + RAG 知识库平台。
            <br />构建、编排、部署 AI 工作流。
          </p>
          <div className="mt-8 space-y-3">
            {['Agent 编排与管理', '工作流可视化构建', '知识库与 RAG', '团队协作与共享'].map(f => (
              <div key={f} className="flex items-center gap-2 text-secondary">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                <span>{f}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 右侧登录表单 */}
      <div className="w-full lg:w-[480px] flex items-center justify-center p-8">
        <div className="w-full max-w-sm animate-fadeIn">
          <div className="mb-8">
            <h2 className="text-2xl font-bold text-primary">{mode === 'login' ? '欢迎回来' : '创建账号'}</h2>
            <p className="text-sm text-tertiary mt-1">
              {mode === 'login' ? '登录到你的 AgentFlow 账户' : '注册一个新的 AgentFlow 账户'}
            </p>
          </div>

          <div className="flex gap-1 mb-6 bg-subtle rounded-lg p-1">
            <button onClick={() => setMode('login')}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${mode === 'login' ? 'bg-card shadow-sm text-primary' : 'text-tertiary hover:text-primary'}`}>
              登录
            </button>
            <button onClick={() => setMode('register')}
              className={`flex-1 py-2 rounded-md text-sm font-medium transition-all ${mode === 'register' ? 'bg-card shadow-sm text-primary' : 'text-tertiary hover:text-primary'}`}>
              注册
            </button>
          </div>

          <form onSubmit={submit} className="space-y-4">
            {mode === 'register' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1.5">用户名</label>
                  <input className="input" value={form.username} onChange={e => setForm({...form, username: e.target.value})} placeholder="显示名称" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1.5">邮箱</label>
                  <input type="email" className="input" value={form.email} onChange={e => setForm({...form, email: e.target.value})} placeholder="you@example.com" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-secondary mb-1.5">绑定管理员 <span className="text-placeholder text-xs">(可选)</span></label>
                  <select value={form.bind_admin_id} onChange={e => setForm({...form, bind_admin_id: e.target.value})}
                    className="input">
                    <option value="">不绑定 (稍后由管理员分配)</option>
                    {admins.map(a => (
                      <option key={a.user_id} value={a.user_id}>
                        {a.username} (@{a.account}) - {a.role === 'super_admin' ? '超级管理员' : '管理员'}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}
            <div>
              <label className="block text-sm font-medium text-secondary mb-1.5">账号</label>
              <input className="input" value={form.account} onChange={e => setForm({...form, account: e.target.value})} placeholder="登录账号" />
            </div>
            <div>
              <label className="block text-sm font-medium text-secondary mb-1.5">密码</label>
              <input type="password" className="input" value={form.password} onChange={e => setForm({...form, password: e.target.value})} placeholder="至少 6 位" />
            </div>

            <button type="submit" disabled={loading}
              className="btn btn-primary w-full h-10 mt-2">
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" opacity="0.25"/><path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" opacity="0.75"/></svg>
                  {mode === 'login' ? '登录中...' : '注册中...'}
                </span>
              ) : (mode === 'login' ? '登录' : '注册')}
            </button>
          </form>

          {mode === 'login' && (
            <p className="text-placeholder text-xs text-center mt-8">默认管理员账号: admin / admin123</p>
          )}
        </div>
      </div>
    </div>
  )
}
