<!--
  404 页 — 品牌光球 + 大号渐变数字 + 3D 倾斜 + 轨道粒子
  数据流：无 API，纯静态；点击返回 /chat
-->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowLeft, Sparkles } from 'lucide-vue-next'
import AppButton from '../components/ui/AppButton.vue'

const router = useRouter()

// 鼠标视差 + 3D 倾斜
const px = ref(0)
const py = ref(0)
const rx = ref(0)
const ry = ref(0)
const gx = ref(50)
const gy = ref(50)
const tilting = ref(false)

const onMove = (e) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const r = e.currentTarget.getBoundingClientRect()
  px.value = (e.clientX - r.left) / r.width - 0.5
  py.value = (e.clientY - r.top) / r.height - 0.5
  ry.value = px.value * 14
  rx.value = -py.value * 14
  gx.value = (px.value + 0.5) * 100
  gy.value = (py.value + 0.5) * 100
  tilting.value = true
}
const onLeave = () => {
  px.value = 0; py.value = 0
  rx.value = 0; ry.value = 0
  tilting.value = false
}
</script>

<template>
  <div
    class="tilt-scene relative min-h-dvh flex flex-col items-center justify-center overflow-hidden px-4"
    @mousemove="onMove"
    @mouseleave="onLeave"
  >
    <!-- 环境光（视差层） -->
    <div class="pointer-events-none absolute inset-0" aria-hidden="true">
      <div
        class="absolute w-[520px] h-[520px] rounded-full opacity-20 blur-[110px] animate-aurora transition-transform duration-500 ease-out"
        style="background: radial-gradient(circle, var(--brand) 0%, transparent 65%); top: 14%; left: 26%"
        :style="{ transform: `translate(${px * 36}px, ${py * 36}px)` }"
      />
      <div
        class="absolute w-[420px] h-[420px] rounded-full opacity-[0.14] blur-[100px] animate-aurora transition-transform duration-500 ease-out"
        style="background: radial-gradient(circle, var(--ai) 0%, transparent 65%); bottom: 10%; right: 22%; animation-delay: -8s"
        :style="{ transform: `translate(${px * -28}px, ${py * -28}px)` }"
      />
      <!-- 网格（近层视差） -->
      <div
        class="absolute inset-[-30px] opacity-[0.4] transition-transform duration-300 ease-out"
        style="background-image: linear-gradient(var(--line-soft) 1px, transparent 1px), linear-gradient(90deg, var(--line-soft) 1px, transparent 1px); background-size: 48px 48px"
        :style="{ transform: `translate(${px * -12}px, ${py * -12}px)` }"
      />
    </div>

    <div class="relative text-center animate-rise" :style="{ transform: `translate(${px * 10}px, ${py * 10}px)` }">
      <!-- 轨道环 + 呼吸光球 -->
      <div class="relative mx-auto mb-8 w-20 h-20" aria-hidden="true">
        <span class="absolute rounded-full bg-brand/25 blur-xl animate-pulse-soft" style="inset: -16px" />
        <span class="absolute rounded-full bg-ai/15 blur-2xl animate-pulse-soft" style="inset: -28px; animation-delay: -1.2s" />
        <!-- 轨道环 -->
        <div class="absolute inset-[-18%] animate-orbit">
          <div class="absolute inset-0 rounded-full border border-ai/35" />
          <span class="absolute left-1/2 -top-[4px] -translate-x-1/2 w-2 h-2 rounded-full bg-ai shadow-[0_0_14px_var(--ai-glow)]" />
        </div>
        <div class="absolute inset-[-6%] animate-orbit-slow">
          <div class="absolute inset-0 rounded-full border border-brand/30" />
          <span class="absolute left-1/2 -bottom-[3px] -translate-x-1/2 w-1.5 h-1.5 rounded-full bg-brand shadow-[0_0_12px_var(--brand-glow)]" />
        </div>
        <!-- 光球主体 -->
        <span class="tilt-3d relative flex w-20 h-20 items-center justify-center rounded-full bg-gradient-to-br from-brand/90 via-[#8b7cf6]/70 to-ai/80 shadow-[0_0_44px_-6px_var(--brand-glow)]" :class="{ tilting }" :style="{ '--rx': rx + 'deg', '--ry': ry + 'deg' }">
          <span class="tilt-gloss absolute inset-0 rounded-full z-10 pointer-events-none" />
          <Sparkles class="relative w-8 h-8 text-white drop-shadow-[0_4px_14px_rgba(0,0,0,0.35)]" :stroke-width="1.8" />
        </span>
      </div>

      <!-- 大号 404（渐变 + 3D 微倾） -->
      <p
        class="tilt-3d select-none tabular-nums text-[120px] sm:text-[140px] leading-none font-bold tracking-tighter bg-gradient-to-b from-ink via-ink-2 to-transparent bg-clip-text text-transparent"
        :class="{ tilting }"
        :style="{ '--rx': rx * 0.5 + 'deg', '--ry': ry * 0.5 + 'deg', transformStyle: 'preserve-3d' }"
      >
        404
      </p>
      <p class="text-ink-2 text-[15px] mt-3 max-w-xs mx-auto leading-relaxed">页面走丢了，它可能去了另一个工作流</p>
      <AppButton class="mt-8" @click="router.push('/chat')">
        <ArrowLeft class="w-4 h-4" />
        返回对话
      </AppButton>
    </div>
  </div>
</template>
