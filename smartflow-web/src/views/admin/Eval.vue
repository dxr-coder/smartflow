<!--
  Eval — RAG 评测工业化版（多标签金标 + 负例拒答 + 检索/生成双层 + A/B 配对显著性 + 分类别切片）
  数据流：GET /eval/cases（docs 数组 + is_answerable）/documents → 金标集卡；
         POST /eval/run → 检索层同步跑一轮落库（排名指标只算可回答用例，answerable_count 为分母）；
         POST /eval/run-generation → 异步 job 立即回 job_id → GET /eval/job/{id} 5s 轮询真进度；
         生成层 = 检索+生成答案+LLM-as-judge（正例 F/R 1-5；负例 refused 二分类 → refusal_rate）；
         GET /eval/runs → 历史（含 mode/refusal_rate/answerable_count）；GET /eval/runs/{id} → 逐用例明细 + slices；
         GET /eval/compare?a_id&b_id → Hit@1 精确 McNemar，分数指标（含 F/R/refusal）paired bootstrap 95% CI
  指标语义分层：Hit/MRR 对主文档与可接受文档一视同仁；NDCG@5 用 grade 线性增益区分主次；
         负例（is_answerable=0）不进排名指标分母（防稀释 hit1），只在生成层评"拒答 vs 幻觉"；
         显著性：Δ±CI 不含 0 / p<0.05 才标"显著"；CI 完全落在 0 以下 = 显著劣化应拦截（回归门禁）
  A=baseline top_k=5，B=top_k+2（离线注入 ab_variant_var ContextVar，与线上 A/B 同口径）；
  rewrite 开关=查询重写消融；对比条自动选最近一次完整 A/B 对（优先最新 mode，退回另一 mode）
  视觉：运行控制条（含 job 进度条）+ A/B 对比玻璃条（Δ±CI+显著徽章）+ 可展开历史（明细/slices/答案/评审）
       + 金标集多标签管理（含负例开关）
-->
<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {
  Target, Play, Trophy, Plus, Trash2, FileText, Lightbulb, Loader2, Sparkles, Ban,
} from 'lucide-vue-next'
import api from '../../api'
import { toast } from '../../composables/useToast'
import AppCard from '../../components/ui/AppCard.vue'
import AppBadge from '../../components/ui/AppBadge.vue'
import AppButton from '../../components/ui/AppButton.vue'
import AppInput from '../../components/ui/AppInput.vue'
import AppSelect from '../../components/ui/AppSelect.vue'
import AppTable from '../../components/ui/AppTable.vue'
import AppModal from '../../components/ui/AppModal.vue'
import AppSkeleton from '../../components/ui/AppSkeleton.vue'
import PageHero from '../../components/layout/PageHero.vue'

// ---------- 运行状态 ----------
const loading = ref(true)
const running = ref(false)
const runningPhase = ref('')
const rewriteOn = ref(false) // 查询重写消融开关：关=原话直检（基线），开=走 rewrite_query
const runs = ref([]) // GET /eval/runs，按 id 倒序
const cases = ref([])
const documents = ref([])

// ---------- 生成评测异步 job：提交后 5s 轮询，进度条来自服务端真实 done/total ----------
const genJob = ref(null) // {jobId, variant, done, total, phase}
let pollTimer = null

const pollJob = (jobId) => new Promise((resolve, reject) => {
  pollTimer = setInterval(async () => {
    try {
      const res = await api.get(`/eval/job/${jobId}`)
      const j = res.data
      genJob.value = { ...genJob.value, done: j.done, total: j.total, phase: j.phase }
      if (j.status === 'done') { clearInterval(pollTimer); resolve(j) }
      if (j.status === 'error') { clearInterval(pollTimer); reject(new Error(j.error || '任务失败')) }
    } catch (e) {
      clearInterval(pollTimer) // 404 = 服务重启任务表清空
      reject(e)
    }
  }, 5000)
})

const jobPct = computed(() => {
  if (!genJob.value?.total) return 0
  return Math.round((genJob.value.done / genJob.value.total) * 100)
})

// ---------- 对比条：最近一次完整 A/B 对（优先最新 run 的 mode，缺对则退回另一 mode） ----------
const pairOf = (mode) => {
  const pool = runs.value.filter((r) => r.mode === mode)
  if (!pool.length) return null
  const rw = Boolean(pool[0].rewrite)
  const a = pool.find((r) => r.variant === 'A' && Boolean(r.rewrite) === rw)
  const b = pool.find((r) => r.variant === 'B' && Boolean(r.rewrite) === rw)
  return a && b ? { a, b, mode } : null
}
const latest = computed(() => {
  if (!runs.value.length) return null
  const newest = runs.value[0].mode
  return pairOf(newest) || pairOf(newest === 'retrieval' ? 'generation' : 'retrieval')
})

const retrievalMetricDefs = [
  { key: 'hit1', label: 'Hit@1', hint: '首位命中' },
  { key: 'recall5', label: 'Recall@5', hint: '前5覆盖率' },
  { key: 'mrr', label: 'MRR', hint: '排序质量' },
  { key: 'ndcg5', label: 'NDCG@5', hint: '主次加权排序' },
]
// 生成层对比看"答得怎么样"：检索健康度 + 两个评审维度 + 拒答率（负例独有）
const generationMetricDefs = [
  { key: 'hit1', label: 'Hit@1', hint: '检索健康度' },
  { key: 'faithfulness', label: '忠实性', hint: '答案有据' },
  { key: 'relevance', label: '相关性', hint: '答得切题' },
  { key: 'refusal_rate', label: '拒答率', hint: '负例不编造' },
]
const metricDefs = computed(() => (latest.value?.mode === 'generation' ? generationMetricDefs : retrievalMetricDefs))

