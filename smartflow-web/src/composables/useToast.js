/**
 * Toast 单例：模块级状态，main.js 在 mount 前也能用
 * 最多 3 条堆叠；error 默认 4.5s，其余 3s
 */
import { ref } from 'vue'

const toasts = ref([])
let uid = 0

const show = (type, message, duration) => {
  const id = ++uid
  toasts.value.push({ id, type, message })
  if (toasts.value.length > 3) toasts.value.shift()
  setTimeout(() => dismiss(id), duration || (type === 'error' ? 4500 : 3000))
}

const dismiss = (id) => {
  toasts.value = toasts.value.filter((t) => t.id !== id)
}

export const toast = {
  success: (m, d) => show('success', m, d),
  error: (m, d) => show('error', m, d),
  info: (m, d) => show('info', m, d),
}

export function useToast() {
  return { toasts, dismiss, ...toast }
}
