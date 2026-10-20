<!--
  ABTest — A/B 实验对比（CSAT 口径）
  数据流：GET /ab-test/stats → {experiment:{id,name,variant_a,variant_b},
         variants:[{variant,label,n,avg,csat_pct,dist}]}
  指标：csat_pct = top-2-box（4-5 星占比，行业口径）+ 均分 + 1-5 分布；
        胜出判定看 csat_pct，但任一组样本 < 3 只提示"样本不足"不下结论
  视觉：实验配置卡 + 洞察玻璃条 + 双卡片对比（均分大数字 + 分布迷你条）
        + 胜出卡片品牌光晕 + trophy
-->
<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import { Trophy, Users, Star, TrendingUp, FlaskConical, Lightbulb, MessageSquareQuote } from 'lucide-vue-next'
import api from '../../api'
import AppCard from '../../components/ui/AppCard.vue'
import AppBadge from '../../components/ui/AppBadge.vue'
import AppSkeleton from '../../components/ui/AppSkeleton.vue'
import StarRating from '../../components/ui/StarRating.vue'
import PageHero from '../../components/layout/PageHero.vue'

const data = ref(null) // {experiment, variants}
const loading = ref(true)
const barReady = ref(false)

const MIN_N = 3 // 样本量护栏：demo 只有 8 个用户，每组满 3 条评分才下结论

const experiment = computed(() => data.value?.experiment)
const variants = computed(() => data.value?.variants || [])

const enough = computed(() => variants.value.length === 2 && variants.value.every((v) => v.n >= MIN_N))
const winner = computed(() => {
  if (!enough.value) return null
  const [a, b] = variants.value
  if (a.csat_pct === b.csat_pct) return null
  return a.csat_pct > b.csat_pct ? a : b
})

const totalCount = computed(() => variants.value.reduce((s, v) => s + v.n, 0))
const overallAvg = computed(() => {
  const rated = variants.value.filter((v) => v.avg != null)
  const n = rated.reduce((s, v) => s + v.n, 0)
  if (!n) return null
  return (rated.reduce((s, v) => s + v.avg * v.n, 0) / n).toFixed(2)
})
const top2Gap = computed(() => {
  if (variants.value.length < 2) return 0
  const pcts = variants.value.map((v) => v.csat_pct)
  return (Math.max(...pcts) - Math.min(...pcts)).toFixed(1)
})

const summary = computed(() => [
  { label: '评分总数', value: totalCount.value, icon: MessageSquareQuote, tone: 'text-ink-2', bg: 'bg-surface-2' },
  { label: '总体均分', value: overallAvg.value ?? '—', icon: Star, tone: 'text-amber', bg: 'bg-amber-soft' },
  { label: 'top-2-box 差', value: `${top2Gap.value}%`, icon: TrendingUp, tone: 'text-ai', bg: 'bg-ai-soft' },
])

const variantStyle = (v) =>
  v === 'A'
    ? { chip: 'bg-blue-soft text-blue border-blue/25', bar: 'bg-blue' }
    : { chip: 'bg-ai-soft text-ai border-ai/25', bar: 'bg-ai' }

