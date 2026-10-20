<!--
  AppSelect — 原生 select + 自定义 chevron
  options: [{ value, label }]
-->
<script setup>
import { ChevronDown } from 'lucide-vue-next'

defineProps({
  modelValue: { type: [String, Number], default: '' },
  options: { type: Array, default: () => [] },
  size: { type: String, default: 'md' },
  disabled: Boolean,
})
defineEmits(['update:modelValue'])

const sizes = { sm: 'h-8 pl-2.5 pr-8 text-[13px]', md: 'h-9.5 pl-3 pr-9 text-sm' }
</script>

<template>
  <div class="relative inline-flex w-full">
    <select
      :value="modelValue"
      :disabled="disabled"
      class="w-full appearance-none bg-surface-2 border border-line rounded-ctl text-ink outline-none cursor-pointer transition-all duration-150 hover:border-line-2 focus:border-brand/60 focus:ring-2 focus:ring-brand/15 disabled:opacity-50 disabled:cursor-not-allowed"
      :class="sizes[size]"
      @change="$emit('update:modelValue', $event.target.value)"
    >
      <option v-for="opt in options" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
    </select>
    <ChevronDown class="w-3.5 h-3.5 text-ink-3 absolute right-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
  </div>
</template>
