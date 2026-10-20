<!--
  AppPagination — 分页
  page / total / pageSize；页码药丸 + 上一页/下一页
-->
<script setup>
import { computed } from 'vue'
import { ChevronLeft, ChevronRight } from 'lucide-vue-next'

const props = defineProps({
  page: { type: Number, default: 1 },
  total: { type: Number, default: 0 },
  pageSize: { type: Number, default: 20 },
})
const emit = defineEmits(['update:page'])

const pageCount = computed(() => Math.max(1, Math.ceil(props.total / props.pageSize)))

const pages = computed(() => {
  const n = pageCount.value
  const cur = props.page
  const out = []
  const push = (p) => out.push(p)
  if (n <= 7) { for (let i = 1; i <= n; i++) push(i); return out }
  push(1)
  if (cur > 3) push('…')
  for (let i = Math.max(2, cur - 1); i <= Math.min(n - 1, cur + 1); i++) push(i)
  if (cur < n - 2) push('…')
  push(n)
  return out
})

const go = (p) => {
  const target = Math.min(Math.max(1, p), pageCount.value)
  if (target !== props.page) emit('update:page', target)
}
</script>

<template>
  <div v-if="total > pageSize" class="flex items-center justify-center gap-1">
    <button
      class="p-2 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors disabled:opacity-30 disabled:pointer-events-none"
      :disabled="page <= 1"
      @click="go(page - 1)"
    >
      <ChevronLeft class="w-4 h-4" />
    </button>
    <button
      v-for="(p, i) in pages"
      :key="i"
      class="min-w-8 h-8 px-2 rounded-ctl text-[13px] font-medium transition-all duration-150"
      :class="
        p === page
          ? 'bg-brand-soft text-brand border border-brand/25'
          : p === '…'
            ? 'text-ink-3 pointer-events-none'
            : 'text-ink-2 hover:text-ink hover:bg-surface-2 border border-transparent'
      "
      @click="p !== '…' && go(p)"
    >
      {{ p }}
    </button>
    <button
      class="p-2 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors disabled:opacity-30 disabled:pointer-events-none"
      :disabled="page >= pageCount"
      @click="go(page + 1)"
    >
      <ChevronRight class="w-4 h-4" />
    </button>
  </div>
</template>
