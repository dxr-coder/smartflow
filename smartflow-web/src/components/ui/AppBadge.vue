<!--
  AppBadge — 状态徽章
  tone: gray/brand/ai/amber/red/blue；dot 可选呼吸点；soft 底色 / outline 描边
-->
<script setup>
defineProps({
  tone: { type: String, default: 'gray' },
  variant: { type: String, default: 'soft' },
  size: { type: String, default: 'md' },
  dot: Boolean,
})

const tones = {
  gray: { soft: 'bg-surface-2 text-ink-2 border-line', dot: 'bg-ink-3' },
  brand: { soft: 'bg-brand-soft text-brand border-brand/25', dot: 'bg-brand' },
  ai: { soft: 'bg-ai-soft text-ai border-ai/25', dot: 'bg-ai' },
  amber: { soft: 'bg-amber-soft text-amber border-amber/25', dot: 'bg-amber' },
  red: { soft: 'bg-red-soft text-red border-red/25', dot: 'bg-red' },
  blue: { soft: 'bg-blue-soft text-blue border-blue/25', dot: 'bg-blue' },
}

const sizes = { sm: 'text-[11px] px-1.5 py-0.5 gap-1', md: 'text-[12px] px-2 py-0.5 gap-1.5' }
</script>

<template>
  <span
    class="inline-flex items-center font-medium border rounded-full whitespace-nowrap"
    :class="[tones[tone]?.soft || tones.gray.soft, sizes[size]]"
  >
    <span
      v-if="dot"
      class="w-1.5 h-1.5 rounded-full animate-pulse-soft"
      :class="tones[tone]?.dot || tones.gray.dot"
    />
    <slot />
  </span>
</template>
