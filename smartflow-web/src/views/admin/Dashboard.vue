<!--
  Dashboard — 数据概览（bento 布局）
  数据流：GET /stats/overview（英雄指标 + 统计卡 + GSAP 数字跳动）；GET /stats/trends?days=7（ECharts 折线）
  主题：watch(isDark) 时重渲染图表配色；英雄卡 = 锥形渐变描边 + 渐变网格呼吸背景
-->
<script setup>
import { ref, onMounted, onUnmounted, watch, computed, nextTick } from 'vue'
import { MessageSquare, Ticket, Users, FileText, Activity, TrendingUp } from 'lucide-vue-next'
import * as echarts from 'echarts'
import api from '../../api'
import { useTheme } from '../../composables/useTheme'
import AppSkeleton from '../../components/ui/AppSkeleton.vue'
import AppTabs from '../../components/ui/AppTabs.vue'

const { isLight } = useTheme()
const isDark = computed(() => !isLight.value)

const overview = ref(null)
const trends = ref(null)
const loading = ref(true)
const trendDays = ref(7)
const chartRef = ref(null)
let chart = null

const dayOptions = [
  { value: 7, label: '7 天' },
  { value: 14, label: '14 天' },
  { value: 30, label: '30 天' },
]

const todayLabel = new Date().toLocaleDateString('zh-CN', { month: 'long', day: 'numeric', weekday: 'long' })

// 前 4 张进 bento 右侧小格，后 2 张整行宽卡
const statCards = computed(() => {
  const o = overview.value
  if (!o) return []
  return [
    { key: 'total_conversations', label: '总会话数', value: o.total_conversations, icon: MessageSquare, tone: 'brand' },
    { key: 'today_conversations', label: '今日会话', value: o.today_conversations, icon: Activity, tone: 'blue' },
    { key: 'total_tickets', label: '总工单', value: o.total_tickets, icon: Ticket, tone: 'amber' },
    { key: 'today_tickets', label: '今日工单', value: o.today_tickets, icon: Ticket, tone: 'rose' },
    { key: 'total_users', label: '用户数', value: o.total_users, icon: Users, tone: 'ai' },
    { key: 'total_documents', label: '知识库文档', value: o.total_documents, icon: FileText, tone: 'brand' },
  ]
})

const toneStyles = {
  brand: 'bg-brand-soft text-brand border-brand/20',
  blue: 'bg-blue-soft text-blue border-blue/20',
  amber: 'bg-amber-soft text-amber border-amber/20',
  rose: 'bg-rose/10 text-rose border-rose/20',
  ai: 'bg-ai-soft text-ai border-ai/20',
}

// GSAP 数字跳动（尊重 reduced-motion）
const animateCounters = async () => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const { gsap } = await import('gsap')
  document.querySelectorAll('[data-count]').forEach((el) => {
    const target = Number(el.dataset.count) || 0
    const obj = { v: 0 }
    gsap.to(obj, {
      v: target,
      duration: 0.9,
      ease: 'power3.out',
      onUpdate: () => { el.textContent = Math.round(obj.v) },
    })
  })
}

const load = async () => {
  loading.value = true
  try {
    const [ov, tr] = await Promise.all([
      api.get('/stats/overview'),
      api.get('/stats/trends', { params: { days: trendDays.value } }),
    ])
    overview.value = ov.data
    trends.value = tr.data
    // 等 v-else 分支（bento 网格 + 图表容器）挂载后再跑动画/初始化图表
    loading.value = false
    await nextTick()
    await animateCounters()
    renderChart()
  } catch (e) {
    /* toast 由全局 handler 处理 */
  } finally {
    loading.value = false
  }
}

