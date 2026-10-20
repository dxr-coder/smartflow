<!--
  AppTabs — 标签页切换
  items: [{ value, label, icon? }]；v-model；pill 胶囊滑块 / underline 下划线
-->
<script setup>
import { ref, watch, onMounted, nextTick } from 'vue'

const props = defineProps({
  items: { type: Array, required: true },
  modelValue: { type: [String, Number], default: '' },
  variant: { type: String, default: 'pill' },
})
const emit = defineEmits(['update:modelValue'])

const rootRef = ref(null)
const indicatorStyle = ref({})

const updateIndicator = async () => {
  if (props.variant !== 'pill') return
  await nextTick()
  const root = rootRef.value
  if (!root) return
  const active = root.querySelector('[data-active="true"]')
  if (!active) { indicatorStyle.value = { opacity: 0 }; return }
  indicatorStyle.value = {
    left: active.offsetLeft + 'px',
    width: active.offsetWidth + 'px',
    opacity: 1,
  }
}

watch(() => props.modelValue, updateIndicator)
onMounted(() => {
  updateIndicator()
  window.addEventListener('resize', updateIndicator)
})
</script>

<template>
  <div
    ref="rootRef"
    class="relative inline-flex items-center gap-0.5 p-1 bg-surface-2 border border-line rounded-ctl overflow-x-auto max-w-full"
    :class="variant === 'underline' ? 'bg-transparent border-0 border-b border-line rounded-none p-0' : ''"
  >
    <div
      v-if="variant === 'pill'"
      class="absolute top-1 bottom-1 bg-surface-3 border border-line rounded-[8px] transition-all duration-250 shadow-[var(--shadow-card)]"
      :style="indicatorStyle"
    />
    <button
      v-for="item in items"
      :key="item.value"
      :data-active="modelValue === item.value"
      class="relative z-10 inline-flex items-center gap-1.5 px-3 h-8 text-[13px] font-medium whitespace-nowrap transition-colors duration-150 rounded-[8px]"
      :class="
        modelValue === item.value
          ? variant === 'pill' ? 'text-ink' : 'text-brand border-b-2 border-brand -mb-px rounded-none'
          : 'text-ink-3 hover:text-ink-2'
      "
      @click="emit('update:modelValue', item.value)"
    >
      <component :is="item.icon" v-if="item.icon" class="w-3.5 h-3.5" />
      {{ item.label }}
    </button>
  </div>
</template>
