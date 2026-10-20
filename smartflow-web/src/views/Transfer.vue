<!--
  Transfer — 工单转接
  数据流：GET /transfer?scope=mine|out|all 列表（后端 JOIN 工单标题 + 转出人/接收人）；
         PUT /transfer/:id/accept 接受 / decline 拒绝（仅接收人本人，乐观更新 + toast）
  状态机：waiting 待接受 → connected 已接受 / declined 已拒绝（后两者终态）
  视觉：PageHero + 页签（转给我的带待处理角标）+ 状态汇总玻璃条 + 方向流动卡片
        （waiting 琥珀呼吸点 / connected 品牌色 / declined 灰沉底），工单号与标题可点进详情
-->
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowRightLeft, ArrowRight, Inbox, CheckCircle2, Ban, Check } from 'lucide-vue-next'
import api from '../api'
import { toast } from '../composables/useToast'
import { useAuth } from '../composables/useAuth'
import AppCard from '../components/ui/AppCard.vue'
import AppBadge from '../components/ui/AppBadge.vue'
import AppButton from '../components/ui/AppButton.vue'
import AppEmptyState from '../components/ui/AppEmptyState.vue'
import AppSkeleton from '../components/ui/AppSkeleton.vue'
import PageHero from '../components/layout/PageHero.vue'

const router = useRouter()
const { userInfo } = useAuth()
const isStaff = computed(() => ['agent', 'admin'].includes(userInfo.value?.role_name))

const transfers = ref([])
const loading = ref(true)
const tab = ref('mine')        // mine 转给我的 / out 我发起的 / all 全部（坐席管理员）
const actingKey = ref('')      // "id-action"，按钮转圈定位用

const tabs = computed(() => {
  const list = [
    { v: 'mine', l: '转给我的' },
    { v: 'out', l: '我发起的' },
  ]
  if (isStaff.value) list.push({ v: 'all', l: '全部' })
  return list
})

const statusMeta = {
  waiting: { label: '待接受', tone: 'amber', bar: 'bg-amber', dot: true },
  connected: { label: '已接受', tone: 'brand', bar: 'bg-brand', dot: false },
  declined: { label: '已拒绝', tone: 'red', bar: 'bg-ink-3', dot: false },
}

// 状态汇总条：从当前页签的列表即时统计
const summary = computed(() => {
  const c = {}
  for (const t of transfers.value) c[t.status] = (c[t.status] || 0) + 1
  return [
    { label: '全部', value: transfers.value.length, icon: ArrowRightLeft, tone: 'text-ink-2', bg: 'bg-surface-2' },
    { label: '待接受', value: c.waiting || 0, icon: Inbox, tone: 'text-amber', bg: 'bg-amber-soft' },
    { label: '已接受', value: c.connected || 0, icon: CheckCircle2, tone: 'text-brand', bg: 'bg-brand-soft' },
    { label: '已拒绝', value: c.declined || 0, icon: Ban, tone: 'text-red', bg: 'bg-red-soft' },
  ]
})

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/transfer', { params: { scope: tab.value } })
    transfers.value = res.data.items || res.data
  } catch (e) {
    toast.error(e.response?.data?.detail || '转接列表加载失败')
  } finally {
    loading.value = false
  }
}
watch(tab, load)

// 接受 / 拒绝：乐观更新，失败回滚（后端是抢锁式 UPDATE，可能被抢先）
const act = async (t, action) => {
  actingKey.value = `${t.id}-${action}`
  const prev = t.status
  t.status = action === 'accept' ? 'connected' : 'declined'
  try {
    const res = await api.put(`/transfer/${t.id}/${action}`)
    toast.success(res.data.msg)
  } catch (e) {
    t.status = prev
    toast.error(e.response?.data?.detail || '操作失败')
  } finally {
    actingKey.value = ''
  }
}

const goTicket = (id) => router.push(`/tickets/${id}`)

