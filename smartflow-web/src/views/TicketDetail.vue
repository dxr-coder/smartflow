<!--
  TicketDetail — 工单详情 + 状态流转 + 审批链 + 转接 + CSAT 评分
  数据流：GET /tickets/:id（带 approvals）；PUT /tickets/:id/status；
         POST /tickets/:id/approvals/:level/approve|reject?comment=；
         POST /transfer（发起转接）；GET /csat/:id 评分初始态；POST /csat/:id 提交评分
  视觉：全宽状态色英雄带（conic 描边 + mesh-drift）+ 评分邀请条 + AppStepper
        + 审批时间线 + 左描述/右侧栏双栏
-->
<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ArrowLeft, Clock, FileText, User, Activity, Zap, ShieldCheck, Check, X, ArrowRightLeft, Star } from 'lucide-vue-next'
import api from '../api'
import { toast } from '../composables/useToast'
import { ticketTones } from '../utils/badges'
import { useAuth, ensureUserLoaded } from '../composables/useAuth'
import AppBadge from '../components/ui/AppBadge.vue'
import AppButton from '../components/ui/AppButton.vue'
import AppCard from '../components/ui/AppCard.vue'
import AppInput from '../components/ui/AppInput.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import AppModal from '../components/ui/AppModal.vue'
import AppSkeleton from '../components/ui/AppSkeleton.vue'
import AppStepper from '../components/ui/AppStepper.vue'
import StarRating from '../components/ui/StarRating.vue'
import CsatModal from '../components/ui/CsatModal.vue'

const route = useRoute()
const router = useRouter()
const { userInfo } = useAuth()

const ticket = ref(null)
const loading = ref(true)
const acting = ref(false)
const actingApproval = ref(null)  // 正在处理的审批行 id+动作，按钮转圈用
const approvalComment = ref('')   // 共用的审批意见输入框
const csat = ref(null)            // 本单已有评分（null=没评过）
const csatOpen = ref(false)       // 评分弹窗开关

const steps = [
  { value: 'pending', label: '待处理' },
  { value: 'processing', label: '处理中' },
  { value: 'resolved', label: '已解决' },
  { value: 'closed', label: '已关闭' },
]

const statusLabels = {
  pending: '待处理', processing: '处理中', resolved: '已解决', closed: '已关闭',
  escalated: '已升级', rejected: '已驳回', waiting: '等待中', accepted: '已受理',
}

const priorityLabels = { low: '低', normal: '普通', high: '高', urgent: '紧急' }
const priorityTones = { low: 'gray', normal: 'blue', high: 'amber', urgent: 'red' }
const approverLabels = { agent: '客服审批', admin: '管理员审批' }
const approvalTones = {
  pending: { badge: 'amber', circle: 'bg-amber/15 text-amber', label: '等待审批' },
  approved: { badge: 'brand', circle: 'bg-brand/15 text-brand', label: '已通过' },
  rejected: { badge: 'red', circle: 'bg-red/15 text-red', label: '已驳回' },
}

// rejected 是终态：STATUS_FLOW 里没有出口，流转操作一个都没有
const actions = computed(() => {
  const s = ticket.value?.status
  const map = {
    pending: [{ label: '开始处理', to: 'processing', variant: 'brand', icon: Zap }],
    processing: [
      { label: '标记已解决', to: 'resolved', variant: 'brand', icon: Zap },
      { label: '关闭工单', to: 'closed', variant: 'secondary' },
    ],
    resolved: [
      { label: '关闭工单', to: 'closed', variant: 'secondary' },
      { label: '重新打开', to: 'processing', variant: 'secondary' },
    ],
    closed: [{ label: '重新打开', to: 'processing', variant: 'secondary' }],
    escalated: [{ label: '开始处理', to: 'processing', variant: 'brand', icon: Zap }],
    waiting: [{ label: '恢复处理', to: 'processing', variant: 'brand', icon: Zap }],
    accepted: [{ label: '开始处理', to: 'processing', variant: 'brand', icon: Zap }],
  }
  return map[s] || []
})

// 这一行轮到我批吗：格子还空着 + 我的角色和这格认的角色一致
const canDecide = (a) =>
  a.status === 'pending' && userInfo.value?.role_name === a.approver_role

