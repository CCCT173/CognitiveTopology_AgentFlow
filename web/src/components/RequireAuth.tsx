import { Navigate } from 'react-router-dom'
import { useAuthStore } from '@/store/auth'

interface Props {
  children: React.ReactNode
  requireAdmin?: boolean
}

export default function RequireAuth({ children, requireAdmin }: Props) {
  const token = useAuthStore(s => s.token)
  const user = useAuthStore(s => s.user)
  if (!token) return <Navigate to="/login" replace />
  if (requireAdmin) {
    const isAdmin = user?.role === 'super_admin' || user?.role === 'admin'
    if (!isAdmin) return <Navigate to="/" replace />
  }
  return <>{children}</>
}
