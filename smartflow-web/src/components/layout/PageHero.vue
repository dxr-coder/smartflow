<!--
  PageHero — 页面头部英雄区（工单/转接/管理共用）
  视觉：锥形渐变描边氛围带 + mesh-drift 呼吸网格 + 错峰入场；标题 gradient-text 可选
  数据流：纯展示组件，props 传 title/subtitle/count/badge，slot 扩展右侧操作
-->
<script setup>
defineProps({
  title: { type: String, required: true },
  subtitle: { type: String, default: '' },
  count: { type: [Number, String], default: '' },
  accent: { type: String, default: 'brand' }, // brand | ai | blue
})

const accentGlow = {
  brand: 'var(--brand-glow)',
  ai: 'var(--ai-glow)',
  blue: 'rgba(56,189,248,0.35)',
}
const accentDot = {
  brand: 'var(--brand)',
  ai: 'var(--ai)',
  blue: '#38bdf8',
}
</script>

<template>
  <div class="relative rounded-lg overflow-hidden mb-6 animate-rise" style="animation-delay: 0ms">
    <!-- 旋转锥形描边（弱化版） -->
    <div class="absolute inset-[-120%] animate-conic-spin opacity-40" style="background: conic-gradient(from 0deg, transparent 0%, var(--brand) 12%, var(--ai) 28%, transparent 48%, transparent 100%)" aria-hidden="true" />
    <div class="relative m-px rounded-lg bg-surface/90 backdrop-blur-sm h-[calc(100%-2px)] overflow-hidden">
      <!-- mesh 呼吸底 -->
      <div
        class="absolute inset-0 opacity-40 animate-mesh-drift"
        style="background: radial-gradient(100% 80% at 5% 0%, var(--brand-soft) 0%, transparent 55%), radial-gradient(80% 70% at 98% 100%, var(--ai-soft) 0%, transparent 50%); background-size: 150% 150%"
        aria-hidden="true"
      />
      <!-- 漂浮微粒 -->
      <span
        v-for="n in 4"
        :key="n"
        class="absolute w-[3px] h-[3px] rounded-full animate-float"
        :style="{
          left: (n * 23 + 11) % 90 + '%',
          top: (n * 19 + 17) % 70 + '%',
          background: accentDot[accent],
          opacity: 0.25 + (n % 3) * 0.08,
          animationDelay: (-n * 1.7) + 's',
          animationDuration: (6 + (n % 4) * 2) + 's',
        }"
        aria-hidden="true"
      />

      <div class="relative flex flex-wrap items-end justify-between gap-4 px-5 sm:px-7 py-5 sm:py-6">
        <div class="min-w-0">
          <h1 class="text-[22px] sm:text-[26px] font-semibold text-ink tracking-tight leading-tight">{{ title }}</h1>
          <p v-if="subtitle" class="text-[13px] text-ink-3 mt-1 leading-relaxed">{{ subtitle }}</p>
        </div>
        <div class="flex items-center gap-3 shrink-0">
          <span
            v-if="count !== ''"
            class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[12px] font-medium tabular-nums"
            :class="accent === 'ai' ? 'bg-ai-soft/60 border-ai/25 text-ai' : 'bg-brand-soft/60 border-brand/25 text-brand'"
          >
            <span
              class="relative flex w-1.5 h-1.5"
            >
              <span class="absolute inline-flex w-full h-full rounded-full opacity-60 animate-ping" :style="{ background: accentDot[accent] }" />
              <span class="relative inline-flex w-1.5 h-1.5 rounded-full" :style="{ background: accentDot[accent] }" />
            </span>
            {{ count }}
          </span>
          <slot />
        </div>
      </div>
    </div>
  </div>
</template>
