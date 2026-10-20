<!--
  ChatMessageItem — 单条消息（编辑式 transcript）
  用户 = 右侧品牌渐变气泡（带尾迹）；AI = 全宽文本块 + 左侧品牌渐变竖线
  流式期间最后一条 assistant 显示闪烁光标
  数据流：content 经 renderMarkdown（DOMPurify 消毒）→ v-html
-->
<script setup>
import { computed } from 'vue'
import { renderMarkdown } from '../../utils/markdown'
import ChatMessageMeta from './ChatMessageMeta.vue'
import AppAvatar from '../ui/AppAvatar.vue'

const props = defineProps({
  message: { type: Object, required: true },
  streaming: Boolean, // 是否正在流式输出（仅最后一条 assistant 传 true）
  conversationId: { type: [Number, String], default: null },
})

const html = computed(() => renderMarkdown(props.message.content))
</script>

<template>
  <!-- 用户消息：右侧气泡 -->
  <div v-if="message.role === 'user'" class="flex justify-end animate-rise">
    <div class="max-w-[85%] sm:max-w-[72%] relative">
      <div
        class="px-4 py-2.5 rounded-2xl rounded-br-md bg-gradient-to-br from-brand to-brand-strong text-brand-ink text-[14px] leading-[1.65] shadow-[0_4px_16px_-6px_var(--brand-glow)]"
        style="white-space: pre-wrap; word-break: break-word"
      >{{ message.content }}</div>
      <!-- 尾迹高光 -->
      <span class="absolute -bottom-px -right-px w-3 h-3 bg-gradient-to-tl from-brand-strong to-transparent rounded-br-md opacity-60" aria-hidden="true" />
    </div>
  </div>

  <!-- AI 消息：全宽编辑式文本块 + 左侧竖线 -->
  <div v-else class="flex gap-3 animate-rise">
    <AppAvatar variant="ai" size="sm" class="mt-0.5 shrink-0" />
    <div class="flex-1 min-w-0 min-h-[28px] relative pl-3.5">
      <!-- 左侧品牌渐变竖线 -->
      <span class="absolute left-0 top-1 bottom-1 w-[2px] rounded-full bg-gradient-to-b from-brand/60 via-ai/40 to-transparent" aria-hidden="true" />
      <!-- meta：agent 徽章 / 来源 / 引用 / 反馈 -->
      <ChatMessageMeta :message="message" :conversation-id="conversationId" class="mb-2" />
      <!-- 正文 -->
      <div class="markdown-body text-ink" v-html="html" />
      <!-- 流式光标 -->
      <span v-if="streaming && message.content" class="inline-block w-2 h-4 ml-0.5 align-text-bottom bg-brand animate-blink" />
    </div>
  </div>
</template>
