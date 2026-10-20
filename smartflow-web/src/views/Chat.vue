<!--
  Chat — 对话工作区编排器
  数据流：
    GET /conversations → 侧栏列表
    GET /conversations/:id/messages → 历史消息
    useChatStream.send → POST /conversations（无 id 时）+ GET /chat/stream（SSE）
    导出 → exportMarkdown Blob 下载
-->
<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import api from '../api'
import { useChatStream } from '../composables/useChatStream'
import { exportMarkdown } from '../utils/exportMarkdown'
import { toast } from '../composables/useToast'
import ConversationSidebar from '../components/chat/ConversationSidebar.vue'
import ChatEmptyState from '../components/chat/ChatEmptyState.vue'
import ChatMessageItem from '../components/chat/ChatMessageItem.vue'
import ChatToolbar from '../components/chat/ChatToolbar.vue'
import ChatSearchBar from '../components/chat/ChatSearchBar.vue'
import ChatComposer from '../components/chat/ChatComposer.vue'

const scrollRef = ref(null)
const textareaRef = ref(null)
const currentId = ref(null)
const streamingConvId = ref(null) // 流式中的会话 id，防止 watch 重复拉历史覆盖流式内容
const conversations = ref([])
const sidebarOpen = ref(false)
const searchOpen = ref(false)
const searchRef = ref(null)
const searchQuery = ref('')
const searchMatches = ref([]) // 匹配到的消息 index
const searchIdx = ref(0)
const composerText = ref('')

const { messages, loading, error, send, clear } = useChatStream(scrollRef, {
  onNewConversation: (id) => {
    streamingConvId.value = id
    currentId.value = id
    loadConversations()
  },
  onFinished: () => {
    streamingConvId.value = null
    loadConversations()
  },
})

const activeConv = computed(() => conversations.value.find((c) => c.id === currentId.value))
const title = computed(() => activeConv.value?.title || '新对话')
const tags = computed(() => activeConv.value?.tags || [])
const isStreaming = computed(() => loading.value)

const agentLabel = (name, source) => {
  const src = source === 'kb' ? '知识库' : source === 'web' ? '网络' : ''
  return [name, src].filter(Boolean).join(' · ')
}

const loadConversations = async () => {
  try {
    const res = await api.get('/conversations')
    // 后端 tags 是逗号拼接字符串，此处统一规范成数组，下游（侧栏 chip / 顶栏 / 编辑弹层）全部按数组消费
    conversations.value = (res.data.items || res.data).map((c) => ({
      ...c,
      tags: Array.isArray(c.tags) ? c.tags : c.tags ? String(c.tags).split(',') : [],
    }))
  } catch (e) {
    /* 静默：侧栏非关键路径 */
  }
}

const loadMessages = async (id) => {
  clear()
  if (!id) return
  try {
    const res = await api.get(`/conversations/${id}/messages`)
    const list = res.data.items || res.data
    messages.value = (list || []).map((m) => ({
      role: m.role,
      content: m.content,
      agent_name: m.agent_name,
      source: m.source,
      citations: m.citations,
      id: m.message_id || m.id,
      conversation_id: id,
    }))
    await nextTick()
    scrollRef.value?.scrollTo({ top: scrollRef.value.scrollHeight })
  } catch (e) {
    toast.error('加载历史消息失败')
  }
}

const selectConv = (id) => {
  currentId.value = id
  sidebarOpen.value = false
  searchOpen.value = false
}

watch(currentId, (id) => {
  // 流式期间新建的会话：服务端还没有落盘消息，loadMessages 会把流式内容清空
  if (id && id === streamingConvId.value) return
  loadMessages(id)
}, { immediate: false })

const newConv = () => {
  currentId.value = null
  clear()
  sidebarOpen.value = false
  searchOpen.value = false
}

const doSend = (text) => {
  send(text, currentId)
}

