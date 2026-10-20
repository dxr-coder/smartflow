<!--
  AppModal — 居中弹窗
  v-model；Teleport 到 body；Esc/遮罩关闭；body 滚动锁
-->
<script setup>
import { watch } from 'vue'
import { X } from 'lucide-vue-next'

const props = defineProps({
  modelValue: Boolean,
  title: { type: String, default: '' },
  size: { type: String, default: 'md' },
  closeOnBackdrop: { type: Boolean, default: true },
})
const emit = defineEmits(['update:modelValue'])

const close = () => emit('update:modelValue', false)

watch(
  () => props.modelValue,
  (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
  }
)

const sizes = { sm: 'max-w-sm', md: 'max-w-md', lg: 'max-w-xl' }
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-opacity duration-150"
      leave-to-class="opacity-0"
    >
      <div
        v-if="modelValue"
        class="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/55 backdrop-blur-sm"
        @click.self="closeOnBackdrop && close()"
        @keydown.esc="close"
      >
        <Transition
          appear
          enter-active-class="transition-all duration-200 ease-out"
          enter-from-class="opacity-0 scale-95 translate-y-2"
          leave-active-class="transition-all duration-150 ease-in"
          leave-to-class="opacity-0 scale-95"
        >
          <div
            class="bg-surface-3 border border-line-2 rounded-lg shadow-[var(--shadow-pop)] w-full"
            :class="sizes[size]"
          >
            <div v-if="title || $slots.header" class="flex items-center justify-between px-5 py-4 border-b border-line">
              <slot name="header">
                <h3 class="text-[15px] font-semibold text-ink">{{ title }}</h3>
              </slot>
              <button class="p-1.5 rounded-ctl text-ink-3 hover:text-ink hover:bg-surface-2 transition-all" @click="close">
                <X class="w-4 h-4" />
              </button>
            </div>
            <div class="px-5 py-4"><slot /></div>
            <div v-if="$slots.footer" class="px-5 py-4 border-t border-line flex justify-end gap-2">
              <slot name="footer" />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
