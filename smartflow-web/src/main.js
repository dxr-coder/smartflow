/**
 * 入口
 * 字体：Geist 变量字体（拉丁/数字），中文回落系统字体
 * 错误兜底：全局 error / unhandledrejection → toast 单例
 */
import { createApp } from 'vue'
import '@fontsource-variable/geist'
import '@fontsource-variable/geist-mono'
import 'highlight.js/styles/github-dark.css'
import './style.css'
import App from './App.vue'
import router from './router'
import { toast } from './composables/useToast'

const app = createApp(App)
app.use(router)

app.config.errorHandler = (err) => {
  console.error(err)
  toast.error(err?.message || '发生未知错误')
}
window.addEventListener('error', (e) => toast.error(e.message || '资源加载失败'))
window.addEventListener('unhandledrejection', (e) => {
  toast.error(e.reason?.message || '请求失败')
})

app.mount('#app')
