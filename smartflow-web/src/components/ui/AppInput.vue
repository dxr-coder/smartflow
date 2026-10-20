<!--
  AppInput — 输入框
  v-model；label 上置；error 红框+抖动；prefix/suffix 插槽
-->
<script setup>
defineProps({
  modelValue: { type: [String, Number], default: '' },
  type: { type: String, default: 'text' },
  placeholder: { type: String, default: '' },
  label: { type: String, default: '' },
  error: { type: String, default: '' },
  disabled: Boolean,
  size: { type: String, default: 'md' },
})
defineEmits(['update:modelValue'])
defineOptions({ inheritAttrs: false })

const sizes = {
  sm: 'h-8 px-2.5 text-[13px]',
  md: 'h-9.5 px-3.5 text-sm',
  lg: 'h-11 px-4 text-[15px]',
}
</script>

<template>
  <div class="w-full">
    <label v-if="label" class="block text-[13px] font-medium text-ink-2 mb-1.5">{{ label }}</label>
    <div
      class="relative flex items-center bg-surface-2 border rounded-ctl transition-all duration-150"
      :class="[
        error
          ? 'border-red animate-shake'
          : 'border-line focus-within:border-brand/60 focus-within:ring-2 focus-within:ring-brand/15 focus-within:bg-surface',
        disabled ? 'opacity-50 pointer-events-none' : '',
      ]"
    >
      <span v-if="$slots.prefix" class="pl-3 text-ink-3 shrink-0"><slot name="prefix" /></span>
      <input
        v-bind="$attrs"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        class="flex-1 min-w-0 bg-transparent text-ink placeholder:text-ink-3 outline-none disabled:cursor-not-allowed"
        :class="[sizes[size], $slots.prefix ? 'pl-2' : '', $slots.suffix ? 'pr-2' : '']"
        @input="$emit('update:modelValue', $event.target.value)"
      />
      <span v-if="$slots.suffix" class="pr-2.5 text-ink-3 shrink-0"><slot name="suffix" /></span>
    </div>
    <p v-if="error" class="mt-1.5 text-xs text-red">{{ error }}</p>
  </div>
</template>
