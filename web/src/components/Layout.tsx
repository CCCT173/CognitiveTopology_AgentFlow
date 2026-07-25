import { useEffect, useRef, useState } from 'react'
import { Outlet, NavLink, useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'

/* SVG Icons - 干净专业的 icon 集 */
const Icons = {
  home: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>,
  agents: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="4" y="4" width="16" height="16" rx="2" ry="2"/><rect x="9" y="9" width="6" height="6"/><line x1="9" y1="1" x2="9" y2="4"/><line x1="15" y1="1" x2="15" y2="4"/><line x1="9" y1="20" x2="9" y2="23"/><line x1="15" y1="20" x2="15" y2="23"/><line x1="20" y1="9" x2="23" y2="9"/><line x1="20" y1="14" x2="23" y2="14"/><line x1="1" y1="9" x2="4" y2="9"/><line x1="1" y1="14" x2="4" y2="14"/></svg>,
  workflows: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>,
  skills: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m12 2 10 6.5v7L12 22 2 15.5v-7z"/><path d="m12 22v-6.5"/><path d="m22 8.5-10 7L2 8.5"/></svg>,
  rag: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H20v20H6.5a2.5 2.5 0 0 1 0-5H20"/></svg>,
  groups: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  users: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg>,
  monitor: <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>,
  chevron: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="6 9 12 15 18 9"/></svg>,
  settings: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"/></svg>,
  logout: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16 17 21 12 16 7"/><line x1="21" y1="12" x2="9" y2="12"/></svg>,
  collapse: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></svg>,
  expand: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></svg>,
}

const menus = [
  { to: '/', end: true, icon: 'home', label: '首页' },
  { to: '/agents', icon: 'agents', label: 'Agent' },
  { to: '/workflows', icon: 'workflows', label: '工作流' },
  { to: '/skills', icon: 'skills', label: '技能' },
  { to: '/rag', icon: 'rag', label: '知识库' },
  { to: '/groups', icon: 'groups', label: '群组' },
]

function getBreadcrumb(path: string) {
  const map: Record<string, string> = {
    '/': '首页', '/agents': 'Agent 管理', '/workflows': '工作流管理',
    '/skills': '技能管理', '/rag': '知识库', '/groups': '群组',
    '/admin/users': '用户管理', '/admin/monitor': '系统监控', '/admin/db-connections': '数据库连接', '/me': '个人中心',
    '/settings': '系统设置',
  }
  for (const k of Object.keys(map)) {
    if (path === k) return [{ label: map[k], to: k }]
    if (path.startsWith(k + '/') && k !== '/') {
      return [{ label: map[k], to: k }, { label: '详情', to: path }]
    }
  }
  return [{ label: '首页', to: '/' }]
}

export default function Layout() {
  const user = useAuthStore(s => s.user)
  const logout = useAuthStore(s => s.logout)
  const nav = useNavigate()
  const loc = useLocation()
  const [menuOpen, setMenuOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const h = (e: MouseEvent) => { if (menuRef.current && !menuRef.current.contains(e.target as Node)) setMenuOpen(false) }
    if (menuOpen) document.addEventListener('mousedown', h)
    return () => document.removeEventListener('mousedown', h)
  }, [menuOpen])

  const onLogout = () => { setMenuOpen(false); logout(); nav('/login') }
  const isAdmin = user?.role === 'super_admin' || user?.role === 'admin'
  const crumbs = getBreadcrumb(loc.pathname)

  useEffect(() => {
    const label = crumbs.length > 0 ? crumbs[crumbs.length - 1].label : 'AgentFlow'
    document.title = `${label} · AgentFlow`
  }, [loc.pathname])

  const sidebarWidth = collapsed ? 'w-[68px]' : 'w-[240px]'

  return (
    <div className="min-h-screen flex bg-app">
      {/* 侧边栏 */}
      <aside className={`fixed top-0 left-0 bottom-0 z-50 ${sidebarWidth} flex flex-col bg-sidebar border-r border transition-all duration-300`}>
        {/* Logo 区 */}
        <div className="h-14 flex items-center px-4 border-b border gap-2">
          <div className="flex items-center gap-2 font-semibold text-[15px] text-primary truncate">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand to-[#0D52D8] flex items-center justify-center text-white text-sm font-bold shrink-0">
              A
            </div>
            {!collapsed && <span className="truncate">AgentFlow</span>}
          </div>
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="ml-auto w-7 h-7 rounded-md hover:bg-hover flex items-center justify-center text-tertiary hover:text-primary transition shrink-0"
          >
            {collapsed ? Icons.expand : Icons.collapse}
          </button>
        </div>

        {/* 导航菜单 */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {menus.map(m => (
            <NavLink key={m.to} to={m.to} end={m.end}
              className={({ isActive }) => `
                flex items-center gap-2.5 px-3 h-9 rounded-lg text-[13px] font-medium transition-all duration-150
                ${collapsed ? 'justify-center' : ''}
                ${isActive
                  ? 'bg-brand-subtle text-brand'
                  : 'text-secondary hover:text-primary hover:bg-hover'
                }
              `}
              title={collapsed ? m.label : undefined}
            >
              <span className={`w-[18px] h-[18px] flex items-center justify-center shrink-0 ${collapsed ? '' : ''}`}>
                {Icons[m.icon as keyof typeof Icons]}
              </span>
              {!collapsed && <span className="truncate">{m.label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* 管理菜单（底部） */}
        {isAdmin && (
          <div className="p-3 border-t border">
            <div className={`text-[11px] font-medium text-tertiary mb-2 ${collapsed ? 'text-center' : ''}`}>
              {!collapsed && '管理'}
            </div>
            <NavLink to="/admin/users"
              className={({ isActive }) => `
                flex items-center gap-2.5 px-3 h-9 rounded-lg text-[13px] font-medium transition-all duration-150
                ${collapsed ? 'justify-center' : ''}
                ${isActive ? 'bg-brand-subtle text-brand' : 'text-secondary hover:text-primary hover:bg-hover'}
              `}
              title={collapsed ? '用户管理' : undefined}
            >
              <span className="w-[18px] h-[18px] flex items-center justify-center shrink-0">{Icons.users}</span>
              {!collapsed && <span className="truncate">用户管理</span>}
            </NavLink>
            <NavLink to="/admin/monitor"
              className={({ isActive }) => `
                flex items-center gap-2.5 px-3 h-9 rounded-lg text-[13px] font-medium transition-all duration-150
                ${collapsed ? 'justify-center' : ''}
                ${isActive ? 'bg-brand-subtle text-brand' : 'text-secondary hover:text-primary hover:bg-hover'}
              `}
              title={collapsed ? '系统监控' : undefined}
            >
              <span className="w-[18px] h-[18px] flex items-center justify-center shrink-0">{Icons.monitor}</span>
              {!collapsed && <span className="truncate">系统监控</span>}
            </NavLink>
          </div>
        )}
      </aside>

      {/* 主内容区 */}
      <div className={`flex-1 flex flex-col min-w-0 transition-all duration-300 ${collapsed ? 'ml-[68px]' : 'ml-[240px]'}`}>
        {/* 顶部面包屑栏 */}
        <header className="sticky top-0 z-30 h-14 bg-app border-b border flex items-center px-6 gap-3">
          <nav className="flex items-center gap-1.5 text-[13px]">
            {crumbs.map((c, i) => (
              <div key={i} className="flex items-center gap-1.5">
                {i > 0 && <span className="text-placeholder">/</span>}
                {i === crumbs.length - 1 ? (
                  <span className="text-primary font-medium">{c.label}</span>
                ) : (
                  <button onClick={() => nav(c.to)} className="text-tertiary hover:text-primary transition">{c.label}</button>
                )}
              </div>
            ))}
          </nav>

          {/* 右侧用户区 */}
          <div className="ml-auto flex items-center gap-3">
            <div ref={menuRef} className="relative">
              <button
                onClick={() => setMenuOpen(!menuOpen)}
                className="w-8 h-8 rounded-full bg-gradient-to-br from-brand to-[#0D52D8] flex items-center justify-center text-xs font-semibold text-white hover:ring-2 ring-brand/20 transition-all overflow-hidden shrink-0"
              >
                {user?.avatar_url
                  ? <img src={user.avatar_url} alt="" className="w-full h-full object-cover" />
                  : (user?.username || 'U').slice(0, 1).toUpperCase()
                }
              </button>
              {menuOpen && (
                <div className="absolute right-0 top-10 bg-card border border rounded-xl shadow-lg py-1.5 min-w-[200px] z-50 animate-fadeIn">
                  <div className="px-3 py-2.5 border-b border">
                    <div className="font-medium text-primary truncate text-sm">{user?.username || '用户'}</div>
                    <div className="text-xs text-tertiary truncate mt-0.5">{user?.email || user?.account}</div>
                    <div className="text-xs text-placeholder mt-0.5">{roleLabel(user?.role)}</div>
                  </div>
                  <button onClick={() => { setMenuOpen(false); nav('/me') }}
                    className="w-full px-3 py-2 text-left text-[13px] text-secondary hover:bg-hover hover:text-primary flex items-center gap-2 transition">
                    <span className="w-4 h-4">{Icons.settings}</span> 个人中心
                  </button>
                  <button onClick={() => { setMenuOpen(false); nav('/settings') }}
                    className="w-full px-3 py-2 text-left text-[13px] text-secondary hover:bg-hover hover:text-primary flex items-center gap-2 transition">
                    <span className="w-4 h-4">{Icons.settings}</span> 系统设置
                  </button>
                  <button onClick={onLogout}
                    className="w-full px-3 py-2 text-left text-[13px] text-danger hover:bg-red-50 flex items-center gap-2 transition">
                    <span className="w-4 h-4">{Icons.logout}</span> 退出登录
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>

        {/* 页面内容 */}
        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}

function roleLabel(role?: string) {
  return { super_admin: '超级管理员', admin: '管理员', user: '普通用户' }[role || 'user'] || role
}