// 迷你分布条：以该组最高一格做参照，条长按比例
const distMax = (v) => Math.max(1, ...Object.values(v.dist || {}))
// 分布从 5 星排到 1 星（好的在上面）
const distRows = (v) => [5, 4, 3, 2, 1].map((score) => ({ score, n: v.dist?.[score] || 0 }))

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/ab-test/stats')
    data.value = res.data
    await nextTick()
    setTimeout(() => { barReady.value = true }, 80)
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHero
      title="A/B 测试"
      :subtitle="experiment ? `实验：${experiment.name} · 工单 CSAT 满意度对比` : '实验指标对比'"
      accent="ai"
    />

    <AppSkeleton v-if="loading" variant="card" />

    <template v-else>
      <!-- 实验配置卡：A/B 组分别是什么方案，数据来自 ab_experiments 表 -->
      <AppCard v-if="experiment" class="mt-4 mb-4 animate-fade-up" style="animation-delay: 20ms">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <span class="flex items-center gap-1.5 text-[13px] font-medium text-ink">
            <FlaskConical class="w-3.5 h-3.5 text-ai" />
            {{ experiment.name }}
          </span>
          <AppBadge tone="blue" size="sm" variant="outline">A · {{ experiment.variant_a }}</AppBadge>
          <AppBadge tone="ai" size="sm" variant="outline">B · {{ experiment.variant_b }}</AppBadge>
          <span class="text-[12px] text-ink-3 ml-auto tabular-nums">实验 #{{ experiment.id }}</span>
        </div>
      </AppCard>

      <!-- 洞察玻璃条 -->
      <div
        v-if="variants.length"
        class="flex items-center gap-2 mb-5 p-3 rounded-card bg-glass backdrop-blur-md border border-line animate-fade-up overflow-x-auto"
        style="animation-delay: 40ms"
      >
        <div
          v-for="(s, i) in summary"
          :key="s.label"
          class="flex items-center gap-2.5 px-3.5 py-2 rounded-ctl shrink-0"
          :class="i < summary.length - 1 ? 'border-r border-line' : ''"
        >
          <span class="w-7 h-7 rounded-[8px] flex items-center justify-center" :class="s.bg">
            <component :is="s.icon" class="w-3.5 h-3.5" :class="s.tone" :stroke-width="2" />
          </span>
          <div>
            <p class="text-[15px] font-bold text-ink leading-none tabular-nums">{{ s.value }}</p>
            <p class="text-[11px] text-ink-3 mt-0.5">{{ s.label }}</p>
          </div>
        </div>
        <!-- 胜出 / 样本不足 二选一提示 -->
        <div v-if="winner" class="flex items-center gap-2 px-3.5 py-2 ml-auto shrink-0">
          <Trophy class="w-4 h-4 text-amber" />
          <span class="text-[13px] font-medium text-ink">当前领先：{{ winner.label }}</span>
        </div>
        <div v-else class="flex items-center gap-2 px-3.5 py-2 ml-auto shrink-0">
          <Users class="w-4 h-4 text-ink-3" />
          <span class="text-[13px] text-ink-3">样本不足（每组需 ≥{{ MIN_N }} 条评分），结论仅供参考</span>
        </div>
      </div>

      <!-- 双卡片对比 -->
      <div class="grid sm:grid-cols-2 gap-4">
        <AppCard
          v-for="s in variants"
          :key="s.variant"
          class="relative overflow-hidden animate-rise"
          :class="winner?.variant === s.variant ? 'border-brand/40 shadow-[0_0_32px_-12px_var(--brand-glow)]' : ''"
        >
          <!-- 胜出光晕 -->
          <div
            v-if="winner?.variant === s.variant"
            class="absolute -top-16 -right-16 w-40 h-40 rounded-full bg-brand/10 blur-3xl pointer-events-none"
          />

          <div class="relative flex items-center justify-between mb-4">
            <span
              class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border text-[12px] font-semibold"
              :class="variantStyle(s.variant).chip"
            >{{ s.label }}</span>
            <Trophy v-if="winner?.variant === s.variant" class="w-4.5 h-4.5 text-amber animate-pop" />
          </div>

          <!-- 均分大数字 + top-2-box -->
          <div class="grid grid-cols-2 gap-3 mb-5">
            <div>
              <p class="text-[11px] text-ink-3">均分</p>
              <p class="text-3xl font-bold text-ink tabular-nums mt-0.5 leading-none">
                {{ s.avg ?? '—' }}<span class="text-base font-medium text-ink-3"> 星</span>
              </p>
              <div class="mt-1.5">
                <StarRating :model-value="Math.round(s.avg || 0)" readonly size="sm" />
              </div>
            </div>
            <div class="text-right">
              <p class="text-[11px] text-ink-3">top-2-box（4-5 星）</p>
              <p class="text-3xl font-bold tabular-nums mt-0.5 leading-none" :class="winner?.variant === s.variant ? 'text-brand' : 'text-ink'">
                {{ s.csat_pct }}<span class="text-base font-medium text-ink-3">%</span>
              </p>
              <p class="text-[11px] text-ink-3 mt-1.5 tabular-nums">{{ s.n }} 条评分</p>
            </div>
          </div>

          <!-- top-2-box 条 -->
          <div class="mb-4">
            <div class="h-2 rounded-full bg-surface-2 overflow-hidden">
              <div
                class="h-full rounded-full transition-[width] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
                :class="variantStyle(s.variant).bar"
                :style="{ width: barReady ? `${s.csat_pct}%` : '0%' }"
              />
            </div>
          </div>

          <!-- 1-5 分布迷你条 -->
          <div class="space-y-1.5">
            <p class="text-[11px] text-ink-3 mb-1">评分分布</p>
            <div v-for="row in distRows(s)" :key="row.score" class="flex items-center gap-2">
              <span class="w-6 text-[11px] text-ink-3 tabular-nums text-right shrink-0">{{ row.score }}★</span>
              <div class="flex-1 h-1.5 rounded-full bg-surface-2 overflow-hidden">
                <div
                  class="h-full rounded-full transition-[width] duration-700 ease-[cubic-bezier(0.16,1,0.3,1)]"
                  :class="variantStyle(s.variant).bar"
                  :style="{ width: barReady ? `${(row.n / distMax(s)) * 100}%` : '0%' }"
                />
              </div>
              <span class="w-5 text-[11px] text-ink-2 tabular-nums shrink-0">{{ row.n }}</span>
            </div>
          </div>
        </AppCard>
      </div>

      <!-- 实验说明 -->
      <AppCard class="mt-4 animate-rise" style="animation-delay: 120ms">
        <div class="flex items-start gap-3">
          <span class="w-8 h-8 rounded-[10px] bg-brand-soft flex items-center justify-center shrink-0 mt-0.5">
            <Lightbulb class="w-4 h-4 text-brand" :stroke-width="2" />
          </span>
          <div class="min-w-0">
            <p class="flex items-center gap-1.5 text-[13px] font-medium text-ink">
              实验说明
              <AppBadge tone="ai" size="sm" variant="outline">
                <FlaskConical class="w-2.5 h-2.5" />
                检索策略
              </AppBadge>
            </p>
            <p class="text-[13px] text-ink-2 mt-1.5 leading-relaxed">
              工单解决后由提交人打 1-5 星（一单一评）。B 组在知识库检索时多捞 2 条候选，理论上引用更全、回答更准。
              csat_pct 按行业口径取 top-2-box（4-5 星占比）；每条评分按打分人所在分组归组。
              已知混淆：聊天答案缓存命中会发生在分组逻辑之前，缓存命中的请求不走实验——demo 环境可接受。
            </p>
          </div>
        </div>
      </AppCard>
    </template>
  </div>
</template>