// 显著性对比：watch 最近一对 → GET /eval/compare（读时计算，失败降级纯 Δ）
const compareData = ref(null)
const compareFailed = ref(false)
watch(latest, async (pair) => {
  compareData.value = null
  compareFailed.value = false
  if (!pair) return
  try {
    const res = await api.get('/eval/compare', { params: { a_id: pair.a.id, b_id: pair.b.id } })
    compareData.value = res.data
  } catch {
    compareFailed.value = true // 降级：卡片只显示裸 Δ，不显示 CI/显著性
  }
}, { immediate: true })

// 某指标的显著性块；旧 run 缺列 / 该 mode 不算此指标时后端返回 skipped 或 undefined
const metricStat = (key) => compareData.value?.metrics?.[key] || null

// Δ = B − A，按百分点展示；0 保持中性
const deltaOf = (key) => {
  if (!latest.value) return null
  const va = latest.value.a[key]
  const vb = latest.value.b[key]
  if (va == null || vb == null) return null
  const d = Number(vb) - Number(va)
  return Math.abs(d) < 0.00005 ? 0 : d
}
const pct = (v) => (v == null ? '—' : `${(Number(v) * 100).toFixed(1)}`)
const deltaText = (d) => (d == null ? '' : `${d > 0 ? '+' : d < 0 ? '−' : '±'}${Math.abs(d * 100).toFixed(1)}`)
// CI 展示：[lo, hi] ×100 保留 1 位；McNemar 无 CI，只显 p
const ciText = (s) => {
  if (!s || s.ci_low == null) return null
  return `[${(s.ci_low * 100).toFixed(1)}, ${(s.ci_high * 100).toFixed(1)}]`
}

// 胜者：检索层按 Recall@5 主指标（打平看 MRR）；生成层按忠实性（打平看拒答率）
const winner = computed(() => {
  if (!latest.value) return null
  const { a, b, mode } = latest.value
  const k1 = mode === 'generation' ? 'faithfulness' : 'recall5'
  const k2 = mode === 'generation' ? 'refusal_rate' : 'mrr'
  if (a[k1] != null && b[k1] != null && Number(b[k1]) !== Number(a[k1])) return Number(b[k1]) > Number(a[k1]) ? 'B' : 'A'
  if (a[k2] != null && b[k2] != null && Number(b[k2]) !== Number(a[k2])) return Number(b[k2]) > Number(a[k2]) ? 'B' : 'A'
  return null
})

// ---------- 运行历史 ----------
const runColumns = [
  { key: 'id', label: 'Run', primary: true },
  { key: 'mode', label: '层' },
  { key: 'variant', label: '变体' },
  { key: 'rewrite', label: '重写' },
  { key: 'case_count', label: '用例' },
  { key: 'hit1', label: 'Hit@1', align: 'right' },
  { key: 'recall5', label: 'Recall@5', align: 'right' },
  { key: 'mrr', label: 'MRR', align: 'right' },
  { key: 'ndcg5', label: 'NDCG@5', align: 'right' },
  { key: 'judge', label: 'F / R', align: 'right' },
  { key: 'refusal', label: '拒答率', align: 'right' },
  { key: 'duration_ms', label: '耗时', align: 'right' },
  { key: 'created_at', label: '时间' },
]

const expandedId = ref(null)
const detailCache = ref({}) // run_id → GET /eval/runs/{id} 结果
const detailLoading = ref(null)

const toggleExpand = async (id) => {
  if (expandedId.value === id) {
    expandedId.value = null
    return
  }
  expandedId.value = id
  if (detailCache.value[id]) return
  detailLoading.value = id
  try {
    const res = await api.get(`/eval/runs/${id}`)
    detailCache.value = { ...detailCache.value, [id]: res.data }
  } catch {
    toast.error('明细加载失败')
    expandedId.value = null
  } finally {
    detailLoading.value = null
  }
}

// 期望文档命中的 chip：主文档（grade=2）brand 描边，可接受（grade=1）blue 描边
const chipClass = (r, item) => {
  const exp = (r.expected_docs || []).find((d) => d.doc_filename === item.document_name)
  if (!exp) return 'border-line bg-surface-2 text-ink-3'
  return exp.grade === 2
    ? 'border-brand/60 bg-brand-soft text-brand font-medium'
    : 'border-blue/50 bg-blue-soft text-blue font-medium'
}

// kb_snapshot 摘要文案
const snapshotText = (snap) => {
  const entries = Object.entries(snap || {})
  if (!entries.length) return '无快照'
  return `${entries.length} 篇文档 · ${entries.slice(0, 3).map(([f, v]) => `${f} v${v}`).join('、')}${entries.length > 3 ? ' …' : ''}`
}

// 切片表：n 列防过度解读（colloquial 这类小样本指标波动大）
const sliceRows = (detail) => Object.entries(detail?.slices || {}).map(([category, v]) => ({ category, ...v }))

// ---------- 金标集（多标签 + 不可回答负例） ----------
const newQuestion = ref('')
const newDoc = ref('')
const newDoc2 = ref('')
const newDoc3 = ref('')
const newCategory = ref('general')
const newIsNegative = ref(false) // 负例开关：开=知识库无答案用例（隐藏文档选择）
const adding = ref(false)
const deleteTarget = ref(null)
const deleting = ref(false)

watch(newIsNegative, (v) => {
  if (v) {
    newCategory.value = 'unanswerable'
    newDoc.value = ''; newDoc2.value = ''; newDoc3.value = ''
  } else if (newCategory.value === 'unanswerable') {
    newCategory.value = 'general'
  }
})

