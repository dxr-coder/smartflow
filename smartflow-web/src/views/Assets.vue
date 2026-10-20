<!--
  Assets — 资产领用/归还（IT 设备台账）
  数据流：GET /assets（category/mine 筛选，返回含购置日期/价格/保修到期/存放位置台账字段）；
         领用 POST /assets/:id/borrow；归还 POST /assets/:id/return；
         admin：入库 POST /assets（query 参数含台账字段）、报废 POST /assets/:id/scrap、流水 GET /assets/:id/logs
  视觉：PageHero + 状态汇总玻璃条 + 资产卡片网格（状态色条 + hover 光晕 + 台账信息行）+ AppModal 入库/报废/流水
-->
<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import {
  Package, Laptop, Monitor, Smartphone, BadgeCheck, Box,
  Plus, Undo2, ArchiveX, ScrollText, User, ShieldCheck,
  CalendarDays, MapPin, StickyNote, AlertTriangle,
} from 'lucide-vue-next'
import api from '../api'
import { toast } from '../composables/useToast'
import { useAuth, ensureUserLoaded } from '../composables/useAuth'
import AppCard from '../components/ui/AppCard.vue'
import AppBadge from '../components/ui/AppBadge.vue'
import AppButton from '../components/ui/AppButton.vue'
import AppModal from '../components/ui/AppModal.vue'
import AppInput from '../components/ui/AppInput.vue'
import AppSelect from '../components/ui/AppSelect.vue'
import AppEmptyState from '../components/ui/AppEmptyState.vue'
import AppSkeleton from '../components/ui/AppSkeleton.vue'
import PageHero from '../components/layout/PageHero.vue'

const { userInfo } = useAuth()
const isAdmin = computed(() => userInfo.value?.role_name === 'admin')

const assets = ref([])
const loading = ref(true)
const tab = ref('all')          // all 全部资产 / mine 我的领用
const category = ref('')        // 类别筛选，空 = 全部
const actingKey = ref('')       // "id-action"，按钮转圈定位用

// 类别：值和后端 ASSET_CATEGORIES 白名单保持一致
const categoryOptions = [
  { value: '', label: '全部类别' },
  { value: 'laptop', label: '笔记本' },
  { value: 'monitor', label: '显示器' },
  { value: 'phone', label: '手机' },
  { value: 'badge', label: '工牌' },
  { value: 'other', label: '其他' },
]
const catIcons = { laptop: Laptop, monitor: Monitor, phone: Smartphone, badge: BadgeCheck, other: Box }
const catLabels = { laptop: '笔记本', monitor: '显示器', phone: '手机', badge: '工牌', other: '其他' }

const statusMeta = {
  available: { label: '在库', tone: 'brand', bar: 'bg-brand', glow: 'rgba(0,220,130,0.14)' },
  in_use: { label: '已领用', tone: 'amber', bar: 'bg-amber', glow: 'rgba(245,158,11,0.16)' },
  retired: { label: '已报废', tone: 'gray', bar: 'bg-ink-3', glow: 'transparent' },
}

// 状态汇总条：从当前列表即时统计
const summary = computed(() => {
  const counts = {}
  for (const a of assets.value) counts[a.status] = (counts[a.status] || 0) + 1
  return [
    { label: '全部', value: assets.value.length },
    { label: '在库', value: counts.available || 0 },
    { label: '已领用', value: counts.in_use || 0 },
    { label: '已报废', value: counts.retired || 0 },
  ]
})

const load = async () => {
  loading.value = true
  try {
    const params = {}
    if (category.value) params.category = category.value
    if (tab.value === 'mine') params.mine = true
    const res = await api.get('/assets', { params })
    assets.value = res.data
  } catch (e) {
    toast.error('资产加载失败')
  } finally {
    loading.value = false
  }
}
watch([tab, category], load)

// ── 领用 / 归还 ──
const act = async (a, action) => {
  actingKey.value = `${a.id}-${action}`
  try {
    const res = await api.post(`/assets/${a.id}/${action}`)
    toast.success(res.data.msg)
    await load()
  } catch (e) {
    toast.error(e.response?.data?.detail || '操作失败')
  } finally {
    actingKey.value = ''
  }
}

