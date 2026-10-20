<!--
  AppTextarea — 多行输入，自动伸缩
-->
<script setup>
import { ref, watch, nextTick } from 'vue'

const props = defineProps({
  modelValue: { type: String, default: '' },
  placeholder: { type: String, default: '' },
  label: { type: String, default: '' },
  rows: { type: Number, default: 3 },
  maxRows: { type: Number, default: 8 },
  autosize: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])
const el = ref(null)

watch(
  () => props.modelValue,
  async () => {
    if (!props.autosize) return
    await nextTick()
    const node = el.value
    if (!node) return
    node.style.height = 'auto'
    const lh = parseFloat(getComputedStyle(node).lineHeight) || 21
    node.style.height = Math.min(node.scrollHeight, lh * props.maxRows + 24) + 'px'
  }
)
</script>

<template>
  <div class="w-full">
    <label v-if="label" class="block text-[13px] font-medium text-ink-2 mb-1.5">{{ label }}</label>
    <textarea
      ref="el"
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      class="w-full bg-surface-2 border border-line rounded-ctl px-3.5 py-2.5 text-sm text-ink placeholder:text-ink-3 outline-none resize-none leading-[1.6] transition-all duration-150 focus:border-brand/60 focus:ring-2 focus:ring-brand/15 focus:bg-surface"
      @input="emit('update:modelValue', $event.target.value)"
    />
  </div>
</template>