const docOptions = computed(() => [
  { value: '', label: '（无）' },
  ...documents.value.map((d) => ({ value: d.filename, label: `${d.filename} v${d.version}` })),
])
const categoryOptions = [
  { value: 'general', label: '通用' },
  { value: 'hr', label: 'HR' },
  { value: 'it', label: 'IT' },
  { value: 'admin', label: '行政' },
  { value: 'finance', label: '财务' },
  { value: 'compliance', label: '合规' },
  { value: 'ambiguous', label: '陷阱/歧义' },
  { value: 'colloquial', label: '口语化' },
  { value: 'unanswerable', label: '无答案负例' },
]
const categoryTone = (c) => (
  { ambiguous: 'amber', compliance: 'blue', unanswerable: 'red', colloquial: 'ai' }[c] || 'gray'
)

const caseColumns = [
  { key: 'question', label: '问题', primary: true },
  { key: 'docs', label: '期望文档（主 + 可接受）' },
  { key: 'category', label: '分类' },
]

const negCount = computed(() => cases.value.filter((c) => c.is_answerable === 0).length)

const addCase = async () => {
  if (!newQuestion.value.trim()) {
    toast.error('问题要填')
    return
  }
  adding.value = true
  try {
    if (newIsNegative.value) {
      await api.post('/eval/cases', {
        question: newQuestion.value,
        category: newCategory.value,
        is_answerable: false,
        docs: [],
      })
    } else {
      if (!newDoc.value) {
        toast.error('主文档要选（无答案用例请打开"知识库无答案"开关）')
        adding.value = false
        return
      }
      // JSON Body 版：docs[0] 恰好一个 grade=2（主文档），其余 grade=1（可接受）
      const docs = [{ filename: newDoc.value, grade: 2 }]
      for (const fn of [newDoc2.value, newDoc3.value]) {
        if (fn) {
          if (docs.some((d) => d.filename === fn)) {
            toast.error('可接受文档不能与主文档或其他可接受文档重复')
            adding.value = false
            return
          }
          docs.push({ filename: fn, grade: 1 })
        }
      }
      await api.post('/eval/cases', {
        question: newQuestion.value,
        category: newCategory.value,
        docs,
      })
    }
    toast.success('用例已添加')
    newQuestion.value = ''
    newDoc.value = ''
    newDoc2.value = ''
    newDoc3.value = ''
    await loadCases()
  } catch (e) {
    toast.error(e.response?.data?.detail || '添加失败')
  } finally {
    adding.value = false
  }
}

const confirmDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.delete(`/eval/cases/${deleteTarget.value.id}`)
    toast.success('用例已删除')
    deleteTarget.value = null
    await loadCases()
  } catch (e) {
    toast.error(e.response?.data?.detail || '删除失败')
  } finally {
    deleting.value = false
  }
}

// ---------- 跑评测 ----------
// 检索层：A → B 顺序执行，rewrite 开关随请求带上（不调 LLM，快）
const runBoth = async () => {
  running.value = true
  const rw = rewriteOn.value
  const rwTag = rw ? '（重写开）' : ''
  try {
    runningPhase.value = `A 组 · baseline top_k=5${rwTag}`
    await api.post('/eval/run', null, { params: { variant: 'A', rewrite: rw } })
    runningPhase.value = `B 组 · top_k+2（检索更多候选）${rwTag}`
    await api.post('/eval/run', null, { params: { variant: 'B', rewrite: rw } })
    toast.success(`A/B 检索层评测完成（查询重写${rw ? '开' : '关'}）`)
    await loadRuns()
  } catch (e) {
    toast.error(e.response?.data?.detail || '评测运行失败')
  } finally {
    running.value = false
    runningPhase.value = ''
  }
}

// 生成层：异步 job——提交立即返回 job_id，5s 轮询真实进度；A 完成后接力 B（并行会被 409）
// jobId 存 localStorage，刷新页面后自动恢复轮询
const GEN_JOB_KEY = 'sf-eval-gen-job'
const saveJob = (s) => localStorage.setItem(GEN_JOB_KEY, JSON.stringify(s))
const clearJob = () => localStorage.removeItem(GEN_JOB_KEY)

const runGeneration = async () => {
  running.value = true
  const rw = rewriteOn.value
  try {
    for (const variant of ['A', 'B']) {
      runningPhase.value = `${variant} 组 · 提交任务…`
      const start = await api.post('/eval/run-generation', null, { params: { variant, rewrite: rw } })
      genJob.value = { jobId: start.data.job_id, variant, done: 0, total: 0, phase: '服务端启动中' }
      saveJob({ jobId: start.data.job_id, variant, rewrite: rw })
      runningPhase.value = ''
      await pollJob(start.data.job_id)
      clearJob()
      toast.success(`${variant} 组生成评测完成`)
    }
    await loadRuns()
  } catch (e) {
    toast.error(e.response?.data?.detail || e.message || '生成层评测失败')
  } finally {
    if (pollTimer) clearInterval(pollTimer)
    genJob.value = null
    running.value = false
    runningPhase.value = ''
  }
}

// 刷新恢复：localStorage 里有未完成的 job → 查状态 → running 就接着轮询，A 完成后自动接力 B
const resumeGenJob = async () => {
  const raw = localStorage.getItem(GEN_JOB_KEY)
  if (!raw) return
  let saved
  try { saved = JSON.parse(raw) } catch { clearJob(); return }
  try {
    const j = (await api.get(`/eval/job/${saved.jobId}`)).data
    if (j.status !== 'running') { clearJob(); return }
    toast.info(`检测到未完成的生成评测（${saved.variant} 组），已恢复进度`)
    running.value = true
    genJob.value = { jobId: saved.jobId, variant: saved.variant, done: j.done, total: j.total, phase: j.phase }
    await pollJob(saved.jobId)
    clearJob()
    toast.success(`${saved.variant} 组生成评测完成`)
    if (saved.variant === 'A') {
      runningPhase.value = 'B 组 · 提交任务…'
      const start = await api.post('/eval/run-generation', null, { params: { variant: 'B', rewrite: saved.rewrite } })
      genJob.value = { jobId: start.data.job_id, variant: 'B', done: 0, total: 0, phase: '服务端启动中' }
      saveJob({ jobId: start.data.job_id, variant: 'B', rewrite: saved.rewrite })
      runningPhase.value = ''
      await pollJob(start.data.job_id)
      clearJob()
      toast.success('B 组生成评测完成')
    }
    await loadRuns()
  } catch (e) {
    toast.error(e.response?.data?.detail || e.message || '恢复生成评测失败')
  } finally {
    if (pollTimer) clearInterval(pollTimer)
    genJob.value = null
    running.value = false
    runningPhase.value = ''
  }
}

