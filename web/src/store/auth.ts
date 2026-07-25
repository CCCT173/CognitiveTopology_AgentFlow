import { create } from 'zustand'
import { authApi, User } from '@/api'

interface AuthState {
  token: string
  user: User | null
  login: (account: string, password: string) => Promise<void>
  register: (data: { username: string; account: string; email: string; password: string; bind_admin_id?: number | null }) => Promise<void>
  fetchMe: () => Promise<void>
  logout: () => void
  updateUser: (u: Partial<User>) => void
}

export const useAuthStore = create<AuthState>((set, get) => ({
  token: localStorage.getItem('token') || '',
  user: null,
  login: async (account, password) => {
    const data = await authApi.login({ account, password })
    localStorage.setItem('token', data.token)
    set({ token: data.token, user: data.user })
  },
  register: async (d) => {
    const data = await authApi.register({ ...d, bind_admin_id: d.bind_admin_id ?? undefined })
    localStorage.setItem('token', data.token)
    set({ token: data.token, user: data.user })
  },
  fetchMe: async () => {
    const token = get().token
    if (!token) return
    try {
      const u = await authApi.me()
      set({ user: u })
    } catch {
      get().logout()
    }
  },
  logout: () => {
    localStorage.removeItem('token')
    set({ token: '', user: null })
  },
  updateUser: (u) => set({ user: get().user ? { ...get().user!, ...u } : null }),
}))
