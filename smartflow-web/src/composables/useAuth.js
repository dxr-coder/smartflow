/**
 * 认证状态
 * token 存 localStorage；userInfo 供 Topbar/权限使用
 * ensureUserLoaded：缓存进行中的 /auth/me Promise，路由守卫复用
 */
import { ref } from 'vue'
import api from '../api'

const token = ref(localStorage.getItem('token') || '')
const userInfo = ref(null)
let mePromise = null

export function useAuth() {
  const setToken = (t) => {
    token.value = t
    localStorage.setItem('token', t)
  }
  const setUser = (u) => { userInfo.value = u }
  const logout = () => {
    token.value = ''
    userInfo.value = null
    mePromise = null
    localStorage.removeItem('token')
    localStorage.removeItem('refresh_token')
    window.location.href = '/login'
  }
  return { token, userInfo, setToken, setUser, logout }
}

export function ensureUserLoaded() {
  if (!token.value) return Promise.resolve(null)
  if (userInfo.value) return Promise.resolve(userInfo.value)
  if (!mePromise) {
    mePromise = api.get('/auth/me')
      .then((res) => { userInfo.value = res.data; return res.data })
      .catch(() => {
        userInfo.value = null
        localStorage.removeItem('token')
        localStorage.removeItem('refresh_token')
        token.value = ''
        return null
      })
      .finally(() => { mePromise = null })
  }
  return mePromise
}
