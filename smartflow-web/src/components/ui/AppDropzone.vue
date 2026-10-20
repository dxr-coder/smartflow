<!--
  AppDropzone — 文件拖拽上传区
  accept / maxSize(MB)；拖拽态内部管理；点击触发隐藏 input
  emits: file（选中/拖入的 File 对象）
-->
<script setup>
import { ref } from 'vue'
import { UploadCloud } from 'lucide-vue-next'
import { toast } from '../../composables/useToast'

const props = defineProps({
  accept: { type: String, default: '.pdf,.docx,.txt,.md' },
  maxSize: { type: Number, default: 20 },
  hint: { type: String, default: '' },
})
const emit = defineEmits(['file'])

const inputRef = ref(null)
const dragging = ref(false)
let dragDepth = 0

const pick = () => inputRef.value?.click()

const onDrop = (e) => {
  e.preventDefault()
  dragging.value = false
  dragDepth = 0
  const file = e.dataTransfer?.files?.[0]
  if (file) validate(file)
}

const onDragEnter = (e) => {
  e.preventDefault()
  dragDepth++
  dragging.value = true
}
const onDragLeave = () => {
  dragDepth--
  if (dragDepth <= 0) { dragging.value = false; dragDepth = 0 }
}

const onChange = (e) => {
  const file = e.target.files?.[0]
  if (file) validate(file)
  e.target.value = ''
}

const validate = (file) => {
  if (props.maxSize && file.size > props.maxSize * 1024 * 1024) {
    toast.error(`文件超过 ${props.maxSize}MB 限制`)
    return
  }
  emit('file', file)
}
</script>

<template>
  <div
    class="relative flex flex-col items-center justify-center gap-2.5 border border-dashed rounded-card cursor-pointer transition-all duration-200 select-none"
    :class="
      dragging
        ? 'border-brand bg-brand-soft scale-[1.01] shadow-[0_0_32px_-8px_var(--brand-glow)]'
        : 'border-line-2 bg-surface-2/50 hover:border-ink-3 hover:bg-surface-2'
    "
    :style="{ padding: '2.25rem 1.5rem' }"
    @click="pick"
    @dragenter="onDragEnter"
    @dragover.prevent
    @dragleave="onDragLeave"
    @drop="onDrop"
  >
    <div
      class="flex items-center justify-center w-11 h-11 rounded-full border transition-all duration-200"
      :class="dragging ? 'bg-brand/15 border-brand/40 scale-110' : 'bg-surface-2 border-line'"
    >
      <UploadCloud class="w-5 h-5 transition-colors" :class="dragging ? 'text-brand' : 'text-ink-3'" :stroke-width="1.5" />
    </div>
    <div class="text-center">
      <p class="text-sm text-ink-2">
        <span class="text-brand font-medium">点击上传</span> 或拖拽文件到此处
      </p>
      <p class="mt-1 text-xs text-ink-3">{{ hint || `支持 ${accept}，最大 ${maxSize}MB` }}</p>
    </div>
    <input ref="inputRef" type="file" class="hidden" :accept="accept" @change="onChange" />
  </div>
</template>
