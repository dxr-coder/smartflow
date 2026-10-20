<!--
  AppEmptyState — 空状态
  icon 图标（lucide 组件）+ 标题 + 描述 + action 插槽
-->
<script setup>
defineProps({
  icon: { type: Object, default: null },
  title: { type: String, default: '暂无数据' },
  description: { type: String, default: '' },
  compact: Boolean,
})
</script>

<template>
  <div class="flex flex-col items-center justify-center text-center animate-fade-up" :class="compact ? 'py-8' : 'py-16'">
    <div
      v-if="icon"
      class="flex items-center justify-center rounded-full bg-surface-2 border border-line mb-4"
      :class="compact ? 'w-10 h-10' : 'w-14 h-14'"
    >
      <component :is="icon" class="text-ink-3" :class="compact ? 'w-5 h-5' : 'w-6.5 h-6.5'" :stroke-width="1.5" />
    </div>
    <p class="font-medium text-ink" :class="compact ? 'text-sm' : 'text-[15px]'">{{ title }}</p>
    <p v-if="description" class="mt-1.5 text-ink-3 max-w-xs leading-relaxed" :class="compact ? 'text-xs' : 'text-[13px]'">
      {{ description }}
    </p>
    <div v-if="$slots.action" class="mt-5"><slot /></div>
  </div>
</template>
