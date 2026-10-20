<!--
  AppSkeleton — 骨架屏
  variant: text / card / table / list；shimmer 光扫动画替代 animate-pulse
-->
<script setup>
defineProps({
  variant: { type: String, default: 'text' },
  rows: { type: Number, default: 3 },
})

const shimmerStyle = {
  backgroundImage:
    'linear-gradient(90deg, var(--surface-2) 25%, var(--line) 50%, var(--surface-2) 75%)',
  backgroundSize: '200% 100%',
}
</script>

<template>
  <div class="animate-shimmer" :style="shimmerStyle">
    <template v-if="variant === 'text'">
      <div class="space-y-2.5">
        <div
          v-for="i in rows"
          :key="i"
          class="h-3.5 rounded-md bg-surface-2"
          :class="i === rows && rows > 1 ? 'w-2/3' : 'w-full'"
        />
      </div>
    </template>
    <template v-else-if="variant === 'card'">
      <div class="rounded-card bg-surface-2 h-28 w-full" />
    </template>
    <template v-else-if="variant === 'table'">
      <div class="space-y-3">
        <div v-for="i in rows" :key="i" class="h-4 rounded-md bg-surface-2" :class="i % 3 === 0 ? 'w-3/4' : 'w-full'" />
      </div>
    </template>
    <template v-else-if="variant === 'list'">
      <div class="space-y-3">
        <div v-for="i in rows" :key="i" class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-surface-2 shrink-0" />
          <div class="flex-1 space-y-2">
            <div class="h-3 rounded bg-surface-2" :class="i % 2 === 0 ? 'w-1/2' : 'w-3/4'" />
            <div class="h-2.5 rounded bg-surface-2 w-1/3" />
          </div>
        </div>
      </div>
    </template>
  </div>
</template>
