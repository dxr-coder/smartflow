<!--
  StarRating — 1-5 星打分
  v-model = 数字（0 表示未评）；readonly 只读展示；hover 预览打分（readonly 无预览）
  点亮的星有 pop 弹跳（style.css 的 animate-pop）+ 悬停放大
-->
<script setup>
import { ref } from 'vue'
import { Star } from 'lucide-vue-next'

const props = defineProps({
  modelValue: { type: Number, default: 0 },
  readonly: Boolean,
  size: { type: String, default: 'md' },
})
const emit = defineEmits(['update:modelValue'])

const hover = ref(0) // 鼠标悬停到第几颗星，0 = 没悬停
const filled = (n) => n <= (hover.value || props.modelValue)

const pick = (n) => {
  if (props.readonly) return
  emit('update:modelValue', n)
}

const sizes = { sm: 'w-4 h-4', md: 'w-5 h-5', lg: 'w-8 h-8' }
</script>

<template>
  <div class="inline-flex items-center gap-0.5" :class="readonly ? '' : 'cursor-pointer'">
    <button
      v-for="n in 5"
      :key="n"
      type="button"
      class="transition-all duration-150"
      :class="[
        sizes[size],
        filled(n) ? 'text-amber' : 'text-ink-3',
        !readonly && hover === n ? 'scale-125' : 'scale-100',
      ]"
      :disabled="readonly"
      @mouseenter="!readonly && (hover = n)"
      @mouseleave="hover = 0"
      @click="pick(n)"
    >
      <Star
        class="w-full h-full animate-pop"
        :fill="filled(n) ? 'currentColor' : 'none'"
        :stroke-width="1.5"
      />
    </button>
  </div>
</template>
