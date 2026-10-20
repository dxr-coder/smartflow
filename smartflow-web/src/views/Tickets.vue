<!--
  Tickets — 工单列表 + 创建
  数据流：GET /tickets；POST /tickets {title, content} → 刷新列表 + toast
  视觉：PageHero 锥形描边英雄区 + AppCard interactive + 左侧状态色条 + AppBadge 呼吸点
-->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Plus, Ticket, ArrowRight, Inbox, CheckCircle2, ListTodo, ShieldCheck } from 'lucide-vue-next'
import api from '../api'
import { toast } from '../composables/useToast'
import { ticketTones } from '../utils/badges'
import AppCard from '../components/ui/AppCard.vue'
import AppBadge from '../components/ui/AppBadge.vue'
import AppButton from '../components/ui/AppButton.vue'
import AppModal from '../components/ui/AppModal.vue'
import AppInput from '../components/ui/AppInput.vue'
import AppTextarea from '../components/ui/AppTextarea.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import AppEmptyState from '../components/ui/AppEmptyState.vue'
import AppSkeleton from '../components/ui/AppSkeleton.vue'
import PageHero from '../components/layout/PageHero.vue'

const router = useRouter()
const route = useRoute()

const tickets = ref([])
const loading = ref(true)
const createOpen = ref(route.query.create === '1')
const creating = ref(false)
const form = ref({ title: '', content: '', category: 'it', priority: 'normal' })

// 建单弹窗里的下拉选项（category 会同时写进 department）
const categoryOptions = [
  { value: 'it', label: 'IT（设备/网络/账号）' },
  { value: 'hr', label: '人事（考勤/假期/入职）' },
  { value: 'finance', label: '财务（报销/发票）' },
  { value: 'admin', label: '行政（会议室/办公用品）' },
]
const priorityOptions = [
  { value: 'low', label: '低' },
  { value: 'normal', label: '普通' },
  { value: 'high', label: '高（需客服主管审批）' },
  { value: 'urgent', label: '紧急（需客服 + 管理员两级审批）' },
]

const statusLabels = {
  pending: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭',
  escalated: '已升级', rejected: '已驳回', waiting: '等待中', accepted: '已受理',
}

const barColors = {
  pending: 'bg-amber', processing: 'bg-blue', resolved: 'bg-brand',
  closed: 'bg-ink-3', escalated: 'bg-red', rejected: 'bg-red', waiting: 'bg-amber', accepted: 'bg-brand',
}

// hover 光晕色
const glowColors = {
  pending: 'rgba(245,158,11,0.18)', processing: 'rgba(56,189,248,0.16)', resolved: 'var(--brand-glow)',
  closed: 'transparent', escalated: 'rgba(244,63,94,0.16)', rejected: 'rgba(244,63,94,0.16)', waiting: 'rgba(245,158,11,0.18)', accepted: 'var(--brand-glow)',
}

// 状态汇总玻璃条：从列表即时统计，不加接口（与 Transfer 同一视觉语言）
const statusSummary = computed(() => {
  const counts = {}
  for (const t of tickets.value) counts[t.status] = (counts[t.status] || 0) + 1
  return [
    { label: '全部', value: tickets.value.length, icon: Ticket, tone: 'text-ink-2', bg: 'bg-surface-2' },
    { label: '待处理', value: counts.pending || 0, icon: Inbox, tone: 'text-amber', bg: 'bg-amber-soft' },
    { label: '处理中', value: counts.processing || 0, icon: ListTodo, tone: 'text-blue', bg: 'bg-blue-soft' },
    { label: '已解决', value: counts.resolved || 0, icon: CheckCircle2, tone: 'text-brand', bg: 'bg-brand-soft' },
  ]
})

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/tickets')
    tickets.value = res.data.items || res.data
  } catch (e) {
    toast.error('工单加载失败')
  } finally {
    loading.value = false
  }
}

const create = async () => {
  if (!form.value.title.trim() || !form.value.content.trim()) {
    toast.error('请填写标题和内容')
    return
  }
  creating.value = true
  try {
    await api.post('/tickets', null, {
      params: {
        title: form.value.title.trim(),
        content: form.value.content.trim(),
        category: form.value.category,
        priority: form.value.priority,
      },
    })
    toast.success('工单创建成功')
    createOpen.value = false
    form.value = { title: '', content: '', category: 'it', priority: 'normal' }
    load()
  } catch (e) {
    toast.error('创建失败，请重试')
  } finally {
    creating.value = false
  }
}

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

