/**
 * useChatStream — SSE 流式对话
 * 协议：首行 JSON meta（agent_name/source/citations/message_id），其余为增量文本
 * 滚动：rAF 批量（每帧最多滚一次，替代逐 chunk nextTick）
 * 首发自动建会话；onFinished 刷新侧栏标题
 */
import { ref, nextTick } from 'vue'
import api from '../api'

export function useChatStream(containerRef, { onNewConversation, onFinished } = {}) {
  const messages = ref([])
  const loading = ref(false)
  const error = ref('')

  let scrollScheduled = false
  const scrollToBottom = () => {
    if (scrollScheduled) return
    scrollScheduled = true
    requestAnimationFrame(async () => {
      scrollScheduled = false
      await nextTick()
      const node = containerRef.value
      if (node) node.scrollTop = node.scrollHeight
    })
  }

  const send = async (text, conversationIdRef) => {
    if (!text.trim() || loading.value) return
    const userMsg = text.trim()
    messages.value.push({ role: 'user', content: userMsg })
    error.value = ''
    loading.value = true
    scrollToBottom()

    let convId = typeof conversationIdRef === 'object' && 'value' in conversationIdRef
      ? conversationIdRef.value
      : conversationIdRef

    if (!convId) {
      try {
        const res = await api.post('/conversations')
        convId = res.data.id
        if (conversationIdRef && typeof conversationIdRef === 'object' && 'value' in conversationIdRef) {
          conversationIdRef.value = convId
        }
        onNewConversation?.(convId)
      } catch (e) {
        error.value = '创建对话失败'
        messages.value.pop()
        loading.value = false
        return
      }
    }

    messages.value.push({ role: 'assistant', content: '', agent_name: '' })
    const idx = messages.value.length - 1

    try {
      const token = localStorage.getItem('token')
      const url = `/chat/stream?message=${encodeURIComponent(userMsg)}&conversation_id=${convId}`
      const res = await fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      if (!res.ok) throw new Error(`请求失败 (${res.status})`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let firstLine = true
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const text2 = decoder.decode(value, { stream: true })

        if (firstLine) {
          buffer += text2
          const nl = buffer.indexOf('\n')
          if (nl !== -1) {
            try {
              const meta = JSON.parse(buffer.slice(0, nl))
              messages.value[idx].agent_name = meta.agent_name
              if (meta.source) messages.value[idx].source = meta.source
              if (meta.citations) messages.value[idx].citations = meta.citations
              if (meta.message_id) messages.value[idx].id = meta.message_id
            } catch (_) {}
            const rest = buffer.slice(nl + 1)
            if (rest) messages.value[idx].content += rest
            firstLine = false
            buffer = ''
          }
        } else {
          messages.value[idx].content += text2
        }
        scrollToBottom()
      }
    } catch (e) {
      error.value = e.message || '网络错误，请重试'
      const i = messages.value.indexOf(assistantMsg)
      if (i >= 0) messages.value.splice(i, 1)
    } finally {
      loading.value = false
      onFinished?.()
    }
  }

  const clear = () => { messages.value = []; error.value = '' }

  return { messages, loading, error, send, scrollToBottom, clear }
}