onMounted(load)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <PageHero
      title="工单转接"
      subtitle="把单转给更合适的坐席，接受后由对方接手处理"
    />

    <!-- 页签 -->
    <div class="flex items-center p-1 rounded-ctl bg-surface-2 border border-line mt-4 mb-4 w-fit">
      <button
        v-for="t in tabs"
        :key="t.v"
        class="px-3.5 py-1.5 rounded-[7px] text-[13px] font-medium transition-all duration-150"
        :class="tab === t.v ? 'bg-surface text-ink shadow-sm' : 'text-ink-3 hover:text-ink'"
        @click="tab = t.v"
      >
        {{ t.l }}
        <span
          v-if="t.v === 'mine' && transfers.filter(x => x.status === 'waiting').length"
          class="ml-1 inline-flex items-center justify-center min-w-[16px] h-4 px-1 rounded-full bg-amber text-[10px] font-bold text-white tabular-nums align-middle"
        >{{ transfers.filter(x => x.status === 'waiting').length }}</span>
      </button>
    </div>

    <!-- 状态汇总玻璃条 -->
    <div
      v-if="!loading && transfers.length"
      class="flex items-center gap-2 mb-5 p-3 rounded-card bg-glass backdrop-blur-md border border-line animate-fade-up overflow-x-auto"
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
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="space-y-3">
      <AppSkeleton v-for="i in 3" :key="i" variant="card" />
    </div>

    <!-- 空状态按页签区分 -->
    <AppEmptyState
      v-else-if="!transfers.length"
      :icon="ArrowRightLeft"
      :title="tab === 'mine' ? '没有转给你的工单' : tab === 'out' ? '你还没有发起过转接' : '还没有转接记录'"
      :description="tab === 'mine' ? '当有工单转接给你时，会出现在这里等你确认。' : tab === 'out' ? '在工单详情页点「转接工单」，可以把单转给其他坐席。' : '工单在坐席之间流转的记录会汇总在这里。'"
    />

    <!-- 转接卡片列表 -->
    <div v-else class="space-y-2.5">
      <AppCard
        v-for="(t, i) in transfers"
        :key="t.id"
        padding="none"
        class="group relative overflow-hidden animate-rise"
        :style="{ animationDelay: `${i * 50}ms` }"
      >
        <div class="relative flex">
          <div
            class="w-[3px] shrink-0 transition-all duration-200 group-hover:w-[5px]"
            :class="statusMeta[t.status]?.bar || 'bg-ink-3'"
          />
          <div class="flex-1 p-4 sm:px-5 min-w-0">
            <div class="flex items-center gap-2 flex-wrap mb-1.5">
              <button
                class="text-[12px] font-mono text-ink-3 tabular-nums hover:text-brand transition-colors"
                @click="goTicket(t.ticket_id)"
              >#{{ t.ticket_id }}</button>
              <AppBadge :tone="statusMeta[t.status]?.tone || 'gray'" size="sm" :dot="statusMeta[t.status]?.dot">
                {{ statusMeta[t.status]?.label || t.status }}
              </AppBadge>
              <span v-if="tab === 'out' && t.status === 'waiting'" class="text-[12px] text-ink-3 ml-auto">
                等待 {{ t.to_name }} 接受
              </span>
            </div>

            <!-- 工单标题：可点进详情 -->
            <button
              class="block text-left text-sm font-medium text-ink hover:text-brand transition-colors leading-snug"
              @click="goTicket(t.ticket_id)"
            >{{ t.ticket_title || `工单 #${t.ticket_id}` }}</button>

            <!-- 方向行：转出人 → 接收人 -->
            <p class="flex items-center gap-1.5 text-[13px] text-ink-2 mt-2">
              <span>{{ t.from_name || '未知用户' }}</span>
              <ArrowRight class="w-3.5 h-3.5 text-ink-3 shrink-0" />
              <span class="font-medium" :class="t.status === 'waiting' ? 'text-amber' : 'text-ink'">{{ t.to_name || '未知用户' }}</span>
            </p>

            <p v-if="t.reason" class="text-[13px] text-ink-2 mt-1.5 leading-relaxed">{{ t.reason }}</p>

            <div class="flex items-center gap-2 mt-3">
              <span class="text-[11px] text-ink-3 tabular-nums">{{ fmtTime(t.created_at) }}</span>
              <!-- 转给我的且待接受：拒绝 / 接受 -->
              <div v-if="tab === 'mine' && t.status === 'waiting'" class="flex items-center gap-2 ml-auto">
                <AppButton
                  size="sm"
                  variant="secondary"
                  :loading="actingKey === `${t.id}-decline`"
                  @click="act(t, 'decline')"
                >
                  拒绝
                </AppButton>
                <AppButton
                  size="sm"
                  :loading="actingKey === `${t.id}-accept`"
                  @click="act(t, 'accept')"
                >
                  <Check class="w-3.5 h-3.5" />
                  接受
                </AppButton>
              </div>
            </div>
          </div>
        </div>
      </AppCard>
    </div>
  </div>
</template>