// 是不是自己的单：/auth/me 返回 id，工单表里是 user_id，字段名不一样
const isOwner = computed(() => ticket.value && userInfo.value?.id === ticket.value.user_id)
// 能评：自己的 + 已解决/已关闭 + 还没评过（后端同样校验，这里只是少弹一次报错）
const canRate = computed(() =>
  ticket.value
  && ['resolved', 'closed'].includes(ticket.value.status)
  && !csat.value
  && isOwner.value,
)

const load = async () => {
  loading.value = true
  try {
    const res = await api.get(`/tickets/${route.params.id}`)
    ticket.value = res.data
  } catch (e) {
    toast.error('工单加载失败')
  } finally {
    loading.value = false
  }
}

// 评分初始态：GET 返回已有评分或 null，刷新后"已评价"不丢
const loadCsat = async () => {
  try {
    const res = await api.get(`/csat/${route.params.id}`)
    csat.value = res.data || null
  } catch {
    csat.value = null
  }
}

const setStatus = async (newStatus) => {
  acting.value = true
  try {
    await api.put(`/tickets/${ticket.value.id}/status`, null, { params: { new_status: newStatus } })
    ticket.value.status = newStatus
    toast.success(`已更新为「${statusLabels[newStatus] || newStatus}」`)
  } catch (e) {
    // 审批守卫拦下时 detail 是中文提示，透出来比笼统的"失败"有用
    toast.error(e.response?.data?.detail || '状态更新失败')
  } finally {
    acting.value = false
  }
}

// 批 / 驳：批完重新拉详情，审批链和工单状态一起刷新（可能被自动推进）
const decide = async (a, decision) => {
  actingApproval.value = `${a.id}-${decision}`
  try {
    const res = await api.post(
      `/tickets/${ticket.value.id}/approvals/${a.level}/${decision}`,
      null,
      { params: { comment: approvalComment.value } },
    )
    toast.success(res.data.msg)
    approvalComment.value = ''
    await load()
  } catch (e) {
    toast.error(e.response?.data?.detail || '审批操作失败')
  } finally {
    actingApproval.value = null
  }
}

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// ── 转接 ──
// resolved/closed/rejected 是结束态，没有在办意义，不给转（和后端校验一致）
const transferOpen = ref(false)
const transferring = ref(false)
const agents = ref([])
const transferForm = ref({ target_agent_id: '', reason: '' })
const canTransfer = computed(() =>
  ticket.value && !['resolved', 'closed', 'rejected'].includes(ticket.value.status),
)
const agentOptions = computed(() => [
  { value: '', label: '选择接收坐席' },
  ...agents.value.map((a) => ({
    value: a.id,
    label: `${a.username}（${a.role_name === 'admin' ? '管理员' : '客服'}）`,
  })),
])

const openTransfer = async () => {
  transferForm.value = { target_agent_id: '', reason: '' }
  transferOpen.value = true
  if (agents.value.length) return
  try {
    const res = await api.get('/transfer/agents')
    agents.value = res.data
  } catch (e) {
    toast.error('坐席列表加载失败')
  }
}

const submitTransfer = async () => {
  if (!transferForm.value.target_agent_id) {
    toast.error('请选择接收坐席')
    return
  }
  transferring.value = true
  try {
    const res = await api.post('/transfer', null, {
      params: {
        ticket_id: ticket.value.id,
        target_agent_id: transferForm.value.target_agent_id,
        reason: transferForm.value.reason.trim(),
      },
    })
    toast.success(res.data.msg)
    transferOpen.value = false
  } catch (e) {
    toast.error(e.response?.data?.detail || '转接失败')
  } finally {
    transferring.value = false
  }
}

