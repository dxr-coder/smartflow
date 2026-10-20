<!--
  ChatComposer — 输入区（悬浮玻璃坞）
  textarea 自动伸缩 1-6 行；Enter 发送、Shift+Enter 换行（IME 安全）
  emit: send(text)；loading 时禁用
-->
<script setup>
import { ref, watch, nextTick } from 'vue'
import { ArrowUp, Loader2 } from 'lucide-vue-next'
import { useMagnetic } from '../../composables/useMagnetic'

const props = defineProps({
  loading: Boolean,
  modelValue: { type: String, default: '' },
})
const emit = defineEmits(['send', 'update:modelValue'])

const { el: magneticEl, onMove, onLeave } = useMagnetic(0.32)
const sendEl = (node) => { magneticEl.value = node }

const text = ref('')
const ta = ref(null)
const focused = ref(false)

// 外部填充（建议提示词 chip）→ 同步内部值
watch(
  () => props.modelValue,
  (v) => { if (v && v !== text.value) text.value = v }
)
watch(text, (v) => { if (v !== props.modelValue) emit('update:modelValue', v) })

watch(text, async () => {
  await nextTick()
  const node = ta.value
  if (!node) return
  node.style.height = 'auto'
  const lh = parseFloat(getComputedStyle(node).lineHeight) || 22
  node.style.height = Math.min(node.scrollHeight, lh * 6 + 24) + 'px'
})

const submit = () => {
  const t = text.value.trim()
  if (!t || props.loading) return
  emit('send', t)
  text.value = ''
  // 重置高度
  nextTick(() => { if (ta.value) ta.value.style.height = 'auto' })
}

const onKeydown = (e) => {
  if (e.key === 'Enter' && !e.shiftKey && !e.isComposing) {
    e.preventDefault()
    submit()
  }
}

const focus = () => ta.value?.focus()
defineExpose({ focus })
</script>

<template>
  <div class="px-4 pb-4 lg:pb-6">
    <!-- 流式思考指示：脉冲活体核心 + 文字 -->
    <div v-if="loading" class="max-w-3xl mx-auto mb-3 flex items-center justify-center gap-2.5 animate-fade-in">
      <span class="relative flex w-4 h-4" aria-hidden="true">
        <span class="absolute inset-0 rounded-full bg-ai/50 animate-ping" />
        <span class="relative inline-flex w-4 h-4 rounded-full bg-gradient-to-br from-ai to-[#0e7490] shadow-[0_0_12px_var(--ai-glow)]" />
      </span>
      <span class="text-[13px] text-ink-2 flex items-center gap-1.5">
        正在思考
        <span class="flex gap-0.5">
          <span class="w-1 h-1 rounded-full bg-ai animate-[typing-dot_1.2s_ease-in-out_infinite]" />
          <span class="w-1 h-1 rounded-full bg-ai animate-[typing-dot_1.2s_ease-in-out_0.2s_infinite]" />
          <span class="w-1 h-1 rounded-full bg-ai animate-[typing-dot_1.2s_ease-in-out_0.4s_infinite]" />
        </span>
      </span>
    </div>
    <div
      class="relative max-w-3xl mx-auto rounded-2xl transition-all duration-300"
      :class="focused ? 'shadow-[0_0_0_1px_var(--brand-soft),0_16px_48px_-16px_var(--brand-glow)]' : 'shadow-[var(--shadow-card)]'"
    >
      <!-- 聚焦锥形流光描边 -->
      <div
        class="absolute -inset-px rounded-2xl transition-opacity duration-300 overflow-hidden pointer-events-none"
        :class="focused ? 'opacity-100' : 'opacity-0'"
        aria-hidden="true"
      >
        <div class="absolute inset-[-200%] animate-conic-spin" style="background: conic-gradient(from 0deg, transparent 0%, var(--brand) 16%, var(--ai) 34%, transparent 52%, transparent 100%)" />
      </div>
      <div class="relative flex items-end gap-2 bg-glass backdrop-blur-xl border border-line rounded-2xl px-3 py-2 transition-colors duration-200"
        :class="focused ? 'border-transparent' : ''"
      >
      <textarea
        ref="ta"
        v-model="text"
        :disabled="loading"
        rows="1"
        placeholder="输入消息…（Enter 发送，Shift+Enter 换行）"
        class="flex-1 min-w-0 bg-transparent text-sm text-ink placeholder:text-ink-3 outline-none resize-none py-1.5 px-1 leading-[1.55] disabled:opacity-50"
        @keydown="onKeydown"
        @focus="focused = true"
        @blur="focused = false"
      />
      <button
        ref="sendEl"
        class="magnetic relative shrink-0 w-8 h-8 rounded-[10px] flex items-center justify-center transition-all duration-150"
        :class="
          text.trim() && !loading
            ? 'bg-brand text-brand-ink hover:bg-brand-strong shadow-[0_4px_14px_-4px_var(--brand-glow)] active:scale-95'
            : 'bg-surface-2 text-ink-3 cursor-not-allowed'
        "
        :disabled="!text.trim() || loading"
        aria-label="发送"
        @mousemove="onMove"
        @mouseleave="onLeave"
        @click="submit"
      >
        <span v-if="text.trim() && !loading" class="magnetic-light absolute inset-0 rounded-[10px] pointer-events-none" aria-hidden="true" />
        <Loader2 v-if="loading" class="w-4 h-4 animate-spin-dot" />
        <ArrowUp v-else class="w-4 h-4" :stroke-width="2.2" />
      </button>
      </div>
    </div>
    <p class="max-w-3xl mx-auto mt-2 text-center text-[11px] text-ink-3/70">
      AI 生成内容仅供参考，请核对重要信息
    </p>
  </div>
</template>
