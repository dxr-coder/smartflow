<!--
  ChatMessageMeta — AI 消息的元信息行
  agent 徽章（AI 青）、来源徽章（kb 品牌 / web 天蓝）、引用 chips（hover 显示文档名）
  👍👎 点赞弹跳动画 + 已反馈态
  数据流：POST /feedback {conversation_id, message_id, rating, agent_name}
-->
<script setup>
import { ref, computed } from 'vue'
import { ThumbsUp, ThumbsDown, FileText, Globe } from 'lucide-vue-next'
import api from '../../api'
import { toast } from '../../composables/useToast'
import AppBadge from '../ui/AppBadge.vue'

const props = defineProps({
  message: { type: Object, required: true },
  conversationId: { type: [Number, String], default: null },
})

const rating = ref(null) // null | 'like' | 'dislike'
const popKey = ref('')

const sourceMeta = computed(() => {
  const s = props.message.source
  if (!s) return null
  if (s === 'kb') return { label: '知识库', icon: FileText, tone: 'brand' }
  if (s === 'web') return { label: '网络', icon: Globe, tone: 'blue' }
  return { label: s, icon: FileText, tone: 'gray' }
})

// 后端契约：citations = [{ index, document_name }]；兼容字符串数组
const citations = computed(() => {
  const c = props.message.citations
  if (!Array.isArray(c)) return []
  const normalized = c.map((x) =>
    typeof x === 'string'
      ? { label: x, title: x }
      : {
          label: x.document_name || x.filename || x.text || '',
          title: x.text || x.document_name || '',
        }
  ).filter((x) => x.label)
  return normalized.filter((x, i, arr) => arr.findIndex((y) => y.label === x.label) === i)
})

const sendFeedback = async (r) => {
  if (!props.message.id || rating.value === r) return
  rating.value = r
  popKey.value = r + Date.now()
  try {
    await api.post('/feedback', {
      conversation_id: props.conversationId || props.message.conversation_id,
      message_id: props.message.id,
      rating: r,
      agent_name: props.message.agent_name,
    })
    toast.success(r === 'like' ? '感谢反馈！' : '已记录，我们会改进')
  } catch (e) {
    toast.error('反馈提交失败')
  }
}
</script>

<template>
  <div class="flex items-center flex-wrap gap-x-2 gap-y-1.5">
    <!-- agent 徽章 -->
    <AppBadge v-if="message.agent_name" tone="ai" size="sm">{{ message.agent_name }}</AppBadge>

    <!-- 来源徽章 -->
    <AppBadge v-if="sourceMeta" :tone="sourceMeta.tone" size="sm" variant="outline">
      <component :is="sourceMeta.icon" class="w-2.5 h-2.5" />
      {{ sourceMeta.label }}
    </AppBadge>

    <!-- 引用 chips -->
    <span
      v-for="cite in citations"
      :key="cite.label"
      class="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-surface-2 border border-line text-[11px] text-ink-2 cursor-help transition-colors hover:border-brand/30 hover:text-brand"
      :title="cite.title"
    >
      <FileText class="w-2.5 h-2.5" />
      {{ cite.label.length > 22 ? cite.label.slice(0, 22) + '…' : cite.label }}
    </span>

    <span class="flex-1" />

    <!-- 反馈按钮（仅完成后显示，流式中隐藏） -->
    <span v-if="message.id && message.content" class="inline-flex items-center gap-0.5">
      <button
        class="p-1.5 rounded-ctl transition-all duration-150 hover:bg-brand-soft"
        :class="rating === 'like' ? 'text-brand' : 'text-ink-3 hover:text-brand'"
        aria-label="有帮助"
        @click="sendFeedback('like')"
      >
        <ThumbsUp
          :key="'up' + (rating === 'like' ? popKey : '')"
          class="w-3.5 h-3.5"
          :class="rating === 'like' ? 'animate-pop' : ''"
        />
      </button>
      <button
        class="p-1.5 rounded-ctl transition-all duration-150 hover:bg-red-soft"
        :class="rating === 'dislike' ? 'text-red' : 'text-ink-3 hover:text-red'"
        aria-label="需改进"
        @click="sendFeedback('dislike')"
      >
        <ThumbsDown
          :key="'down' + (rating === 'dislike' ? popKey : '')"
          class="w-3.5 h-3.5"
          :class="rating === 'dislike' ? 'animate-pop' : ''"
        />
      </button>
    </span>
  </div>
</template>