const statusMeta = computed(() => {
  const s = ticket.value?.status
  const map = {
    pending: { glow: 'rgba(245,158,11,0.14)', dot: '#f59e0b', ring: 'rgba(245,158,11,0.3)' },
    processing: { glow: 'rgba(56,189,248,0.12)', dot: '#38bdf8', ring: 'rgba(56,189,248,0.3)' },
    resolved: { glow: 'var(--brand-soft)', dot: 'var(--brand)', ring: 'var(--brand-glow)' },
    closed: { glow: 'rgba(120,130,125,0.1)', dot: 'var(--ink-3)', ring: 'var(--line-2)' },
    escalated: { glow: 'rgba(244,63,94,0.1)', dot: '#f43f5e', ring: 'rgba(244,63,94,0.3)' },
    rejected: { glow: 'rgba(244,63,94,0.1)', dot: '#f43f5e', ring: 'rgba(244,63,94,0.3)' },
    waiting: { glow: 'rgba(245,158,11,0.12)', dot: '#f59e0b', ring: 'rgba(245,158,11,0.3)' },
    accepted: { glow: 'var(--brand-soft)', dot: 'var(--brand)', ring: 'var(--brand-glow)' },
  }
  return map[s] || { glow: 'transparent', dot: 'var(--ink-3)', ring: 'var(--line)' }
})

