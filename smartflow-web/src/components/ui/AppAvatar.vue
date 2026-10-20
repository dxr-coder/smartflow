<!--
  AppAvatar — 头像
  name 首字母头像（品牌渐变）；src 图片；variant: user / ai（电紫渐变 + sparkle）
-->
<script setup>
import { Sparkles } from 'lucide-vue-next'

const props = defineProps({
  name: { type: String, default: '' },
  src: { type: String, default: '' },
  size: { type: String, default: 'md' },
  variant: { type: String, default: 'user' },
})

const sizes = {
  xs: 'w-6 h-6 text-[10px]',
  sm: 'w-7 h-7 text-[11px]',
  md: 'w-9 h-9 text-[13px]',
  lg: 'w-12 h-12 text-[15px]',
}

const initial = () => {
  const n = props.name.trim()
  return n ? n[0].toUpperCase() : (props.variant === 'ai' ? '' : '?')
}
</script>

<template>
  <div
    class="relative shrink-0 rounded-full overflow-hidden flex items-center justify-center font-semibold select-none"
    :class="sizes[size]"
  >
    <img v-if="src" :src="src" :alt="name" class="w-full h-full object-cover" />
    <template v-else-if="variant === 'ai'">
      <div class="absolute inset-0 bg-gradient-to-br from-ai via-[#22d3ee] to-[#0e7490]" />
      <Sparkles class="relative text-white" :class="size === 'lg' ? 'w-5.5 h-5.5' : 'w-4 h-4'" :stroke-width="2" />
    </template>
    <template v-else>
      <div class="absolute inset-0 bg-gradient-to-br from-brand/80 to-brand-strong" />
      <span class="relative text-brand-ink">{{ initial() }}</span>
    </template>
  </div>
</template>
