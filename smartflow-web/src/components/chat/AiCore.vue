<!--
  AiCore — AI 活体核心（Chat centerpiece）
  视觉：渐变球体 + 六条旋转轨道环 + 反光高光层 + 环绕卫星点
  交互：鼠标 3D 倾斜（真实 rotateX/Y 物理 + 光泽跟随）；active=流式时脉冲+转速加快
  数据流：纯视觉组件，无 API；props 控制状态
-->
<script setup>
import { ref, computed } from 'vue'
import { Sparkles } from 'lucide-vue-next'

const props = defineProps({
  active: Boolean, // 流式中
})

const scene = ref(null)
const tilting = ref(false)
const rx = ref(0)
const ry = ref(0)
const gx = ref(50)
const gy = ref(50)

const reduced = computed(
  () => typeof window !== 'undefined'
    && window.matchMedia('(prefers-reduced-motion: reduce)').matches,
)

const onMove = (e) => {
  if (reduced.value) return
  const el = scene.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const px = (e.clientX - r.left) / r.width
  const py = (e.clientY - r.top) / r.height
  ry.value = (px - 0.5) * 26 // 左右倾斜
  rx.value = (0.5 - py) * 26 // 上下倾斜
  gx.value = px * 100
  gy.value = py * 100
  tilting.value = true
}

const onLeave = () => {
  rx.value = 0
  ry.value = 0
  gx.value = 50
  gy.value = 50
  tilting.value = false
}
</script>

<template>
  <div
    ref="scene"
    class="tilt-scene ai-core relative select-none"
    @mousemove="onMove"
    @mouseleave="onLeave"
  >
    <!-- 环境光晕（脉冲时呼吸） -->
    <div
      class="absolute inset-[-22%] rounded-full blur-[90px] transition-all duration-700"
      :class="active ? 'opacity-100 scale-110' : 'opacity-80 scale-100'"
      style="background: radial-gradient(circle, var(--ai-glow) 0%, transparent 62%)"
      aria-hidden="true"
    />

    <!-- 轨道环组（旋转） -->
    <div class="absolute inset-0 animate-orbit" :class="active ? '!duration-[4s]' : ''" aria-hidden="true">
      <div class="absolute inset-0 rounded-full border-2 border-ai/40" />
      <span class="absolute left-1/2 -top-[6px] -translate-x-1/2 w-3 h-3 rounded-full bg-ai shadow-[0_0_20px_var(--ai-glow)]" />
    </div>
    <div class="absolute inset-[8%] animate-orbit-slow" :class="active ? '!duration-[6s]' : ''" aria-hidden="true">
      <div class="absolute inset-0 rounded-full border-2 border-brand/40" />
      <span class="absolute left-1/2 -bottom-[6px] -translate-x-1/2 w-[11px] h-[11px] rounded-full bg-brand shadow-[0_0_20px_var(--brand-glow)]" />
    </div>
    <div class="absolute inset-[16%] animate-orbit" style="animation-duration: 10s" aria-hidden="true">
      <div class="absolute inset-0 rounded-full border border-ai/25 [transform:rotateX(72deg)]" />
      <span class="absolute -left-[4px] top-1/2 -translate-y-1/2 w-2 h-2 rounded-full bg-white/70" />
    </div>

    <!-- 球体（3D 倾斜主体） -->
    <div
      class="tilt-3d absolute inset-[22%] rounded-full"
      :class="{ tilting }"
      :style="{ '--rx': rx + 'deg', '--ry': ry + 'deg' }"
    >
      <!-- 反光高光层（跟随鼠标） -->
      <div class="tilt-gloss absolute inset-0 rounded-full z-20 pointer-events-none" />
      <!-- 主渐变体 -->
      <div
        class="absolute inset-0 rounded-full bg-gradient-to-br from-ai via-[#22d3ee] to-[#0e7490] transition-all duration-700"
        :class="active ? 'shadow-[0_0_90px_-2px_var(--ai-glow),0_0_180px_-30px_var(--ai-glow)] scale-105' : 'shadow-[0_0_70px_-8px_var(--ai-glow)]'"
      />
      <!-- 内层高光 -->
      <div class="absolute inset-[3%] rounded-full bg-gradient-to-br from-white/40 via-transparent to-transparent" />
      <!-- 内环结构线 -->
      <div class="absolute inset-[8%] rounded-full border-2 border-white/25" />
      <div class="absolute inset-[16%] rounded-full border border-white/15 [transform:rotateX(60deg)]" />
      <!-- 中心图标（随核心尺寸缩放） -->
      <div class="relative z-10 flex items-center justify-center w-full h-full">
        <Sparkles
          class="text-white drop-shadow-[0_4px_16px_rgba(0,0,0,0.4)] transition-all duration-500 w-[30%] h-[30%] max-w-14 max-h-14"
          :class="active ? 'scale-110 rotate-12' : ''"
          :stroke-width="1.4"
        />
      </div>
    </div>

    <!-- 流式状态：环绕能量点 -->
    <template v-if="active">
      <span class="absolute left-1/2 top-1/2 w-full h-full -translate-x-1/2 -translate-y-1/2 animate-orbit [animation-duration:2.4s]" aria-hidden="true">
        <span class="absolute left-1/2 -top-[6px] -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-white shadow-[0_0_12px_white]" />
      </span>
    </template>
  </div>
</template>
