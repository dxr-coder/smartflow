<!--
  AppDrawer — 抽屉
  side: left/right/bottom；v-model；遮罩点击关闭
-->
<script setup>
defineProps({
  modelValue: Boolean,
  side: { type: String, default: 'left' },
})
const emit = defineEmits(['update:modelValue'])
const close = () => emit('update:modelValue', false)

const panelPos = {
  left: 'left-0 top-0 h-full',
  right: 'right-0 top-0 h-full',
  bottom: 'bottom-0 left-0 w-full',
}
const enterFrom = {
  left: 'enter-from -translate-x-full',
  right: 'enter-from translate-x-full',
  bottom: 'enter-from translate-y-full',
}
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200"
      enter-from-class="opacity-0"
      leave-active-class="transition-opacity duration-150"
      leave-to-class="opacity-0"
    >
      <div v-if="modelValue" class="fixed inset-0 z-[90] bg-black/55 backdrop-blur-sm" @click="close" />
    </Transition>
    <Transition
      enter-active-class="transition-transform duration-[260ms] ease-out"
      :enter-from="enterFrom[side]"
      leave-active-class="transition-transform duration-200 ease-in"
      :leave-to="enterFrom[side]"
    >
      <div
        v-if="modelValue"
        class="fixed z-[95] bg-surface border-line shadow-[var(--shadow-pop)]"
        :class="[
          panelPos[side],
          side === 'bottom' ? 'border-t rounded-t-lg max-h-[85vh]' : 'w-72 border-r',
        ]"
      >
        <slot :close="close" />
      </div>
    </Transition>
  </Teleport>
</template>