// ── 入库（admin）──
const createOpen = ref(false)
const creating = ref(false)
const emptyForm = () => ({
  asset_no: '', category: 'laptop', model: '',
  purchase_date: '', price: '', warranty_end: '', location: '', note: '',
})
const form = ref(emptyForm())
const create = async () => {
  if (!form.value.asset_no.trim()) {
    toast.error('请填写资产编号')
    return
  }
  creating.value = true
  try {
    await api.post('/assets', null, {
      params: {
        asset_no: form.value.asset_no.trim(),
        category: form.value.category,
        model: form.value.model.trim(),
        purchase_date: form.value.purchase_date || undefined,
        price: form.value.price || undefined,
        warranty_end: form.value.warranty_end || undefined,
        location: form.value.location.trim(),
        note: form.value.note.trim(),
      },
    })
    toast.success('入库成功')
    createOpen.value = false
    form.value = emptyForm()
    load()
  } catch (e) {
    toast.error(e.response?.data?.detail || '入库失败')
  } finally {
    creating.value = false
  }
}

// ── 报废确认（admin）──
const scrapOpen = ref(false)
const scrapTarget = ref(null)
const scrapReason = ref('')
const confirmScrap = async () => {
  if (!scrapTarget.value) return
  actingKey.value = `${scrapTarget.value.id}-scrap`
  try {
    const res = await api.post(`/assets/${scrapTarget.value.id}/scrap`, null, {
      params: { reason: scrapReason.value },
    })
    toast.success(res.data.msg)
    scrapOpen.value = false
    scrapReason.value = ''
    await load()
  } catch (e) {
    toast.error(e.response?.data?.detail || '报废失败')
  } finally {
    actingKey.value = ''
  }
}

// ── 流水（admin）──
const logsOpen = ref(false)
const logsTarget = ref(null)
const logs = ref([])
const loadingLogs = ref(false)
const openLogs = async (a) => {
  logsTarget.value = a
  logsOpen.value = true
  loadingLogs.value = true
  try {
    const res = await api.get(`/assets/${a.id}/logs`)
    logs.value = res.data
  } catch (e) {
    toast.error('流水加载失败')
  } finally {
    loadingLogs.value = false
  }
}
const actionLabels = { create: '入库', borrow: '领用', return: '归还', scrap: '报废' }
const actionTones = { create: 'brand', borrow: 'amber', return: 'blue', scrap: 'red' }

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

// 保修状态：已过保红、30 天内将至琥珀、正常灰
// textClass 必须是完整类名字符串——Tailwind 是静态扫描的，拼接的 text-${tone} 不会生成
const warrantyMeta = (a) => {
  if (!a.warranty_end) return null
  const end = new Date(a.warranty_end)
  const days = Math.ceil((end - Date.now()) / 86400000)
  if (days < 0) return { textClass: 'text-red', label: `已过保 ${Math.abs(days)} 天`, warn: true }
  if (days <= 30) return { textClass: 'text-amber', label: `保修将至（剩 ${days} 天）`, warn: true }
  return { textClass: 'text-ink-3', label: `保修至 ${String(a.warranty_end).slice(0, 10)}`, warn: false }
}
const fmtPrice = (p) => (p == null ? '' : `¥${Number(p).toLocaleString('zh-CN')}`)

