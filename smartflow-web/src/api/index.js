/**
 * axios 实例
 * 数据流：请求头注入 access token；401 → 单飞刷新（POST /auth/refresh 轮换）→ 重放原请求；
 *        刷新失败（refresh 过期/复用被吊销）→ 清 token 踢回登录
 * 单飞锁：同时多个请求 401 时只允许一个去刷新，其余等同一 Promise——后端是轮换制，
 *        并发刷新会触发"旧 refresh 复用检测"误吊销全部 token（生产级 refresh 的经典并发坑）
 * 登录/注册接口自身的 401（密码错误等）不走刷新逻辑，直接抛给页面展示错误
 */
import axios from 'axios'

const api = axios.create({ baseURL: '' })

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// 单飞刷新：进行中的刷新 Promise；并发 401 全部复用它，防止刷新风暴
let refreshing = null

function doRefresh() {
  const rt = localStorage.getItem('refresh_token')
  if (!rt) return Promise.reject(new Error('no refresh token'))
  // 用裸 axios 直连，防止递归触发本响应拦截器
  return axios.post('/auth/refresh', { refresh_token: rt }).then((res) => {
    localStorage.setItem('token', res.data.access_token)
    localStorage.setItem('refresh_token', res.data.refresh_token)
    return res.data
  })
}

function forceLogin() {
  localStorage.removeItem('token')
  localStorage.removeItem('refresh_token')
  if (window.location.pathname !== '/login') window.location.href = '/login'
}

api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const original = err.config || {}
    const url = original.url || ''
    // 登录/注册是"用户名密码错"的 401；refresh 自身 401 = 已过期或复用被吊销
    const isLoginOrRegister = url.includes('/auth/login') || url.includes('/auth/register')
    const isRefreshCall = url.includes('/auth/refresh')

    if (err.response?.status === 401 && !isLoginOrRegister && !isRefreshCall && !original._retry) {
      original._retry = true // 重放只允许一次，防刷新成功后仍 401 的死循环
      try {
        if (!refreshing) {
          refreshing = doRefresh().finally(() => { refreshing = null })
        }
        await refreshing
        // 刷新成功：用新 access 重放刚才失败的请求
        original.headers = { ...original.headers, Authorization: `Bearer ${localStorage.getItem('token')}` }
        return api(original)
      } catch {
        forceLogin() // refresh 也失败 = 真过期了，重登
        return Promise.reject(err)
      }
    }
    if (err.response?.status === 401 && isRefreshCall) {
      forceLogin() // refresh 接口自己 401：复用检测触发或已过期，必须重登
    }
    return Promise.reject(err)
  }
)

export default api
