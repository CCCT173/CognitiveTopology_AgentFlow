import { useEffect, useRef, Suspense, lazy } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import CommandPalette from './components/CommandPalette'
import Login from './pages/Login'
import Home from './pages/Home'
import NotFound from './pages/NotFound'
import { useAuthStore } from './store/auth'
import { useMetaStore } from './store/meta'
import { authApi } from '@/api'

// 懒加载大页面，拆包优化首屏
const Agents = lazy(() => import('./pages/Agents'))
const AgentDetail = lazy(() => import('./pages/AgentDetail'))
const Rag = lazy(() => import('./pages/Rag'))
const KBDetail = lazy(() => import('./pages/KBDetail'))
const Workflows = lazy(() => import('./pages/Workflows'))
const WFDetail = lazy(() => import('./pages/WFDetail'))
const Groups = lazy(() => import('./pages/Groups'))
const GroupDetail = lazy(() => import('./pages/GroupDetail'))
const Users = lazy(() => import('./pages/Users'))
const Me = lazy(() => import('./pages/Me'))
const Skills = lazy(() => import('./pages/Skills'))
const Monitor = lazy(() => import('./pages/Monitor'))
const DbConnections = lazy(() => import('./pages/DbConnections'))
const Settings = lazy(() => import('./pages/Settings'))

const PageLoader = () => (
  <div className="flex items-center justify-center py-20 text-placeholder text-sm">
    <div className="w-5 h-5 border-2 border border-t-cyan-400 rounded-full animate-spin mr-3" />
    加载页面中...
  </div>
)

export default function App() {
  const fetchMe = useAuthStore(s => s.fetchMe)
  const loadMeta = useMetaStore(s => s.load)
  const metaLoaded = useMetaStore(s => s.loaded)
  const token = useAuthStore(s => s.token)
  const pingTimer = useRef<ReturnType<typeof setInterval> | null>(null)

  useEffect(() => {
    fetchMe()
    // 只有登录后才加载 meta (避免登录页因后端重启/未就绪时弹出大量错误 toast)
    if (!metaLoaded && token) loadMeta()
  }, [])

  // 登录后每 45s 心跳一次,更新在线状态
  useEffect(() => {
    if (!token) {
      if (pingTimer.current) { clearInterval(pingTimer.current); pingTimer.current = null }
      return
    }
    pingTimer.current = setInterval(() => { authApi.ping().catch(()=>{}) }, 45000)
    return () => { if (pingTimer.current) clearInterval(pingTimer.current) }
  }, [token])

  return (
    <>
      <CommandPalette />
      <Routes>
        <Route path="/login" element={<Login />} />
      <Route path="/" element={<RequireAuth><Layout /></RequireAuth>}>
        <Route index element={<Home />} />
        <Route path="agents" element={<Suspense fallback={<PageLoader/>}><Agents /></Suspense>} />
        <Route path="agents/:name" element={<Suspense fallback={<PageLoader/>}><AgentDetail /></Suspense>} />
        <Route path="rag" element={<Suspense fallback={<PageLoader/>}><Rag /></Suspense>} />
        <Route path="rag/:id" element={<Suspense fallback={<PageLoader/>}><KBDetail /></Suspense>} />
        <Route path="workflows" element={<Suspense fallback={<PageLoader/>}><Workflows /></Suspense>} />
        <Route path="workflows/:id" element={<Suspense fallback={<PageLoader/>}><WFDetail /></Suspense>} />
        <Route path="skills" element={<Suspense fallback={<PageLoader/>}><Skills /></Suspense>} />
        <Route path="groups" element={<Suspense fallback={<PageLoader/>}><Groups /></Suspense>} />
        <Route path="groups/:id" element={<Suspense fallback={<PageLoader/>}><GroupDetail /></Suspense>} />
        <Route path="admin/users" element={<RequireAuth requireAdmin><Suspense fallback={<PageLoader/>}><Users /></Suspense></RequireAuth>} />
        <Route path="admin/monitor" element={<RequireAuth requireAdmin><Suspense fallback={<PageLoader/>}><Monitor /></Suspense></RequireAuth>} />
        <Route path="admin/db-connections" element={<RequireAuth requireAdmin><Suspense fallback={<PageLoader/>}><DbConnections /></Suspense></RequireAuth>} />
        <Route path="me" element={<Suspense fallback={<PageLoader/>}><Me /></Suspense>} />
        <Route path="settings" element={<Suspense fallback={<PageLoader/>}><Settings /></Suspense>} />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
    </>
  )
}
