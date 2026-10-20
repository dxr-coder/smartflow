<!--
  AuditLogs — 审计日志
  数据流：GET /audit/logs?page= → {items, total}；AppPagination 分页
-->
<script setup>
import { ref, onMounted, watch } from 'vue'
import { ScrollText } from 'lucide-vue-next'
import api from '../../api'
import AppTable from '../../components/ui/AppTable.vue'
import AppBadge from '../../components/ui/AppBadge.vue'
import AppPagination from '../../components/ui/AppPagination.vue'
import PageHero from '../../components/layout/PageHero.vue'

const items = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = 20
const loading = ref(true)

const columns = [
  { key: 'action', label: '动作', primary: true },
  { key: 'username', label: '操作者' },
  { key: 'detail', label: '详情' },
  { key: 'created_at', label: '时间' },
]

const actionTone = (action) => (action === 'sensitive_blocked' ? 'red' : 'gray')

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/audit/logs', { params: { page: page.value } })
    items.value = res.data.items || []
    total.value = res.data.total || 0
  } catch (e) {
    /* 全局 handler */
  } finally {
    loading.value = false
  }
}

watch(page, load)
onMounted(load)

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}
</script>

<template>
  <div>
    <PageHero
      title="审计日志"
      subtitle="敏感操作与系统行为追溯"
      :count="total ? `${total} 条` : ''"
    />

    <AppTable :columns="columns" :rows="items" :loading="loading" empty-text="暂无日志">
      <template #cell-action="{ row }">
        <AppBadge :tone="actionTone(row.action)" size="sm" :dot="row.action === 'sensitive_blocked'">
          {{ row.action }}
        </AppBadge>
      </template>
      <template #cell-detail="{ row }">
        <span class="text-[13px] text-ink-2 line-clamp-2">{{ row.detail || '—' }}</span>
      </template>
      <template #cell-created_at="{ row }">
        <span class="tabular-nums text-[13px]">{{ fmtTime(row.created_at) }}</span>
      </template>
    </AppTable>

    <div class="mt-5">
      <AppPagination v-model:page="page" :total="total" :page-size="pageSize" />
    </div>
  </div>
</template>
