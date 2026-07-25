import axios, { AxiosRequestConfig } from 'axios'
import toast from 'react-hot-toast'
import { useAuthStore } from '@/store/auth'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 60000,
})

http.interceptors.request.use((cfg) => {
  const token = useAuthStore.getState().token
  if (token) cfg.headers.Authorization = `Bearer ${token}`
  return cfg
})

http.interceptors.response.use(
  (res) => {
    const body = res.data
    if (body && typeof body === 'object' && 'code' in body) {
      if (body.code !== 0) {
        toast.error(body.msg || '请求失败')
        return Promise.reject(new Error(body.msg || 'Error'))
      }
      return body.data as any
    }
    return body
  },
  (err) => {
    const status = err?.response?.status
    const code = err?.response?.data?.code
    const respData = err?.response?.data
    const isLoginPage = location.pathname === '/login'
    // 优先提取后端结构化错误: {code, msg} > FastAPI {detail} > 原始 message
    let msg: string = ''
    if (respData && typeof respData === 'object') {
      msg = respData.msg || respData.detail || respData.message
      if (!msg && Array.isArray(respData.detail)) msg = respData.detail.map((d: any) => d.msg || JSON.stringify(d)).join('; ')
    }
    msg = msg || err.message || '网络错误'
    if (status === 401 || code === 4010) {
      // 登录页遇到 401 不弹 toast (用户还没登录, token 为空/过期都属正常),仅清理本地凭证
      if (!isLoginPage) toast.error('登录已失效，请重新登录')
      useAuthStore.getState().logout()
      if (!isLoginPage) location.href = '/login'
    } else if (status && status >= 500) {
      // 登录页遇到 5xx 可能是后端尚未就绪/重启中, 静默处理避免堆叠错误
      if (!isLoginPage) toast.error(`服务器错误 (${status}): ${msg.slice(0, 200)}`)
    } else if (status === 404) {
      toast.error(`资源不存在: ${msg.slice(0, 120)}`)
    } else if (status === 422 || code === 4220) {
      // 参数校验错误, 由调用方处理或轻提示
      toast.error(msg.slice(0, 200))
    } else if (status) {
      toast.error(msg)
    }
    return Promise.reject(err)
  },
)

export default {
  get<T = any>(url: string, cfg?: AxiosRequestConfig) { return http.get<any, T>(url, cfg) },
  post<T = any>(url: string, data?: any, cfg?: AxiosRequestConfig) { return http.post<any, T>(url, data, cfg) },
  put<T = any>(url: string, data?: any, cfg?: AxiosRequestConfig) { return http.put<any, T>(url, data, cfg) },
  patch<T = any>(url: string, data?: any, cfg?: AxiosRequestConfig) { return http.patch<any, T>(url, data, cfg) },
  delete<T = any>(url: string, cfg?: AxiosRequestConfig) { return http.delete<any, T>(url, cfg) },
}
