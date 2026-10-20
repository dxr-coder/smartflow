import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vite'

// 后端地址：默认真后端 8000；视觉审计可用 API_PROXY=http://127.0.0.1:8001 指向 mock
const apiTarget = process.env.API_PROXY || 'http://127.0.0.1:8000'

const apiProxy = () => ({
  target: apiTarget,
  changeOrigin: true,
  bypass(req) {
    if (req.headers.accept?.includes('text/html')) {
      return '/index.html'
    }
  },
})

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/auth': apiProxy(),
      '/users': apiProxy(),
      '/documents': apiProxy(),
      '/stats': apiProxy(),
      '/tickets': apiProxy(),
      '/transfer': apiProxy(),
      '/chat/stream': apiProxy(),
      '/conversations': apiProxy(),
      '/feedback': apiProxy(),
      '/audit': apiProxy(),
      '/ab-test': apiProxy(),
      '/csat': apiProxy(),
      '/eval': apiProxy(),
      '/pdf': apiProxy(),
      '/assets': apiProxy(),
    },
  },
})
