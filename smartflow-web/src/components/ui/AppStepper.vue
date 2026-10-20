<!--
  AppStepper — 状态流转步骤条
  steps: [{ value, label }]；current 当前值；已完成步骤间翡翠填充线动画
  语义：value === current 之前视为完成（线填充），当前步发光圆点
-->
<script setup>
import { computed } from 'vue'
import { Check } from 'lucide-vue-next'

const props = defineProps({
  steps: { type: Array, required: true },
  current: { type: String, default: '' },
})

const currentIndex = computed(() => props.steps.findIndex((s) => s.value === props.current))
</script>

<template>
  <div class="flex items-center">
    <template v-for="(step, i) in steps" :key="step.value">
      <!-- 连接线 -->
      <div
        v-if="i > 0"
        class="flex-1 h-px mx-2 relative overflow-hidden bg-line min-w-6"
      >
        <div
          class="absolute inset-0 bg-gradient-to-r from-brand to-brand-strong origin-left transition-transform duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
          :class="i <= currentIndex.value ? 'scale-x-100' : 'scale-x-0'"
        />
      </div>
      <!-- 节点 -->
      <div class="flex items-center gap-2 shrink-0">
        <div
          class="flex items-center justify-center w-6 h-6 rounded-full border transition-all duration-300"
          :class="
            i < currentIndex.value
              ? 'bg-brand border-brand text-brand-ink'
              : i === currentIndex.value
                ? 'bg-brand-soft border-brand text-brand shadow-[0_0_0_4px_var(--brand-soft)] animate-pulse-soft'
                : 'bg-surface-2 border-line text-ink-3'
          "
        >
          <Check v-if="i < currentIndex.value" class="w-3.5 h-3.5" :stroke-width="2.5" />
          <span v-else class="text-[10px] font-semibold">{{ i + 1 }}</span>
        </div>
        <span
          class="text-[13px] whitespace-nowrap"
          :class="i <= currentIndex.value ? 'text-ink font-medium' : 'text-ink-3'"
        >
          {{ step.label }}
        </span>
      </div>
    </template>
  </div>
</template>