onMounted(async () => {
  await Promise.all([load(), ensureUserLoaded()])  // 角色没加载时审批按钮显示不出来，要等它
  // 已解决的单才拉评分（没评过返回 null），喂给"去评分"/"已评价"两个态
  if (['resolved', 'closed'].includes(ticket.value?.status)) await loadCsat()
})
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <!-- 返回 -->
    <button
      class="group inline-flex items-center gap-1.5 text-[13px] text-ink-3 hover:text-ink transition-colors mb-5"
      @click="router.push('/tickets')"
    >
      <ArrowLeft class="w-3.5 h-3.5 transition-transform group-hover:-translate-x-0.5" />
      返回工单列表
    </button>

    <AppSkeleton v-if="loading" variant="card" />

    <template v-else-if="ticket">
      <div class="animate-fade-up">
        <!-- 状态色英雄带 -->
        <div class="relative rounded-lg overflow-hidden mb-5">
          <div
            class="absolute inset-[-60%] animate-conic-spin opacity-50"
            style="background: conic-gradient(from 0deg, transparent 0%, var(--brand) 14%, var(--ai) 32%, transparent 52%, transparent 100%)"
            aria-hidden="true"
          />
          <div class="relative m-px rounded-lg bg-surface overflow-hidden">
            <div
              class="absolute inset-0 animate-mesh-drift"
              :style="{ background: `radial-gradient(110% 90% at 6% 0%, ${statusMeta.glow} 0%, transparent 55%)`, backgroundSize: '150% 150%' }"
              aria-hidden="true"
            />
            <!-- 状态光晕球 -->
            <span
              class="absolute -right-10 -top-10 w-44 h-44 rounded-full blur-[60px] opacity-40 pointer-events-none animate-pulse-soft"
              :style="{ background: statusMeta.dot }"
              aria-hidden="true"
            />
            <div class="relative px-5 sm:px-8 py-7">
              <div class="flex items-center gap-2.5 mb-3 flex-wrap">
                <span class="text-[13px] font-mono text-ink-3 tabular-nums">#{{ ticket.id }}</span>
                <AppBadge :tone="ticketTones[ticket.status] || 'gray'" dot>
                  {{ statusLabels[ticket.status] || ticket.status }}
                </AppBadge>
                <AppBadge v-if="ticket.priority" :tone="priorityTones[ticket.priority] || 'gray'" size="sm">
                  {{ priorityLabels[ticket.priority] || ticket.priority }}优先级
                </AppBadge>
              </div>
              <h1 class="text-[22px] sm:text-[28px] font-semibold text-ink tracking-tight leading-snug max-w-2xl">{{ ticket.title }}</h1>
              <div class="flex flex-wrap items-center gap-4 mt-4">
                <p class="flex items-center gap-1.5 text-[12px] text-ink-3 tabular-nums">
                  <Clock class="w-3.5 h-3.5" />
                  创建于 {{ fmtTime(ticket.created_at) }}
                </p>
                <p v-if="ticket.department" class="flex items-center gap-1.5 text-[12px] text-ink-3">
                  <Activity class="w-3.5 h-3.5" />
                  {{ ticket.department }}
                </p>
              </div>
            </div>
          </div>
        </div>

        <!-- 评分邀请：自己的已解决单 + 没评过 -->
        <div
          v-if="canRate"
          class="rounded-card border border-amber/30 bg-amber-soft mb-5 px-4 sm:px-5 py-3.5 flex flex-wrap items-center gap-3 animate-fade-up"
        >
          <Star class="w-4.5 h-4.5 text-amber shrink-0" fill="currentColor" :stroke-width="1.5" />
          <p class="text-[13px] text-ink flex-1 min-w-[200px] leading-relaxed">
            这张工单已解决，给本次服务打个分——评分会计入 A/B 实验的 CSAT 指标
          </p>
          <AppButton size="sm" @click="csatOpen = true">
            <Star class="w-3.5 h-3.5" />
            去评分
          </AppButton>
        </div>

        <!-- 已评：星级 + 评语只读（刷新不丢） -->
        <div
          v-else-if="csat && isOwner"
          class="rounded-card border border-line bg-surface mb-5 px-4 sm:px-5 py-3.5 flex flex-wrap items-center gap-x-3 gap-y-1.5 animate-fade-up"
        >
          <span class="text-[13px] font-medium text-ink-2">我的评价</span>
          <StarRating :model-value="csat.score" readonly size="sm" />
          <span v-if="csat.comment" class="text-[13px] text-ink-2">「{{ csat.comment }}」</span>
          <span class="text-[12px] text-ink-3 tabular-nums ml-auto">{{ fmtTime(csat.created_at) }}</span>
        </div>

        <!-- 状态流转 -->
        <AppCard class="mb-5 overflow-x-auto">
          <AppStepper :steps="steps" :current="steps.some(s => s.value === ticket.status) ? ticket.status : 'pending'" />
        </AppCard>

        <!-- 审批链时间线：high/urgent 单才有 -->
        <AppCard v-if="ticket.approvals?.length" class="mb-5">
          <p class="flex items-center gap-1.5 text-[13px] font-medium text-ink-2 mb-4">
            <ShieldCheck class="w-3.5 h-3.5" />
            审批链
          </p>
          <ol class="space-y-3">
            <li
              v-for="a in ticket.approvals"
              :key="a.id"
              class="rounded-xl border border-line-soft px-4 py-3"
            >
              <div class="flex flex-wrap items-center gap-x-3 gap-y-2">
                <span
                  class="w-7 h-7 rounded-full flex items-center justify-center text-[12px] font-semibold shrink-0"
                  :class="approvalTones[a.status]?.circle"
                >{{ a.level }}</span>
                <span class="text-[13px] font-medium text-ink">{{ approverLabels[a.approver_role] || a.approver_role }}</span>
                <AppBadge :tone="approvalTones[a.status]?.badge || 'gray'" size="sm" dot>
                  {{ approvalTones[a.status]?.label || a.status }}
                </AppBadge>
                <!-- 已批过：批注 + 签字时间 -->
                <template v-if="a.status !== 'pending'">
                  <span v-if="a.comment" class="text-[12px] text-ink-2">「{{ a.comment }}」</span>
                  <span class="text-[12px] text-ink-3 tabular-nums">{{ fmtTime(a.decided_at) }}</span>
                </template>
                <!-- 轮到我批：意见框 + 通过/驳回 -->
                <template v-else-if="canDecide(a)">
                  <AppInput
                    v-model="approvalComment"
                    class="flex-1 min-w-[180px]"
                    placeholder="审批意见（可选）"
                  />
                  <div class="flex items-center gap-2 ml-auto">
                    <AppButton
                      variant="secondary"
                      size="sm"
                      :loading="actingApproval === `${a.id}-reject`"
                      @click="decide(a, 'reject')"
                    >
                      <X class="w-3.5 h-3.5" />
                      驳回
                    </AppButton>
                    <AppButton
                      variant="brand"
                      size="sm"
                      :loading="actingApproval === `${a.id}-approve`"
                      @click="decide(a, 'approve')"
                    >
                      <Check class="w-3.5 h-3.5" />
                      通过
                    </AppButton>
                  </div>
                </template>
                <!-- 不归我批的空格子：只提示等谁 -->
                <span v-else class="text-[12px] text-ink-3 ml-auto">等待{{ approverLabels[a.approver_role] || a.approver_role }}</span>
              </div>
            </li>
          </ol>
        </AppCard>

        <!-- 描述 + 侧栏 双栏 -->
        <div class="grid lg:grid-cols-[1fr_260px] gap-4 items-start">
          <AppCard>
            <p class="flex items-center gap-1.5 text-[13px] font-medium text-ink-2 mb-4">
              <FileText class="w-3.5 h-3.5" />
              问题描述
            </p>
            <p class="text-sm text-ink leading-relaxed whitespace-pre-wrap">{{ ticket.content }}</p>
          </AppCard>

          <div class="space-y-4">
            <!-- 操作面板 -->
            <AppCard v-if="actions.length || canTransfer">
              <p class="flex items-center gap-1.5 text-[13px] font-medium text-ink-2 mb-4">
                <Zap class="w-3.5 h-3.5" />
                流转操作
              </p>
              <div class="flex flex-col gap-2">
                <AppButton
                  v-for="a in actions"
                  :key="a.to"
                  :variant="a.variant"
                  :loading="acting"
                  block
                  @click="setStatus(a.to)"
                >
                  <component v-if="a.icon" :is="a.icon" class="w-3.5 h-3.5" />
                  {{ a.label }}
                </AppButton>
                <AppButton v-if="canTransfer" variant="secondary" block @click="openTransfer">
                  <ArrowRightLeft class="w-3.5 h-3.5" />
                  转接工单
                </AppButton>
              </div>
            </AppCard>

            <!-- 工单元信息 -->
            <AppCard>
              <p class="flex items-center gap-1.5 text-[13px] font-medium text-ink-2 mb-4">
                <User class="w-3.5 h-3.5" />
                工单信息
              </p>
              <dl class="space-y-3 text-[13px]">
                <div class="flex justify-between">
                  <dt class="text-ink-3">工单号</dt>
                  <dd class="font-mono text-ink tabular-nums">#{{ ticket.id }}</dd>
                </div>
                <div class="flex justify-between">
                  <dt class="text-ink-3">状态</dt>
                  <dd><AppBadge :tone="ticketTones[ticket.status] || 'gray'" size="sm">{{ statusLabels[ticket.status] || ticket.status }}</AppBadge></dd>
                </div>
                <div v-if="ticket.priority" class="flex justify-between">
                  <dt class="text-ink-3">优先级</dt>
                  <dd><AppBadge :tone="priorityTones[ticket.priority] || 'gray'" size="sm">{{ priorityLabels[ticket.priority] || ticket.priority }}</AppBadge></dd>
                </div>
                <div v-if="ticket.requester" class="flex justify-between">
                  <dt class="text-ink-3">提交人</dt>
                  <dd class="text-ink">{{ ticket.requester }}</dd>
                </div>
                <div v-if="ticket.department" class="flex justify-between">
                  <dt class="text-ink-3">部门</dt>
                  <dd class="text-ink">{{ ticket.department }}</dd>
                </div>
                <div class="flex justify-between">
                  <dt class="text-ink-3">创建时间</dt>
                  <dd class="text-ink tabular-nums">{{ fmtTime(ticket.created_at) }}</dd>
                </div>
              </dl>
            </AppCard>
          </div>
        </div>
      </div>
    </template>

    <!-- 转接弹窗 -->
    <AppModal v-model="transferOpen" title="转接工单" size="sm">
      <p class="text-sm text-ink-2 leading-relaxed">
        把 <span class="font-mono font-semibold text-ink">#{{ ticket?.id }}</span>
        转给其他坐席协同处理，对方在「转接」页接受后接手这张单。
      </p>
      <div class="space-y-4 mt-4">
        <div>
          <label class="block text-[12px] font-medium text-ink-2 mb-1.5">接收人</label>
          <AppSelect v-model="transferForm.target_agent_id" :options="agentOptions" />
        </div>
        <AppInput
          v-model="transferForm.reason"
          label="转接原因"
          placeholder="选填，如 涉及服务器权限，需 IT 坐席跟进"
        />
      </div>
      <template #footer>
        <AppButton variant="secondary" @click="transferOpen = false">取消</AppButton>
        <AppButton :loading="transferring" @click="submitTransfer">发起转接</AppButton>
      </template>
    </AppModal>

    <!-- 评分弹窗：提交成功后 loadCsat 刷成"已评价"态；ticket 未加载完时 ?. 兜底 -->
    <CsatModal v-model="csatOpen" :ticket-id="ticket?.id" @done="loadCsat" />
  </div>
</template>
