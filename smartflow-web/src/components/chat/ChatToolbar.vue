<!--
  ChatToolbar — 会话顶栏
  左：移动端菜单按钮 + 会话标题/标签；右：搜索切换 + 导出 + 消息计数
  视觉：底部品牌→AI 渐变发丝线；玻璃顶栏
-->
<script setup>
import { Menu, Search, Download, MessageSquare } from 'lucide-vue-next'

defineProps({
  title: { type: String, default: '新对话' },
  tags: { type: Array, default: () => [] },
  messageCount: { type: Number, default: 0 },
  searchOpen: Boolean,
  canExport: Boolean,
})
const emit = defineEmits(['toggle-sidebar', 'toggle-search', 'export'])
</script>

<template>
  <header class="relative shrink-0 flex items-center gap-2 px-4 h-12 border-b border-line bg-glass backdrop-blur-xl">
    <!-- 移动端菜单 -->
    <button
      class="lg:hidden p-1.5 -ml-1 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-colors"
      aria-label="打开会话列表"
      @click="emit('toggle-sidebar')"
    >
      <Menu class="w-4.5 h-4.5" />
    </button>

    <div class="min-w-0 flex-1">
      <div class="flex items-center gap-2">
        <MessageSquare v-if="messageCount" class="w-3.5 h-3.5 text-brand shrink-0 hidden sm:block" :stroke-width="1.8" />
        <h1 class="text-sm font-medium text-ink truncate">{{ title }}</h1>
        <span
          v-for="t in tags.slice(0, 2)"
          :key="t"
          class="hidden sm:inline text-[11px] px-1.5 py-px rounded-full bg-surface-2 border border-line text-ink-3"
        >{{ t }}</span>
      </div>
    </div>

    <span v-if="messageCount" class="hidden sm:inline text-[11px] text-ink-3 tabular-nums mr-1">{{ messageCount }} 条消息</span>

    <button
      class="p-1.5 rounded-ctl transition-all duration-150"
      :class="searchOpen ? 'text-brand bg-brand-soft' : 'text-ink-3 hover:text-ink hover:bg-surface-2'"
      aria-label="搜索"
      @click="emit('toggle-search')"
    >
      <Search class="w-4 h-4" />
    </button>
    <button
      v-if="canExport"
      class="p-1.5 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-all duration-150"
      aria-label="导出 Markdown"
      @click="emit('export')"
    >
      <Download class="w-4 h-4" />
    </button>

    <!-- 底部渐变发丝线 -->
    <div class="absolute inset-x-0 -bottom-px h-px bg-gradient-to-r from-transparent via-brand/35 to-transparent" aria-hidden="true" />
  </header>
</template>