onMounted(async () => {
  await Promise.all([load(), ensureUserLoaded()])  // admin 按钮依赖角色，等 /auth/me
})
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 py-6 sm:py-8">
    <PageHero title="资产" subtitle="公司设备台账：在库的可以领，自己名下的记得还">
      <AppButton v-if="isAdmin" @click="createOpen = true">
        <Plus class="w-4 h-4" />
        <span class="hidden sm:inline">入库</span>
      </AppButton>
    </PageHero>

    <!-- 页签 + 类别筛选 -->
    <div class="flex items-center gap-3 mt-4 mb-4 flex-wrap">
      <div class="flex items-center p-1 rounded-ctl bg-surface-2 border border-line">
        <button
          v-for="t in [{ v: 'all', l: '全部资产' }, { v: 'mine', l: '我的领用' }]"
          :key="t.v"
          class="px-3.5 py-1.5 rounded-[7px] text-[13px] font-medium transition-all duration-150"
          :class="tab === t.v ? 'bg-surface text-ink shadow-sm' : 'text-ink-3 hover:text-ink'"
          @click="tab = t.v"
        >{{ t.l }}</button>
      </div>
      <AppSelect v-model="category" :options="categoryOptions" size="sm" class="w-36" />
    </div>

    <!-- 状态汇总条 -->
    <div
      v-if="!loading && assets.length"
      class="flex items-center gap-2 mb-5 p-3 rounded-card bg-glass backdrop-blur-md border border-line animate-fade-up overflow-x-auto"
    >
      <div
        v-for="(s, i) in summary"
        :key="s.label"
        class="flex items-center gap-2.5 px-3.5 py-2 rounded-ctl shrink-0"
        :class="i < summary.length - 1 ? 'border-r border-line' : ''"
      >
        <span class="w-7 h-7 rounded-[8px] bg-surface-2 flex items-center justify-center">
          <Package class="w-3.5 h-3.5 text-ink-2" :stroke-width="2" />
        </span>
        <div>
          <p class="text-[15px] font-bold text-ink leading-none tabular-nums">{{ s.value }}</p>
          <p class="text-[11px] text-ink-3 mt-0.5">{{ s.label }}</p>
        </div>
      </div>
    </div>

    <!-- 骨架 -->
    <div v-if="loading" class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <AppSkeleton v-for="i in 6" :key="i" variant="card" />
    </div>

    <!-- 空状态 -->
    <AppEmptyState
      v-else-if="!assets.length"
      :icon="Package"
      :title="tab === 'mine' ? '你还没有领用任何资产' : '台账是空的'"
      :description="tab === 'mine' ? '去「全部资产」里挑一台领用。' : (isAdmin ? '点右上角「入库」录入第一台设备。' : '等管理员录入资产后就能看到。')"
    />

    <!-- 卡片网格 -->
    <div v-else class="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
      <AppCard
        v-for="(a, i) in assets"
        :key="a.id"
        padding="none"
        class="group relative overflow-hidden animate-rise"
        :style="{ animationDelay: `${i * 40}ms` }"
      >
        <!-- 状态色条 + hover 光晕 -->
        <div
          class="absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity duration-300 pointer-events-none"
          :style="{ background: `linear-gradient(160deg, ${statusMeta[a.status]?.glow} 0%, transparent 55%)` }"
          aria-hidden="true"
        />
        <div class="relative flex">
          <div class="w-[3px] shrink-0" :class="statusMeta[a.status]?.bar || 'bg-ink-3'" />
          <div class="flex-1 p-4">
            <div class="flex items-center gap-2 mb-2.5">
              <span class="w-8 h-8 rounded-[9px] bg-surface-2 flex items-center justify-center shrink-0">
                <component :is="catIcons[a.category] || Box" class="w-4 h-4 text-ink-2" :stroke-width="1.8" />
              </span>
              <div class="min-w-0 flex-1">
                <p class="text-[13px] font-mono font-semibold text-ink truncate tabular-nums">{{ a.asset_no }}</p>
                <p class="text-[11px] text-ink-3">{{ catLabels[a.category] || a.category }}<template v-if="a.model"> · {{ a.model }}</template></p>
              </div>
              <AppBadge :tone="statusMeta[a.status]?.tone || 'gray'" size="sm" dot>
                {{ statusMeta[a.status]?.label || a.status }}
              </AppBadge>
            </div>

            <!-- 持有人 -->
            <p class="flex items-center gap-1.5 text-[12px] text-ink-2 mb-2 h-[18px]">
              <User class="w-3.5 h-3.5 text-ink-3" />
              <template v-if="a.holder_name">{{ a.holder_name }}</template>
              <template v-else-if="a.status === 'retired'"><span class="text-ink-3">已退出流通</span></template>
              <template v-else><span class="text-ink-3">无人占用</span></template>
            </p>

            <!-- 台账信息：位置 / 购置 / 价格 / 保修 -->
            <div class="space-y-1 mb-3 min-h-[40px]">
              <p class="flex items-center gap-1.5 text-[12px] text-ink-2">
                <MapPin class="w-3.5 h-3.5 text-ink-3 shrink-0" />
                <span class="truncate">{{ a.location || '未登记位置' }}</span>
                <span v-if="a.price != null" class="ml-auto shrink-0 font-medium tabular-nums">{{ fmtPrice(a.price) }}</span>
              </p>
              <p class="flex items-center gap-1.5 text-[12px] text-ink-2 flex-wrap">
                <CalendarDays class="w-3.5 h-3.5 text-ink-3 shrink-0" />
                <template v-if="a.purchase_date">
                  购置 {{ String(a.purchase_date).slice(0, 10) }}
                  <span v-if="warrantyMeta(a)" class="text-ink-3">·</span>
                </template>
                <span v-if="warrantyMeta(a)" :class="warrantyMeta(a).textClass">
                  <template v-if="warrantyMeta(a).warn">
                    <AlertTriangle class="w-3 h-3 inline -mt-0.5 mr-0.5" />
                  </template>
                  {{ warrantyMeta(a).label }}
                </span>
                <span v-else-if="!a.purchase_date" class="text-ink-3">无台账信息</span>
              </p>
              <p v-if="a.note" class="flex items-center gap-1.5 text-[12px] text-ink-3">
                <StickyNote class="w-3.5 h-3.5 shrink-0" />
                <span class="truncate" :title="a.note">{{ a.note }}</span>
              </p>
            </div>

            <!-- 操作行 -->
            <div class="flex items-center gap-2">
              <!-- 全部页签：在库的可领 -->
              <AppButton
                v-if="tab !== 'mine' && a.status === 'available'"
                size="sm"
                :loading="actingKey === `${a.id}-borrow`"
                @click="act(a, 'borrow')"
              >
                领用
              </AppButton>
              <!-- 我的页签：名下的可还 -->
              <AppButton
                v-if="tab === 'mine' && a.status === 'in_use'"
                size="sm"
                variant="secondary"
                :loading="actingKey === `${a.id}-return`"
                @click="act(a, 'return')"
              >
                <Undo2 class="w-3.5 h-3.5" />
                归还
              </AppButton>
              <AppButton
                v-if="isAdmin"
                size="sm"
                variant="ghost"
                class="ml-auto"
                @click="openLogs(a)"
              >
                <ScrollText class="w-3.5 h-3.5" />
              </AppButton>
              <AppButton
                v-if="isAdmin && a.status !== 'retired'"
                size="sm"
                variant="ghost"
                :loading="actingKey === `${a.id}-scrap`"
                @click="scrapTarget = a; scrapOpen = true"
              >
                <ArchiveX class="w-3.5 h-3.5" />
              </AppButton>
            </div>
          </div>
        </div>
      </AppCard>
    </div>

    <!-- 入库弹窗（admin）-->
    <AppModal v-model="createOpen" title="资产入库" size="md">
      <div class="space-y-4">
        <AppInput v-model="form.asset_no" label="资产编号" placeholder="如 NB-2026-002，全局唯一" />
        <div class="grid grid-cols-2 gap-3">
          <div>
            <label class="block text-[12px] font-medium text-ink-2 mb-1.5">类别</label>
            <AppSelect v-model="form.category" :options="categoryOptions.filter(o => o.value)" />
          </div>
          <AppInput v-model="form.model" label="品牌型号" placeholder="选填，如 ThinkPad T14" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <AppInput v-model="form.purchase_date" type="date" label="购置日期" />
          <AppInput v-model="form.price" type="number" label="采购价格（元）" placeholder="选填，如 6499" />
        </div>
        <div class="grid grid-cols-2 gap-3">
          <AppInput v-model="form.warranty_end" type="date" label="保修到期" />
          <AppInput v-model="form.location" label="存放位置" placeholder="选填，如 IT库房-柜1" />
        </div>
        <AppInput v-model="form.note" label="备注" placeholder="选填，如 设计岗专用" />
      </div>
      <template #footer>
        <AppButton variant="secondary" @click="createOpen = false">取消</AppButton>
        <AppButton :loading="creating" @click="create">入库</AppButton>
      </template>
    </AppModal>

    <!-- 报废确认（admin）-->
    <AppModal v-model="scrapOpen" title="报废确认" size="sm">
      <p class="text-sm text-ink-2 leading-relaxed">
        确定报废 <span class="font-mono font-semibold text-ink">{{ scrapTarget?.asset_no }}</span> 吗？
        报废是终态，之后谁也领不了这台。
      </p>
      <div class="mt-4">
        <AppInput v-model="scrapReason" label="报废原因" placeholder="选填，如 屏幕碎裂 / 无法开机" />
      </div>
      <template #footer>
        <AppButton variant="secondary" @click="scrapOpen = false">再想想</AppButton>
        <AppButton variant="danger" @click="confirmScrap">确认报废</AppButton>
      </template>
    </AppModal>

    <!-- 流水弹窗（admin）-->
    <AppModal v-model="logsOpen" :title="`流转流水 · ${logsTarget?.asset_no || ''}`" size="md">
      <AppSkeleton v-if="loadingLogs" variant="text" />
      <p v-else-if="!logs.length" class="text-sm text-ink-3 py-4 text-center">还没有流转记录</p>
      <ol v-else class="space-y-2.5 max-h-80 overflow-y-auto pr-1">
        <li v-for="l in logs" :key="l.id" class="flex items-center gap-3 text-[13px]">
          <AppBadge :tone="actionTones[l.action] || 'gray'" size="sm">{{ actionLabels[l.action] || l.action }}</AppBadge>
          <span class="text-ink">{{ l.user_name || '未知用户' }}</span>
          <span v-if="l.operator_name && l.operator_name !== l.user_name" class="text-[12px] text-ink-3">由 {{ l.operator_name }} 代办</span>
          <span v-if="l.note" class="text-[12px] text-ink-2 truncate">「{{ l.note }}」</span>
          <span class="ml-auto text-[12px] text-ink-3 tabular-nums shrink-0">{{ fmtTime(l.created_at) }}</span>
        </li>
      </ol>
    </AppModal>
  </div>
</template>