const onSuggest = (text) => {
  composerText.value = text
  // 聚焦输入框，让用户直接看到已填入的内容
  nextTick(() => textareaRef.value?.focus())
}

// 搜索
const onSearchQuery = (q) => {
  searchQuery.value = q
  searchMatches.value = []
  searchIdx.value = 0
  if (!q) return
  const lower = q.toLowerCase()
  messages.value.forEach((m, i) => {
    if (m.content && m.content.toLowerCase().includes(lower)) searchMatches.value.push(i)
  })
}

const onSearchNav = (dir) => {
  const total = searchMatches.value.length
  if (!total) return
  searchIdx.value = (searchIdx.value + dir + total) % total
  scrollToMessage(searchMatches.value[searchIdx.value])
}

const scrollToMessage = async (msgIndex) => {
  await nextTick()
  const nodes = scrollRef.value?.querySelectorAll('[data-msg-index]')
  nodes?.[msgIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' })
}

const toggleSearch = () => {
  searchOpen.value = !searchOpen.value
  if (searchOpen.value) nextTick(() => searchRef.value?.focus())
  else { searchQuery.value = ''; searchMatches.value = [] }
}

const doExport = () => {
  exportMarkdown(messages.value, agentLabel)
  toast.success('已导出 Markdown')
}

onMounted(() => {
  loadConversations()
})
</script>

<template>
  <div class="flex h-[calc(100dvh-4rem)] md:h-dvh">
    <!-- 会话侧栏 -->
    <ConversationSidebar
      :conversations="conversations"
      :active-id="currentId"
      :mobile-open="sidebarOpen"
      @select="selectConv"
      @new="newConv"
      @update:mobile-open="sidebarOpen = $event"
      @tags-saved="loadConversations"
    />

    <!-- 主区（电影级错峰入场：工具栏→消息区→输入坞） -->
    <div class="flex-1 flex flex-col min-w-0">
      <div class="animate-rise" style="animation-delay: 40ms">
        <ChatToolbar
        :title="title"
        :tags="tags"
        :message-count="messages.length"
        :search-open="searchOpen"
        :can-export="messages.length > 0"
        @toggle-sidebar="sidebarOpen = true"
        @toggle-search="toggleSearch"
        @export="doExport"
        />
      </div>

      <!-- 搜索条（覆盖在顶栏下） -->
      <div v-if="searchOpen" class="px-4 py-2 border-b border-line bg-surface/80 backdrop-blur-sm">
        <ChatSearchBar
          ref="searchRef"
          :total="searchMatches.length"
          :current="searchIdx"
          @query-change="onSearchQuery"
          @nav="onSearchNav"
          @close="toggleSearch"
        />
      </div>

      <!-- 消息区 -->
      <div ref="scrollRef" class="relative flex-1 overflow-y-auto animate-rise" style="animation-delay: 110ms">
        <!-- 极淡点阵底纹（仅消息态显示） -->
        <div
          v-if="messages.length"
          class="pointer-events-none absolute inset-0 opacity-[0.35]"
          style="background-image: radial-gradient(var(--line) 1px, transparent 1px); background-size: 22px 22px"
          aria-hidden="true"
        />
        <ChatEmptyState v-if="!messages.length && !loading" @suggest="onSuggest" />
        <div v-else class="relative max-w-3xl mx-auto px-4 lg:px-6 py-6 space-y-7">
          <ChatMessageItem
            v-for="(m, i) in messages"
            :key="i"
            :message="m"
            :conversation-id="currentId"
            :streaming="isStreaming && i === messages.length - 1 && m.role === 'assistant'"
          />
        </div>
      </div>

      <!-- 输入坞 -->
      <div class="animate-rise" style="animation-delay: 180ms">
        <ChatComposer ref="textareaRef" :loading="loading" :model-value="composerText" @send="doSend" @update:model-value="composerText = $event" />
      </div>
    </div>
  </div>
</template>
