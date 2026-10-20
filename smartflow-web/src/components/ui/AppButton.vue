<!--
  AppButton — 按钮
  variant: brand（发光主按钮）/ secondary / ghost / danger / ai
  微交互：磁吸跟随（brand/ai）+ hover 亮起 + active 压缩 + loading 内嵌 spinner
-->
<script setup>
import { Loader2 } from 'lucide-vue-next'
import { useMagnetic } from '../../composables/useMagnetic'

const props = defineProps({
  variant: { type: String, default: 'brand' },
  size: { type: String, default: 'md' },
  loading: Boolean,
  disabled: Boolean,
  block: Boolean,
  type: { type: String, default: 'button' },
})

// 主/AI 按钮带磁吸；其余保持轻量
const isMagnetic = () => props.variant === 'brand' || props.variant === 'ai'
const { el, onMove, onLeave } = useMagnetic(0.28)
const setBtnRef = (node) => { if (isMagnetic()) el.value = node }

const variants = {
  brand:
    'bg-brand text-brand-ink hover:bg-brand-strong shadow-[0_0_0_0_var(--brand-glow)] hover:shadow-[0_8px_28px_-6px_var(--brand-glow)] font-semibold',
  secondary:
    'bg-surface-2 text-ink border border-line hover:border-line-2 hover:bg-surface-3',
  ghost: 'text-ink-2 hover:text-ink hover:bg-surface-2',
  danger: 'bg-red text-white hover:opacity-90 font-medium',
  ai: 'bg-ai text-white hover:opacity-90 font-medium shadow-[0_8px_24px_-8px_var(--ai-glow)]',
}

const sizes = {
  sm: 'h-8 px-3 text-[13px] rounded-ctl gap-1.5',
  md: 'h-9.5 px-4 text-sm rounded-ctl gap-2',
  lg: 'h-11 px-6 text-[15px] rounded-ctl gap-2',
}
</script>

<template>
  <button
    :ref="setBtnRef"
    :type="type"
    :disabled="disabled || loading"
    class="relative inline-flex items-center justify-center whitespace-nowrap transition-all duration-150 select-none active:scale-[0.97] disabled:opacity-40 disabled:pointer-events-none"
    :class="[
      variants[variant], sizes[size], block ? 'w-full' : '',
      isMagnetic() ? 'magnetic' : '',
    ]"
    @mousemove="isMagnetic() && onMove($event)"
    @mouseleave="isMagnetic() && onLeave()"
  >
    <span v-if="isMagnetic()" class="magnetic-light absolute inset-0 rounded-[inherit] pointer-events-none" aria-hidden="true" />
    <Loader2 v-if="loading" class="w-4 h-4 animate-spin-dot" />
    <slot v-else name="icon" />
    <slot />
  </button>
</template>
