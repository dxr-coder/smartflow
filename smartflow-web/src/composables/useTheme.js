/**
 * 主题：亮色优先。html 加 .light = 亮色（默认），无 class = 暗色
 * localStorage 'sf-theme' = 'light' | 'dark'
 * isLight 供图表等 JS 场景读取当前是否亮色
 */
import { ref, watchEffect } from 'vue'

const KEY = 'sf-theme'
const stored = localStorage.getItem(KEY)
const isLight = ref(stored !== 'dark')

watchEffect(() => {
  document.documentElement.classList.toggle('light', isLight.value)
  document.documentElement.style.background = isLight.value ? '#f7f7fa' : '#09090b'
  document.querySelector('meta[name="theme-color"]')?.setAttribute(
    'content',
    isLight.value ? '#f7f7fa' : '#09090b'
  )
  localStorage.setItem(KEY, isLight.value ? 'light' : 'dark')
})

export function useTheme() {
  const toggle = () => { isLight.value = !isLight.value }
  return { isLight, toggle }
}