// ---------- 加载 ----------
const loadRuns = async () => {
  const res = await api.get('/eval/runs')
  runs.value = res.data || []
  // 换新数据后清明细缓存，防止陈旧快照
  detailCache.value = {}
}

const loadCases = async () => {
  const res = await api.get('/eval/cases')
  cases.value = res.data || []
}

onMounted(async () => {
  try {
    await Promise.all([loadRuns(), loadCases(), api.get('/eval/documents').then((r) => { documents.value = r.data || [] })])
  } catch {
    toast.error('评测数据加载失败，请确认后端已部署 /eval 路由')
  } finally {
    loading.value = false
  }
  resumeGenJob() // 刷新后恢复未完成的生成评测 job
})

onUnmounted(() => { if (pollTimer) clearInterval(pollTimer) })
</script>

<template>
  <div>
    <PageHero
      title="RAG 评测"
      subtitle="多标签金标 · 负例拒答 · 检索/生成双层回归 · A/B 配对显著性（NDCG@5 / refusal / Δ±CI）"
      accent="ai"
    />

    <AppSkeleton v-if="loading" variant="card" />

    <template v-else>
      <!-- 运行控制条 -->
      <div
        class="flex flex-wrap items-center gap-3 mb-5 p-4 rounded-card bg-glass backdrop-blur-md border border-line animate-fade-up"
      >
        <AppButton variant="ai" :loading="running" :disabled="running" @click="runBoth">
          <Play v-if="!running" class="w-4 h-4" />
          <Loader2 v-else class="w-4 h-4 animate-spin" />
          跑检索评测（A+B）
        </AppButton>
        <AppButton variant="secondary" :loading="running" :disabled="running" @click="runGeneration">
          <Sparkles v-if="!running" class="w-4 h-4" />
          <Loader2 v-else class="w-4 h-4 animate-spin" />
          跑生成评测（A+B）
        </AppButton>
        <!-- 查询重写消融开关：量化线上 rewrite_query 层贡献 -->
        <button
          class="inline-flex items-center gap-2 px-3 h-9.5 rounded-ctl border transition-all duration-150 select-none"
          :class="rewriteOn
            ? 'border-ai/40 bg-ai-soft text-ai hover:border-ai/60'
            : 'border-line bg-surface-2 text-ink-3 hover:border-line-2 hover:text-ink-2'"
          :aria-pressed="rewriteOn"
          :disabled="running"
          @click="rewriteOn = !rewriteOn"
        >
          <span class="relative w-7 h-4 rounded-full transition-colors duration-200" :class="rewriteOn ? 'bg-ai/70' : 'bg-line-2'">
            <span
              class="absolute top-0.5 w-3 h-3 rounded-full bg-white transition-[left] duration-200"
              :class="rewriteOn ? 'left-3.5' : 'left-0.5'"
            />
          </span>
          <span class="text-[13px] font-medium">查询重写：{{ rewriteOn ? '开' : '关' }}</span>
        </button>
        <div class="min-w-0 flex-1 min-w-56">
          <!-- 生成 job 真进度条：done/total 来自服务端，不是假动画 -->
          <template v-if="genJob">
            <div class="flex items-center justify-between text-[12px] mb-1">
              <span class="flex items-center gap-1.5 font-medium text-ai">
                <Loader2 class="w-3.5 h-3.5 animate-spin" />
                {{ genJob.variant }} 组 · {{ genJob.phase }}
              </span>
              <span class="tabular-nums text-ink-3">{{ genJob.done }}/{{ genJob.total || '…' }} · {{ jobPct }}%</span>
            </div>
            <div class="h-1.5 rounded-full bg-surface-2 overflow-hidden">
              <div class="h-full rounded-full bg-ai/80 transition-all duration-500" :style="{ width: jobPct + '%' }" />
            </div>
          </template>
          <template v-else-if="running">
            <p class="flex items-center gap-1.5 text-[13px] font-medium text-ai">
              <Loader2 class="w-3.5 h-3.5 animate-spin" />
              正在运行：{{ runningPhase }}…
            </p>
          </template>
          <template v-else>
            <p class="text-[12px] text-ink-3">
              检索评测：只查不答，每轮约 1-3 分钟 · 重写开每问多一次 LLM 调用
            </p>
            <p class="text-[12px] text-amber mt-0.5">
              生成评测：每例 2 次 LLM 调用，单轮约 30-40 分钟——任务在服务端运行，已启动的轮次刷新页面不会中断
            </p>
          </template>
        </div>
        <div class="ml-auto flex items-center gap-4 text-[12px] text-ink-3 tabular-nums">
          <span>金标 {{ cases.length }} 条<span v-if="negCount">（负例 {{ negCount }}）</span></span>
          <span>历史 {{ runs.length }} 轮</span>
        </div>
      </div>

      <!-- A/B 对比玻璃条：Δ ± 95% CI + 显著性徽章 -->
      <div
        v-if="latest"
        class="mb-6 p-4 rounded-card bg-glass backdrop-blur-md border animate-fade-up overflow-x-auto"
        :class="winner ? 'border-brand/30 shadow-[0_0_28px_-14px_var(--brand-glow)]' : 'border-line'"
        style="animation-delay: 40ms"
      >
        <div class="flex items-center gap-2 mb-3 flex-wrap">
          <AppBadge :tone="'blue'" size="sm" variant="outline">
            A{{ latest.mode === 'generation' ? ' · 生成层' : ' · top_k=5（baseline）' }}
          </AppBadge>
          <span class="text-ink-3 text-xs">vs</span>
          <AppBadge tone="ai" size="sm" variant="outline">
            B{{ latest.mode === 'generation' ? ' · 生成层' : ' · top_k+2（实验组）' }}
          </AppBadge>
          <AppBadge :tone="Boolean(latest.a.rewrite) ? 'ai' : 'gray'" size="sm" variant="outline">
            重写{{ Boolean(latest.a.rewrite) ? '开' : '关' }}
          </AppBadge>
          <AppBadge
            v-if="compareData?.warnings?.length"
            tone="amber" size="sm" variant="outline"
            :title="compareData.warnings.join('；')"
          >口径警告 {{ compareData.warnings.length }}</AppBadge>
          <div class="ml-auto flex items-center gap-1.5">
            <Trophy v-if="winner" class="w-4 h-4 text-amber" />
            <span v-if="winner" class="text-[13px] font-medium text-ink">当前领先：{{ winner }} 组</span>
            <span v-else class="text-[13px] text-ink-3">主指标打平</span>
          </div>
        </div>

        <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          <div
            v-for="m in metricDefs"
            :key="m.key"
            class="px-4 py-3 rounded-ctl bg-surface/60 border border-line/60"
          >
            <div class="flex items-baseline justify-between mb-2">
              <p class="text-[12px] font-semibold text-ink-2">{{ m.label }}</p>
              <p class="text-[11px] text-ink-3">{{ m.hint }}</p>
            </div>
            <div class="flex items-end justify-between gap-2">
              <div>
                <p class="text-[11px] text-blue mb-0.5">A</p>
                <p
                  class="text-2xl font-bold tabular-nums leading-none"
                  :class="winner === 'A' ? 'text-blue' : 'text-ink'"
                >{{ pct(latest.a[m.key]) }}</p>
              </div>
              <div class="text-right">
                <p class="text-[11px] text-ai mb-0.5">B</p>
                <p
                  class="text-2xl font-bold tabular-nums leading-none"
                  :class="winner === 'B' ? 'text-ai' : 'text-ink'"
                >{{ pct(latest.b[m.key]) }}</p>
              </div>
            </div>
            <!-- Δ + CI + 显著性：裸 Δ 是幻觉，配对检验说话；CI 全负 = 显著劣化应拦截 -->
            <div class="mt-2 flex items-center justify-between gap-2">
              <p
                class="text-[12px] tabular-nums"
                :class="deltaOf(m.key) > 0 ? 'text-ai' : deltaOf(m.key) < 0 ? 'text-red' : 'text-ink-3'"
              >
                Δ {{ deltaText(deltaOf(m.key)) }}
                <span v-if="ciText(metricStat(m.key))" class="text-ink-3"> · CI {{ ciText(metricStat(m.key)) }}</span>
                <span v-else-if="metricStat(m.key)?.p != null" class="text-ink-3"> · p={{ metricStat(m.key).p }}</span>
              </p>
              <AppBadge
                v-if="metricStat(m.key) && !metricStat(m.key).skipped"
                :tone="metricStat(m.key).significant ? 'ai' : 'gray'"
                size="sm"
                variant="outline"
              >{{ metricStat(m.key).significant ? '显著' : '不显著' }}</AppBadge>
              <AppBadge v-else-if="metricStat(m.key)?.skipped" tone="gray" size="sm" variant="outline" :title="metricStat(m.key).reason">跳过</AppBadge>
            </div>
          </div>
        </div>

        <p class="mt-3 text-[11px] text-ink-3">
          基于最近同口径的一对：A（Run #{{ latest.a.id }}）vs B（Run #{{ latest.b.id }}）·
          配对 {{ compareData?.n_paired ?? '—' }} 条 ·
          Hit@1 走精确 McNemar，分数指标（含生成层 F/R/拒答率）走 paired bootstrap（1000 次，CI 不含 0 = 显著）·
          <span v-if="latest.mode === 'generation'">排名指标只统计可回答用例（负例不进分母），拒答率只统计负例</span>
          <span v-else>对比条只配对同 mode 的 run 且跟随最近一次运行的重写口径</span>
          <span v-if="compareFailed" class="text-amber"> · 显著性服务暂不可用，当前仅显示裸 Δ</span>
        </p>
      </div>

      <!-- 空态：还没跑过 -->
      <AppCard v-else class="mb-6 animate-rise">
        <div class="py-8 text-center">
          <Target class="w-8 h-8 text-ink-3 mx-auto mb-3" :stroke-width="1.5" />
          <p class="text-sm text-ink-2">还没有完整的 A/B 评测记录</p>
          <p class="text-[12px] text-ink-3 mt-1">点击上方"跑检索评测"，A、B 各生成一条 run 后此处显示对比</p>
        </div>
      </AppCard>

      <!-- 运行历史 -->
      <div class="mb-6 animate-rise" style="animation-delay: 80ms">
        <h2 class="flex items-center gap-1.5 text-[13px] font-semibold text-ink-2 mb-2.5">
          <FileText class="w-3.5 h-3.5 text-ink-3" />
          运行历史
          <span class="text-ink-3 font-normal">（展开看逐用例明细、分类别切片、生成答案与评审分）</span>
        </h2>
        <AppTable
          :columns="runColumns"
          :rows="runs"
          expandable
          :expanded-id="expandedId"
          emptyText="还没有评测运行，点上方按钮跑一次"
          @toggle-expand="toggleExpand"
        >
          <template #cell-mode="{ row }">
            <AppBadge :tone="row.mode === 'generation' ? 'ai' : 'gray'" size="sm" variant="outline">
              {{ row.mode === 'generation' ? '生成层' : '检索层' }}
            </AppBadge>
          </template>
          <template #cell-variant="{ row }">
            <AppBadge :tone="row.variant === 'A' ? 'blue' : 'ai'" size="sm" variant="outline">{{ row.variant }}</AppBadge>
          </template>
          <template #cell-rewrite="{ row }">
            <AppBadge :tone="row.rewrite ? 'ai' : 'gray'" size="sm" :variant="row.rewrite ? 'soft' : 'outline'">
              {{ row.rewrite ? '开' : '关' }}
            </AppBadge>
          </template>
          <template #cell-case_count="{ row }">
            <span class="tabular-nums">{{ row.case_count }}</span>
            <span v-if="row.answerable_count != null && row.answerable_count !== row.case_count" class="text-ink-3">/{{ row.answerable_count }}</span>
          </template>
          <template #cell-hit1="{ row }">{{ pct(row.hit1) }}</template>
          <template #cell-recall5="{ row }">{{ pct(row.recall5) }}</template>
          <template #cell-mrr="{ row }">{{ pct(row.mrr) }}</template>
          <template #cell-ndcg5="{ row }">{{ pct(row.ndcg5) }}</template>
          <template #cell-judge="{ row }">
            <span v-if="row.mode === 'generation'" class="tabular-nums text-[12px]">
              <span v-if="row.faithfulness != null">
                F:{{ (row.faithfulness * 5).toFixed(1) }} R:{{ ((row.relevance ?? 0) * 5).toFixed(1) }}
              </span>
              <span v-else class="text-ink-3">评审失败</span>
            </span>
            <span v-else class="text-ink-3">—</span>
          </template>
          <template #cell-refusal="{ row }">
            <span v-if="row.mode === 'generation' && row.refusal_rate != null" class="tabular-nums text-[12px]">
              {{ pct(row.refusal_rate) }}
            </span>
            <span v-else class="text-ink-3">—</span>
          </template>
          <template #cell-duration_ms="{ row }">{{ (row.duration_ms / 1000).toFixed(1) }}s</template>
          <template #cell-created_at="{ row }">
            <span class="tabular-nums text-[12px]">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</span>
          </template>

          <template #expand="{ row }">
            <div v-if="detailLoading === row.id" class="py-4 text-[13px] text-ink-3">明细加载中…</div>
            <div v-else-if="detailCache[row.id]" class="space-y-4">
              <!-- 知识库快照：这轮评测跑在什么语料上 -->
              <div class="flex items-start gap-2 text-[12px]">
                <span class="shrink-0 mt-0.5 w-5 h-5 rounded-[6px] bg-ai-soft flex items-center justify-center">
                  <Target class="w-3 h-3 text-ai" />
                </span>
                <span class="text-ink-2">
                  <span class="font-medium text-ink">kb_snapshot：</span>
                  <span class="text-ink-3">{{ snapshotText(detailCache[row.id].kb_snapshot) }}</span>
                </span>
              </div>

              <!-- 分类别切片：哪类问题在拖分（n 列防小样本过度解读） -->
              <div v-if="Object.keys(detailCache[row.id].slices || {}).length" class="overflow-x-auto">
                <p class="text-[12px] font-medium text-ink-2 mb-1.5">分类别指标（读时聚合）</p>
                <table class="w-full text-[12px]">
                  <thead>
                    <tr class="border-b border-line text-left text-[11px] uppercase tracking-wider text-ink-3">
                      <th class="py-1.5 pr-3 font-semibold">类别</th>
                      <th class="py-1.5 pr-3 font-semibold">n（可答/负）</th>
                      <th class="py-1.5 pr-3 font-semibold text-right">Hit@1</th>
                      <th class="py-1.5 pr-3 font-semibold text-right">Recall@5</th>
                      <th class="py-1.5 pr-3 font-semibold text-right">NDCG@5</th>
                      <th class="py-1.5 pr-3 font-semibold text-right">F / R</th>
                      <th class="py-1.5 font-semibold text-right">拒答率</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="s in sliceRows(detailCache[row.id])" :key="s.category" class="border-b border-line/40 last:border-0">
                      <td class="py-1.5 pr-3">
                        <AppBadge :tone="categoryTone(s.category)" size="sm" variant="outline">{{ s.category }}</AppBadge>
                      </td>
                      <td class="py-1.5 pr-3 tabular-nums text-ink-3">{{ s.n }}（{{ s.n_answerable }}/{{ s.n_negative }}）</td>
                      <td class="py-1.5 pr-3 tabular-nums text-right">{{ pct(s.hit1) }}</td>
                      <td class="py-1.5 pr-3 tabular-nums text-right">{{ pct(s.recall5) }}</td>
                      <td class="py-1.5 pr-3 tabular-nums text-right">{{ pct(s.ndcg5) }}</td>
                      <td class="py-1.5 pr-3 tabular-nums text-right text-ink-3">
                        {{ s.faithfulness != null ? `${(s.faithfulness * 5).toFixed(1)}/${(s.relevance * 5).toFixed(1)}` : '—' }}
                      </td>
                      <td class="py-1.5 tabular-nums text-right" :class="s.refusal_rate != null && s.refusal_rate < 1 ? 'text-red' : ''">
                        {{ pct(s.refusal_rate) }}
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>

              <!-- 逐用例明细 -->
              <div class="overflow-x-auto">
                <table class="w-full text-[12px]">
                  <thead>
                    <tr class="border-b border-line text-left text-[11px] uppercase tracking-wider text-ink-3">
                      <th class="py-2 pr-3 font-semibold">问题</th>
                      <th class="py-2 pr-3 font-semibold">期望文档</th>
                      <th class="py-2 pr-3 font-semibold">结果</th>
                      <th v-if="detailCache[row.id].mode === 'generation'" class="py-2 pr-3 font-semibold">答案 / 评审</th>
                      <th class="py-2 font-semibold">检索产物（top {{ detailCache[row.id].results?.[0]?.retrieved?.items?.length || 0 }}）</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="r in detailCache[row.id].results" :key="r.id" class="border-b border-line/40 last:border-0 align-top">
                      <td class="py-2.5 pr-3 max-w-56 text-ink-2">
                        {{ r.question }}
                        <!-- 重写消融证据：重写后≠原话时把实际检索的 query 摆出来 -->
                        <p
                          v-if="r.retrieved?.query_used && r.retrieved.query_used !== r.question"
                          class="mt-1 text-[11px] text-ai/80 leading-snug"
                        >
                          重写后：{{ r.retrieved.query_used }}
                        </p>
                      </td>
                      <td class="py-2.5 pr-3 text-ink-3">
                        <template v-if="r.expected_doc == null && !r.expected_docs?.length">
                          <AppBadge tone="red" size="sm" variant="outline"><Ban class="w-3 h-3 mr-0.5" />无答案（负例）</AppBadge>
                        </template>
                        <template v-else>
                          <span
                            v-for="d in (r.expected_docs || [])"
                            :key="d.doc_filename"
                            class="inline-block mb-0.5 mr-1 px-1.5 py-0.5 rounded-md border text-[11px] whitespace-nowrap"
                            :class="d.grade === 2
                              ? 'border-brand/60 bg-brand-soft text-brand'
                              : 'border-blue/50 bg-blue-soft text-blue'"
                          >
                            {{ d.grade === 2 ? '✓' : '~' }} {{ d.doc_filename }}
                          </span>
                          <span v-if="!r.expected_docs?.length" class="whitespace-nowrap">{{ r.expected_doc }}</span>
                        </template>
                      </td>
                      <td class="py-2.5 pr-3 whitespace-nowrap">
                        <template v-if="r.expected_doc == null && !r.expected_docs?.length">
                          <AppBadge tone="gray" size="sm" variant="outline">负例 · 不计排名</AppBadge>
                          <p v-if="r.duration_ms != null" class="mt-1 text-[11px] text-ink-3 tabular-nums text-right">{{ r.duration_ms }}ms</p>
                        </template>
                        <template v-else>
                          <AppBadge v-if="r.hit" tone="brand" size="sm">命中@{{ r.first_rank }}</AppBadge>
                          <AppBadge v-else tone="red" size="sm">未命中</AppBadge>
                          <p v-if="r.ndcg5 != null" class="mt-1 text-[11px] text-ink-3 tabular-nums text-right">
                            n@5 {{ (r.ndcg5 * 100).toFixed(0) }} · {{ r.duration_ms }}ms
                          </p>
                        </template>
                      </td>
                      <td v-if="detailCache[row.id].mode === 'generation'" class="py-2.5 pr-3 max-w-72">
                        <template v-if="r.judge && r.judge.refused !== undefined">
                          <!-- 负例评审：拒答=正确（brand），编造=幻觉（red） -->
                          <AppBadge :tone="r.judge.refused ? 'brand' : 'red'" size="sm">
                            {{ r.judge.refused ? '✓ 拒答正确' : '✗ 幻觉编造' }}
                          </AppBadge>
                          <p v-if="r.judge.error" class="mt-1 text-[11px] text-red">评审失败，已剔除出拒答率</p>
                          <p v-else-if="r.judge.reason" class="mt-1 text-[11px] text-ink-3 leading-snug">{{ r.judge.reason }}</p>
                        </template>
                        <template v-else-if="r.judge">
                          <AppBadge
                            :tone="(r.judge.faithfulness ?? 0) >= 4 ? 'brand' : (r.judge.faithfulness ?? 0) >= 3 ? 'amber' : 'red'"
                            size="sm" variant="outline"
                          >F:{{ r.judge.faithfulness }}</AppBadge>
                          <AppBadge
                            :tone="(r.judge.relevance ?? 0) >= 4 ? 'brand' : (r.judge.relevance ?? 0) >= 3 ? 'amber' : 'red'"
                            size="sm" variant="outline"
                          >R:{{ r.judge.relevance }}</AppBadge>
                          <p v-if="r.judge.error" class="mt-1 text-[11px] text-red">评审失败，已剔除出均值</p>
                          <p v-else-if="r.judge.reason" class="mt-1 text-[11px] text-ink-3 leading-snug">{{ r.judge.reason }}</p>
                        </template>
                        <p v-if="r.answer" class="mt-1 text-[11px] text-ink-2 leading-snug line-clamp-3" :title="r.answer">
                          {{ r.answer }}
                        </p>
                      </td>
                      <td class="py-2.5">
                        <div v-if="r.retrieved?.items?.length" class="flex flex-wrap gap-1">
                          <span
                            v-for="item in r.retrieved.items"
                            :key="item.rank"
                            class="inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md border text-[11px] max-w-48 truncate"
                            :class="chipClass(r, item)"
                            :title="item.snippet"
                          >
                            <span class="tabular-nums opacity-60">#{{ item.rank }}</span>
                            {{ item.document_name }}
                          </span>
                        </div>
                        <span v-else class="text-ink-3">（无检索结果）</span>
                      </td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </template>
        </AppTable>
      </div>

      <!-- 金标集管理（多标签 + 负例） -->
      <AppCard class="animate-rise" style="animation-delay: 120ms">
        <h2 class="flex items-center gap-1.5 text-[13px] font-semibold text-ink mb-3">
          <Target class="w-4 h-4 text-ai" />
          金标集
          <AppBadge tone="ai" size="sm" variant="outline">{{ cases.length }} 条</AppBadge>
          <AppBadge tone="gray" size="sm" variant="outline">
            多标签 {{ cases.filter((c) => (c.docs?.length || 0) > 1).length }} 条
          </AppBadge>
          <AppBadge v-if="negCount" tone="red" size="sm" variant="outline">负例 {{ negCount }} 条</AppBadge>
        </h2>

        <!-- 新增行：问题 + 分类 + 负例开关；负例隐藏文档选择 -->
        <div class="space-y-2 mb-4">
          <div class="grid sm:grid-cols-[1fr_160px_auto] gap-2">
            <AppInput v-model="newQuestion" :placeholder="newIsNegative ? '问题：一个知识库里确实没有答案的员工问题' : '问题：一句话，带可核验的数字或事实'" size="sm" />
            <AppSelect v-model="newCategory" :options="categoryOptions" size="sm" :disabled="newIsNegative" />
            <AppButton variant="secondary" size="sm" :loading="adding" @click="addCase">
              <Plus class="w-3.5 h-3.5" />
              添加
            </AppButton>
          </div>
          <div class="flex items-center gap-3">
            <button
              class="inline-flex items-center gap-2 px-2.5 h-8 rounded-ctl border transition-all duration-150 select-none text-[12px]"
              :class="newIsNegative
                ? 'border-red/40 bg-red-soft text-red'
                : 'border-line bg-surface-2 text-ink-3 hover:border-line-2 hover:text-ink-2'"
              :aria-pressed="newIsNegative"
              @click="newIsNegative = !newIsNegative"
            >
              <span class="relative w-7 h-4 rounded-full transition-colors duration-200" :class="newIsNegative ? 'bg-red/70' : 'bg-line-2'">
                <span
                  class="absolute top-0.5 w-3 h-3 rounded-full bg-white transition-[left] duration-200"
                  :class="newIsNegative ? 'left-3.5' : 'left-0.5'"
                />
              </span>
              <span class="font-medium">知识库无答案</span>
            </button>
            <p v-if="newIsNegative" class="text-[11px] text-red">负例不参与排名指标，生成层只评"是否拒答"（不编造）</p>
          </div>
          <div v-if="!newIsNegative" class="grid sm:grid-cols-3 gap-2">
            <div>
              <AppSelect v-model="newDoc" :options="docOptions" size="sm" />
              <span class="mt-1 inline-flex items-center gap-1 text-[11px] text-brand font-medium">
                <span class="px-1 rounded border border-brand/60 bg-brand-soft">✓ 主</span> 权威出处，grade=2
              </span>
            </div>
            <div>
              <AppSelect v-model="newDoc2" :options="docOptions" size="sm" />
              <span class="mt-1 inline-flex items-center gap-1 text-[11px] text-blue">
                <span class="px-1 rounded border border-blue/50 bg-blue-soft">~ 可接受</span> 沾边算对，grade=1
              </span>
            </div>
            <div>
              <AppSelect v-model="newDoc3" :options="docOptions" size="sm" />
              <span class="mt-1 text-[11px] text-ink-3">（可选第 2 个可接受文档）</span>
            </div>
          </div>
        </div>

        <AppTable :columns="caseColumns" :rows="cases" emptyText="金标集为空">
          <template #cell-docs="{ row }">
            <template v-if="row.is_answerable === 0">
              <AppBadge tone="red" size="sm" variant="outline"><Ban class="w-3 h-3 mr-0.5" />无答案（负例）</AppBadge>
            </template>
            <template v-else>
              <span
                v-for="d in (row.docs || [])"
                :key="d.doc_filename"
                class="inline-block mb-0.5 mr-1 px-1.5 py-0.5 rounded-md border text-[11px] whitespace-nowrap"
                :class="d.grade === 2
                  ? 'border-brand/60 bg-brand-soft text-brand font-medium'
                  : 'border-blue/50 bg-blue-soft text-blue font-medium'"
              >
                {{ d.grade === 2 ? '✓ 主' : '~ 可接受' }} {{ d.doc_filename }}
              </span>
            </template>
          </template>
          <template #cell-category="{ row }">
            <AppBadge :tone="categoryTone(row.category)" size="sm" variant="outline">{{ row.category }}</AppBadge>
          </template>
          <template #cell-question="{ row }">
            <div class="flex items-center justify-between gap-2">
              <span class="min-w-0">{{ row.question }}</span>
              <button
                class="p-1 rounded-md text-ink-3 hover:text-red hover:bg-red-soft transition-colors shrink-0"
                aria-label="删除用例"
                @click="deleteTarget = row"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </div>
          </template>
        </AppTable>

        <div class="flex items-start gap-2 mt-4 text-[12px] text-ink-3 leading-relaxed">
          <Lightbulb class="w-3.5 h-3.5 shrink-0 mt-0.5 text-amber" />
          <p>
            多标签金标：主文档（grade=2，权威出处）与可接受文档（grade=1）分开标注——Hit/MRR 引到任一都算对，
            <span class="text-ink-2">NDCG@5 用 grade 加权区分引到谁更好</span>。
            <span class="text-ink-2">负例（知识库无答案）只在生成层评拒答率</span>：如实说没有=正确，编造具体条款=幻觉；
            排名指标分母用 answerable_count，负例混入会稀释 Hit@1。
            A/B 差异一律看配对检验（精确 McNemar / bootstrap CI），裸 Δ 在小样本 + LLM 噪声下是统计幻觉；
            <span class="text-ink-2">CI 完全落在 0 以下 = 显著劣化，应拦截上线</span>。
          </p>
        </div>
      </AppCard>

      <!-- 删除确认 -->
      <AppModal v-model="deleteTarget" title="删除用例" size="sm">
        <p class="text-sm text-ink-2">
          确认删除金标用例？<br />
          <span class="text-ink-3 text-[13px]">「{{ deleteTarget?.question }}」</span>
        </p>
        <template #footer>
          <AppButton variant="secondary" size="sm" @click="deleteTarget = null">取消</AppButton>
          <AppButton variant="danger" size="sm" :loading="deleting" @click="confirmDelete">确认删除</AppButton>
        </template>
      </AppModal>
    </template>
  </div>
</template>