onMounted(load)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <!-- 页头英雄区 -->
    <PageHero title="工单" subtitle="跟进处理进度，点击卡片进入详情流转">
      <AppButton @click="createOpen = true">
        <Plus class="w-4 h-4" />
        <span class="hidden sm:inline">新建工单</span>
      </AppButton>
    </PageHero>

    <!-- 状态汇总玻璃条（与 Transfer 同一视觉语言） -->
    <div
      v-if="!loading && tickets.length"
      class="flex items-center gap-2 mt-4 mb-5 p-3 rounded-card bg-glass backdrop-blur-md border border-line animate-fade-up overflow-x-auto"
      style="animation-delay: 40ms"
    >
      <div
        v-for="(s, i) in statusSummary"
        :key="s.label"
        class="flex items-center gap-2.5 px-3.5 py-2 rounded-ctl shrink-0 transition-colors duration-150"
        :class="i < statusSummary.length - 1 ? 'border-r border-line' : ''"
      >
        <span class="w-7 h-7 rounded-[8px] flex items-center justify-center" :class="s.bg">
          <component :is="s.icon" class="w-3.5 h-3.5" :class="s.tone" :stroke-width="2" />
        </span>
        <div>
          <p class="text-[15px] font-bold text-ink leading-none tabular-nums">{{ s.value }}</p>
          <p class="text-[11px] text-ink-3 mt-0.5">{{ s.label }}</p>
        </div>
      </div>
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="space-y-3">
      <AppSkeleton v-for="i in 4" :key="i" variant="card" />
    </div>

    <!-- 空状态 -->
    <AppEmptyState
      v-else-if="!tickets.length"
      :icon="Ticket"
      title="还没有工单"
      description="遇到需要人工处理的问题时，创建一个工单，支持团队会跟进处理。"
    >
      <AppButton size="sm" @click="createOpen = true"><Plus class="w-4 h-4" />创建第一个工单</AppButton>
    </AppEmptyState>

    <!-- 列表 -->
    <div v-else class="space-y-2.5">
      <AppCard
        v-for="(t, i) in tickets"
        :key="t.id"
        interactive
        padding="none"
        class="group relative overflow-hidden animate-rise"
        :style="{ animationDelay: `${80 + i * 50}ms` }"
        @click="router.push(`/tickets/${t.id}`)"
      >
        <!-- 状态色 hover 光晕 -->
        <div
          class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
          :style="{ background: `linear-gradient(90deg, ${glowColors[t.status] || 'transparent'} 0%, transparent 42%)` }"
          aria-hidden="true"
        />
        <div class="relative flex">
          <!-- 状态色条（加宽 + 发光） -->
          <div
            class="w-[3px] shrink-0 transition-all duration-200 group-hover:w-[5px]"
            :class="barColors[t.status] || 'bg-ink-3'"
          />
          <div class="flex-1 flex items-center gap-4 p-4 sm:px-5">
            <div class="min-w-0 flex-1">
              <div class="flex items-center gap-2.5 mb-1">
                <span class="text-[12px] font-mono text-ink-3 tabular-nums">#{{ t.id }}</span>
                <AppBadge :tone="ticketTones[t.status] || 'gray'" size="sm" dot>
                  {{ statusLabels[t.status] || t.status }}
                </AppBadge>
              </div>
              <p class="text-sm font-medium text-ink truncate group-hover:text-brand transition-colors">
                {{ t.title }}
              </p>
              <p class="text-[12px] text-ink-3 mt-1 tabular-nums">{{ fmtTime(t.created_at) }}</p>
            </div>
            <ArrowRight class="w-4 h-4 text-ink-3 shrink-0 -translate-x-1 opacity-0 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-200" />
          </div>
        </div>
      </AppCard>
    </div>

    <!-- 创建弹窗 -->
    <AppModal v-model="createOpen" title="新建工单" size="md">
      <div class="space-y-4">
        <AppInput v-model="form.title" label="标题" placeholder="一句话概括问题" />
        <AppTextarea v-model="form.content" label="详细描述" placeholder="描述你遇到的问题、已尝试的步骤…" :rows="4" />
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[12px] font-medium text-ink-2 mb-1.5">所属部门</label>
            <AppSelect v-model="form.category" :options="categoryOptions" />
          </div>
          <div>
            <label class="block text-[12px] font-medium text-ink-2 mb-1.5">优先级</label>
            <AppSelect v-model="form.priority" :options="priorityOptions" />
          </div>
        </div>
        <!-- 高优/紧急提示：让用户知道选了会发生什么 -->
        <p
          v-if="form.priority === 'high' || form.priority === 'urgent'"
          class="text-[12px] text-amber flex items-center gap-1.5"
        >
          <ShieldCheck class="w-3.5 h-3.5 shrink-0" />
          该优先级需审批通过后才能开始处理
        </p>
      </div>
      <template #footer>
        <AppButton variant="secondary" @click="createOpen = false">取消</AppButton>
        <AppButton :loading="creating" @click="create">创建工单</AppButton>
      </template>
    </AppModal>
  </div>
</template>