const renderChart = () => {
  if (!chartRef.value || !trends.value) return
  if (!chart) chart = echarts.init(chartRef.value)
  const t = trends.value
  const ink2 = isDark.value ? '#9b9ba5' : '#4e4e5c'
  const line = isDark.value ? '#222228' : '#e4e4ec'
  const brand = isDark.value ? '#818cf8' : '#4f46e5'
  const ai = isDark.value ? '#22d3ee' : '#0891b2'

  chart.setOption({
    backgroundColor: 'transparent',
    grid: { left: 8, right: 8, top: 24, bottom: 8, containLabel: true },
    tooltip: {
      trigger: 'axis',
      backgroundColor: isDark.value ? '#1a1a21' : '#fff',
      borderColor: line,
      textStyle: { color: isDark.value ? '#f0f0f3' : '#0e0e14', fontSize: 12 },
    },
    legend: {
      data: ['会话', '工单'],
      right: 0,
      top: 0,
      textStyle: { color: ink2, fontSize: 11 },
      itemWidth: 12,
      itemHeight: 2,
      icon: 'rect',
    },
    xAxis: {
      type: 'category',
      data: t.dates,
      axisLine: { lineStyle: { color: line } },
      axisTick: { show: false },
      axisLabel: { color: ink2, fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      splitLine: { lineStyle: { color: line } },
      axisLabel: { color: ink2, fontSize: 11 },
    },
    series: [
      {
        name: '会话',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: brand, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: isDark.value ? 'rgba(129,140,248,0.18)' : 'rgba(79,70,229,0.12)' },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ]),
        },
        data: t.conversations,
      },
      {
        name: '工单',
        type: 'line',
        smooth: true,
        symbol: 'none',
        lineStyle: { color: ai, width: 2 },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: isDark.value ? 'rgba(34,211,238,0.14)' : 'rgba(8,145,178,0.1)' },
            { offset: 1, color: 'rgba(0,0,0,0)' },
          ]),
        },
        data: t.tickets,
      },
    ],
  })
}

// 暗色切换 → 重渲染配色
watch(isDark, () => renderChart())
watch(trendDays, load)

const onResize = () => chart?.resize()

// 英雄卡 3D 倾斜（reduced-motion 降级）
const heroRef = ref(null)
const heroTilt = ref(false)
const heroRx = ref(0)
const heroRy = ref(0)
const heroGx = ref(50)
const heroGy = ref(50)
const onHeroMove = (e) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const el = heroRef.value
  if (!el) return
  const r = el.getBoundingClientRect()
  const px = (e.clientX - r.left) / r.width
  const py = (e.clientY - r.top) / r.height
  heroRy.value = (px - 0.5) * 5
  heroRx.value = (0.5 - py) * 5
  heroGx.value = px * 100
  heroGy.value = py * 100
  heroTilt.value = true
}
const onHeroLeave = () => {
  heroRx.value = 0
  heroRy.value = 0
  heroTilt.value = false
}

onMounted(() => {
  load()
  window.addEventListener('resize', onResize)
})
onUnmounted(() => {
  window.removeEventListener('resize', onResize)
  chart?.dispose()
  chart = null
})
</script>

