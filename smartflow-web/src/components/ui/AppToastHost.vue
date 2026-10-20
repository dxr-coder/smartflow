<!--
  AppToastHost — Toast 容器（右上角，玻璃底）
-->
<script setup>
import { CheckCircle2, XCircle, Info, X } from 'lucide-vue-next'
import { useToast } from '../../composables/useToast'

const { toasts, dismiss } = useToast()

const icons = { success: CheckCircle2, error: XCircle, info: Info }
const tones = {
  success: 'text-brand border-brand/30',
  error: 'text-red border-red/30',
  info: 'text-blue border-blue/30',
}
</script>

<template>
  <Teleport to="body">
    <div class="fixed top-4 right-4 z-[200] flex flex-col gap-2 w-[320px] max-w-[calc(100vw-2rem)]">
      <TransitionGroup
        enter-active-class="transition-all duration-250 ease-out"
        enter-from-class="opacity-0 -translate-y-2 scale-95"
        leave-active-class="transition-all duration-200 ease-in"
        leave-to-class="opacity-0 translate-x-4"
        move-class="transition-all duration-250"
      >
        <div
          v-for="t in toasts"
          :key="t.id"
          class="flex items-start gap-2.5 bg-glass backdrop-blur-xl border rounded-card px-4 py-3 shadow-[var(--shadow-pop)]"
          :class="tones[t.type]"
        >
          <component :is="icons[t.type] || Info" class="w-4.5 h-4.5 shrink-0 mt-px" />
          <p class="flex-1 text-[13px] text-ink leading-snug">{{ t.message }}</p>
          <button class="p-0.5 rounded text-ink-3 hover:text-ink transition-colors" @click="dismiss(t.id)">
            <X class="w-3.5 h-3.5" />
          </button>
        </div>
      </TransitionGroup>
    </div>
  </Teleport>
</template>
