<!--
  ChatSearchBar — 消息内搜索
  关键词高亮由父级处理；本组件负责输入 + 上下条 + 计数
  emit: query-change, nav(dir), close
-->
<script setup>
import { ref, watch } from 'vue'
import { Search, ChevronUp, ChevronDown, X } from 'lucide-vue-next'

const props = defineProps({
  total: { type: Number, default: 0 },
  current: { type: Number, default: 0 },
})
const emit = defineEmits(['query-change', 'nav', 'close'])

const q = ref('')
const inputRef = ref(null)

watch(q, () => emit('query-change', q.value))

const focus = () => inputRef.value?.focus()
defineExpose({ focus })

const onKeydown = (e) => {
  if (e.key === 'Enter') { e.preventDefault(); emit('nav', e.shiftKey ? -1 : 1) }
  if (e.key === 'Escape') emit('close')
}
</script>

<template>
  <div class="flex items-center gap-1.5 animate-scale-in">
    <div class="flex items-center gap-2 bg-surface-3 border border-line rounded-ctl px-2.5 h-8 w-56 sm:w-64 shadow-[var(--shadow-card)]">
      <Search class="w-3.5 h-3.5 text-ink-3 shrink-0" />
      <input
        ref="inputRef"
        v-model="q"
        type="text"
        placeholder="搜索消息…"
        class="flex-1 min-w-0 bg-transparent text-[13px] text-ink placeholder:text-ink-3 outline-none"
        @keydown="onKeydown"
      />
      <span v-if="q" class="text-[11px] text-ink-3 tabular-nums whitespace-nowrap">{{ total ? current + 1 : 0 }}/{{ total }}</span>
    </div>
    <button
      class="w-7 h-7 rounded-ctl flex items-center justify-center text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors disabled:opacity-30"
      :disabled="!total"
      aria-label="上一个"
      @click="emit('nav', -1)"
    >
      <ChevronUp class="w-3.5 h-3.5" />
    </button>
    <button
      class="w-7 h-7 rounded-ctl flex items-center justify-center text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors disabled:opacity-30"
      :disabled="!total"
      aria-label="下一个"
      @click="emit('nav', 1)"
    >
      <ChevronDown class="w-3.5 h-3.5" />
    </button>
    <button
      class="w-7 h-7 rounded-ctl flex items-center justify-center text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors"
      aria-label="关闭搜索"
      @click="emit('close')"
    >
      <X class="w-3.5 h-3.5" />
    </button>
  </div>
</template>
