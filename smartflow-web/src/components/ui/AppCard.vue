<!--
  AppCard — 卡片容器
  padding: none/sm/md；hover 抬升；interactive 点击态
-->
<script setup>
defineProps({
  padding: { type: String, default: 'md' },
  hover: Boolean,
  interactive: Boolean,
  as: { type: String, default: 'div' },
})

const paddings = { none: '', sm: 'p-4', md: 'p-5' }
</script>

<template>
  <component
    :is="as"
    class="bg-surface border border-line rounded-card shadow-[var(--shadow-card)] transition-all duration-200"
    :class="[
      paddings[padding],
      hover ? 'hover:border-line-2 hover:-translate-y-0.5' : '',
      interactive ? 'cursor-pointer active:scale-[0.99]' : '',
    ]"
  >
    <slot />
  </component>
</template>