<template>
  <div>
    <div class="flex items-start justify-between gap-4 mb-6">
      <div>
        <div class="flex items-center gap-2.5">
          <h1 class="text-2xl font-semibold text-ink tracking-tight">概览</h1>
          <span class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-brand-soft border border-brand/20 text-[11px] font-medium text-brand">
            <span class="relative flex w-1.5 h-1.5">
              <span class="absolute inline-flex w-full h-full rounded-full bg-brand opacity-60 animate-ping"></span>
              <span class="relative inline-flex w-1.5 h-1.5 rounded-full bg-brand"></span>
            </span>
            实时
          </span>
        </div>
        <p class="text-[13px] text-ink-3 mt-1">{{ todayLabel }} · 平台运行数据一览</p>
      </div>
    </div>

    <!-- Bento 网格：英雄指标（2×2）+ 小统计卡 -->
    <div v-if="loading" class="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      <AppSkeleton v-for="i in 7" :key="i" variant="card" :class="i === 1 ? 'col-span-2 row-span-2 h-64' : ''" />
    </div>
    <div v-else class="tilt-scene grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
      <!-- 英雄卡：AI 独立解决率（锥形渐变描边 + 呼吸网格 + 3D 倾斜） -->
      <div
        ref="heroRef"
        class="tilt-3d relative col-span-2 row-span-2 rounded-lg overflow-hidden animate-rise"
        :class="{ tilting: heroTilt }"
        :style="{ '--rx': heroRx + 'deg', '--ry': heroRy + 'deg', animationDelay: '0ms' }"
        @mousemove="onHeroMove"
        @mouseleave="onHeroLeave"
      >
        <!-- 旋转锥形描边 -->
        <div class="absolute inset-[-80%] animate-conic-spin opacity-60" style="background: conic-gradient(from 0deg, transparent 0%, var(--brand) 18%, var(--ai) 38%, transparent 55%, transparent 100%)" aria-hidden="true" />
        <div class="relative m-px rounded-lg bg-surface h-[calc(100%-2px)] overflow-hidden">
          <!-- 光泽跟随层 -->
          <div
            class="tilt-gloss absolute inset-0 z-10 pointer-events-none"
            :style="{ '--gx': heroGx + '%', '--gy': heroGy + '%' }"
            aria-hidden="true"
          />
          <!-- 渐变网格呼吸背景 -->
          <div
            class="absolute inset-0 opacity-[0.55] animate-mesh-drift"
            style="background: radial-gradient(120% 90% at 8% 0%, var(--brand-soft) 0%, transparent 52%), radial-gradient(90% 80% at 95% 100%, var(--ai-soft) 0%, transparent 50%); background-size: 160% 160%"
            aria-hidden="true"
          />
          <div class="relative flex flex-col sm:flex-row items-center gap-6 p-6 h-full">
            <!-- 大圆环 -->
            <div class="relative w-28 h-28 shrink-0">
              <svg viewBox="0 0 36 36" class="w-full h-full -rotate-90">
                <circle cx="18" cy="18" r="15.5" fill="none" stroke="var(--line)" stroke-width="2.5" />
                <circle
                  cx="18" cy="18" r="15.5" fill="none"
                  :stroke="isDark ? '#818cf8' : '#4f46e5'"
                  stroke-width="2.5" stroke-linecap="round"
                  :stroke-dasharray="`${(overview.ai_resolve_rate || 0) * 0.974} 97.4`"
                  class="transition-all duration-1000"
                />
              </svg>
              <span class="absolute inset-0 flex items-center justify-center text-[11px] font-medium uppercase tracking-wider text-ink-3">解决率</span>
            </div>
            <div class="text-center sm:text-left">
              <p class="text-[12px] font-medium uppercase tracking-wider text-ink-3 flex items-center gap-1.5 justify-center sm:justify-start">
                <TrendingUp class="w-3.5 h-3.5 text-brand" />
                AI 独立解决率
              </p>
              <p class="mt-2 text-[44px] leading-none font-bold text-ink tabular-nums tracking-tight" :data-count="Math.round((overview.ai_resolve_rate || 0) * 100)">
                0<span class="text-[24px] text-ink-2">%</span>
              </p>
              <p class="text-[12px] text-ink-3 mt-2.5 max-w-[240px] leading-relaxed">无需人工介入即完成闭环的会话占比，衡量自动化处理能力</p>
            </div>
          </div>
        </div>
      </div>

      <!-- 小统计卡 ×4（bento 右侧） -->
      <div
        v-for="(s, i) in statCards.slice(0, 4)"
        :key="s.key"
        class="group relative rounded-card bg-surface border border-line p-4 hover:border-ink-3/40 hover:shadow-[var(--shadow-card)] transition-all duration-200 animate-rise"
        :style="{ animationDelay: `${80 + i * 60}ms` }"
      >
        <div class="flex items-start justify-between gap-2">
          <div class="min-w-0">
            <p class="text-[12px] text-ink-3">{{ s.label }}</p>
            <p class="mt-2 text-[26px] leading-none font-bold text-ink tabular-nums tracking-tight" :data-count="s.value">0</p>
          </div>
          <div class="w-8 h-8 rounded-[9px] border flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110" :class="toneStyles[s.tone]">
            <component :is="s.icon" class="w-[15px] h-[15px]" :stroke-width="1.8" />
          </div>
        </div>
      </div>

      <!-- 宽统计卡 ×2（整行两格） -->
      <div
        v-for="(s, i) in statCards.slice(4)"
        :key="s.key"
        class="col-span-2 group flex items-center justify-between gap-3 rounded-card bg-surface border border-line px-5 py-4 hover:border-ink-3/40 hover:shadow-[var(--shadow-card)] transition-all duration-200 animate-rise"
        :style="{ animationDelay: `${320 + i * 60}ms` }"
      >
        <div>
          <p class="text-[12px] text-ink-3">{{ s.label }}</p>
          <p class="mt-1.5 text-[28px] leading-none font-bold text-ink tabular-nums tracking-tight" :data-count="s.value">0</p>
        </div>
        <div class="w-10 h-10 rounded-[11px] border flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-110" :class="toneStyles[s.tone]">
          <component :is="s.icon" class="w-4 h-4" :stroke-width="1.8" />
        </div>
      </div>
    </div>

    <!-- 趋势图 -->
    <div class="rounded-card bg-surface border border-line p-5">
      <div class="flex items-center justify-between mb-3">
        <p class="text-sm font-medium text-ink">趋势</p>
        <AppTabs v-model="trendDays" :items="dayOptions" />
      </div>
      <AppSkeleton v-if="loading" variant="table" :rows="4" />
      <div v-else ref="chartRef" class="w-full h-64" />
    </div>
  </div>
</template>
