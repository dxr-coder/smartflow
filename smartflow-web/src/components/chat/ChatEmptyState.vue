<!--
  ChatEmptyState — 空会话欢迎区（签名画面）
  视觉：AiCore 活体核心（3D 倾斜+流式脉冲）+ 渐变大字 + 3D 倾斜玻璃建议卡 + 实验 chip
  数据流：GET /ab-test/variant（底部实验 chip，失败/未分流静默不显示）；
         emit suggest(text) 填充输入框
-->
<script setup>
import { ref, onMounted } from 'vue'
import { CalendarDays, ReceiptText, Wrench, ArrowUpRight } from 'lucide-vue-next'
import api from '../../api'
import AiCore from './AiCore.vue'

defineEmits(['suggest'])

// A/B 实验 chip：登录了才拉得到；未分流（还没聊过天）或接口挂了都静默不显示
const exp = ref(null)
onMounted(async () => {
  try {
    const res = await api.get('/ab-test/variant')
    if (res.data?.variant) exp.value = res.data
  } catch { /* 静默 */ }
})

const suggestions = [
  { text: '公司年假制度是怎样的？', desc: '查询 HR 政策与剩余额度', icon: CalendarDays, tone: 'ai' },
  { text: '帮我查一下上个月部门差旅报销进度', desc: '跟踪财务流程与报销单状态', icon: ReceiptText, tone: 'brand' },
  { text: 'VPN 连不上了，怎么排查？', desc: 'IT 故障自助诊断指引', icon: Wrench, tone: 'blue' },
]

const toneStyles = {
  ai: 'from-ai/90 to-[#0e7490] shadow-[0_8px_20px_-8px_var(--ai-glow)]',
  brand: 'from-brand/90 to-brand-strong shadow-[0_8px_20px_-8px_var(--brand-glow)]',
  blue: 'from-blue/90 to-[#0369a1] shadow-[0_8px_20px_-8px_rgba(56,189,248,0.35)]',
}

// 卡片 3D 倾斜
const cardRefs = ref([])
const tiltingIdx = ref(-1)
const onCardMove = (e, i) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const el = cardRefs.value[i]
  if (!el) return
  const r = el.getBoundingClientRect()
  const px = (e.clientX - r.left) / r.width
  const py = (e.clientY - r.top) / r.height
  el.style.setProperty('--ry', (px - 0.5) * 12 + 'deg')
  el.style.setProperty('--rx', (0.5 - py) * 12 + 'deg')
  el.style.setProperty('--gx', px * 100 + '%')
  el.style.setProperty('--gy', py * 100 + '%')
  tiltingIdx.value = i
}
const onCardLeave = (i) => {
  const el = cardRefs.value[i]
  if (!el) return
  el.style.setProperty('--rx', '0deg')
  el.style.setProperty('--ry', '0deg')
  if (tiltingIdx.value === i) tiltingIdx.value = -1
}
</script>

<template>
  <div class="relative flex flex-col items-center text-center px-4 sm:px-6 py-5 sm:py-8 min-h-full overflow-hidden">
    <!-- 背景光晕（overflow 裁剪：避免 600px 光斑撑出滚动高度） -->
    <div class="pointer-events-none absolute inset-0 overflow-hidden" aria-hidden="true">
      <div class="absolute left-1/2 top-[36%] -translate-x-1/2 -translate-y-1/2 w-[600px] h-[600px] rounded-full bg-ai/[0.08] blur-[110px] animate-pulse-soft" />
      <div class="absolute left-1/2 top-[36%] -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] rounded-full bg-brand/[0.06] blur-[95px] animate-pulse-soft" style="animation-delay: -1.2s" />
    </div>

    <div class="chat-empty-stack my-auto flex flex-col items-center w-full">
      <!-- AI 活体核心（3D 倾斜 centerpiece，尺寸随视口高度收缩） -->
      <div class="animate-fade-up shrink-0">
        <AiCore />
      </div>

      <!-- 大字标语 -->
      <h2 class="chat-empty-title animate-fade-up leading-[1.15] font-semibold tracking-tight text-ink shrink-0" style="animation-delay: 80ms">
        有什么可以帮<span class="bg-gradient-to-r from-brand via-[#8b7cf6] to-ai bg-clip-text text-transparent">你</span>？
      </h2>
      <p class="chat-empty-desc animate-fade-up text-[13px] sm:text-[14px] text-ink-2 max-w-md leading-relaxed shrink-0" style="animation-delay: 140ms">
        制度政策、工单进度、IT 排障——直接输入问题，AI 即时应答；搞不定的自动带上下文转人工。
      </p>

      <!-- 3D 倾斜玻璃建议卡 -->
      <div class="chat-empty-cards tilt-scene grid sm:grid-cols-3 w-full max-w-2xl shrink-0">
      <button
        v-for="(s, i) in suggestions"
        :key="s.text"
        :ref="(el) => (cardRefs[i] = el)"
        class="tilt-3d group relative text-left p-3 sm:p-4 rounded-card bg-glass backdrop-blur-md border border-line hover:border-ink-3/50 transition-colors duration-200 active:scale-[0.98] animate-rise overflow-hidden"
        :class="{ tilting: tiltingIdx === i }"
        :style="{ animationDelay: `${220 + i * 90}ms` }"
        @mousemove="onCardMove($event, i)"
        @mouseleave="onCardLeave(i)"
        @click="$emit('suggest', s.text)"
      >
        <span class="tilt-gloss absolute inset-0 rounded-card z-10 pointer-events-none" />
        <span class="absolute inset-x-4 -top-px h-px bg-gradient-to-r from-transparent via-ink-3/40 to-transparent opacity-0 group-hover:opacity-100 transition-opacity" />
        <span class="relative z-20 flex items-center justify-center w-8 h-8 sm:w-9 sm:h-9 rounded-[10px] bg-gradient-to-br text-white mb-2 sm:mb-3 transition-transform duration-200 group-hover:scale-110" :class="toneStyles[s.tone]">
          <component :is="s.icon" class="w-4 h-4 sm:w-[17px] sm:h-[17px]" :stroke-width="1.8" />
        </span>
        <p class="relative z-20 text-[12px] sm:text-[13px] font-medium text-ink leading-snug">{{ s.text }}</p>
        <p class="relative z-20 text-[11px] sm:text-[12px] text-ink-3 mt-0.5 sm:mt-1 leading-snug">{{ s.desc }}</p>
        <ArrowUpRight class="absolute right-3 top-3 z-20 w-3.5 h-3.5 text-ink-3 opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200" :stroke-width="2" />
      </button>
      </div>

      <!-- 实验 chip：低调展示当前用户在哪个实验组 -->
      <p
        v-if="exp"
        class="animate-fade-up text-[11px] text-ink-3 mt-4 shrink-0 tabular-nums"
        style="animation-delay: 480ms"
      >
        实验：{{ exp.name }} · {{ exp.variant }}组
      </p>
    </div>
  </div>
</template>
