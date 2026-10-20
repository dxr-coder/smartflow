<!--
  Users — 用户管理
  数据流：GET /users；PUT /users/:id/role?role_name=；PUT /users/:id/status?status=
  视觉：PageHero 英雄区 + AppTable
-->
<script setup>
import { ref, onMounted } from 'vue'
import { RefreshCw, ShieldCheck, Ban, CheckCircle2 } from 'lucide-vue-next'
import api from '../../api'
import { toast } from '../../composables/useToast'
import { roleTones } from '../../utils/badges'
import AppTable from '../../components/ui/AppTable.vue'
import AppBadge from '../../components/ui/AppBadge.vue'
import AppButton from '../../components/ui/AppButton.vue'
import AppSelect from '../../components/ui/AppSelect.vue'
import AppAvatar from '../../components/ui/AppAvatar.vue'
import PageHero from '../../components/layout/PageHero.vue'

const users = ref([])
const loading = ref(true)
const actingId = ref(null)

const roleOptions = [
  { value: 'user', label: '普通用户' },
  { value: 'support', label: '客服' },
  { value: 'admin', label: '管理员' },
]

const roleLabels = { user: '普通用户', support: '客服', admin: '管理员' }
const statusLabels = { active: '正常', disabled: '已禁用' }

const columns = [
  { key: 'username', label: '用户', primary: true },
  { key: 'role_name', label: '角色' },
  { key: 'status', label: '状态' },
]

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/users')
    users.value = res.data.items || res.data
  } catch (e) {
    toast.error('用户加载失败')
  } finally {
    loading.value = false
  }
}

const setRole = async (u, role) => {
  actingId.value = u.id
  const prev = u.role_name
  u.role_name = role
  try {
    await api.put(`/users/${u.id}/role`, null, { params: { role_name: role } })
    toast.success(`${u.username} 已设为${roleLabels[role]}`)
  } catch (e) {
    u.role_name = prev
    toast.error('角色更新失败')
  } finally {
    actingId.value = null
  }
}

const toggleStatus = async (u) => {
  const next = u.status === 'active' ? 'disabled' : 'active'
  actingId.value = u.id
  const prev = u.status
  u.status = next
  try {
    await api.put(`/users/${u.id}/status`, null, { params: { status: next } })
    toast.success(next === 'disabled' ? '已禁用' : '已启用')
  } catch (e) {
    u.status = prev
    toast.error('状态更新失败')
  } finally {
    actingId.value = null
  }
}

onMounted(load)
</script>

<template>
  <div>
    <PageHero
      title="用户管理"
      subtitle="账号角色与权限状态"
      :count="users.length ? `${users.length} 个账号` : ''"
    >
      <AppButton variant="secondary" size="sm" :loading="loading" @click="load">
        <RefreshCw class="w-3.5 h-3.5" :class="loading ? 'animate-spin-dot' : ''" />
        刷新
      </AppButton>
    </PageHero>

    <AppTable :columns="columns" :rows="users" :loading="loading" empty-text="暂无用户">
      <template #cell-username="{ row }">
        <div class="flex items-center gap-3">
          <AppAvatar :name="row.username" size="sm" />
          <span class="font-medium text-ink">{{ row.username }}</span>
        </div>
      </template>

      <template #cell-role_name="{ row }">
        <div class="w-28">
          <AppSelect
            :model-value="row.role_name"
            :options="roleOptions"
            size="sm"
            :disabled="actingId === row.id"
            @update:model-value="setRole(row, $event)"
          />
        </div>
      </template>

      <template #cell-status="{ row }">
        <div class="flex items-center gap-2">
          <AppBadge :tone="row.status === 'active' ? 'brand' : 'red'" size="sm" :dot="row.status === 'active'">
            {{ statusLabels[row.status] || row.status }}
          </AppBadge>
          <button
            class="p-1.5 rounded-ctl transition-all duration-150"
            :class="row.status === 'active' ? 'text-ink-3 hover:text-red hover:bg-red-soft' : 'text-ink-3 hover:text-brand hover:bg-brand-soft'"
            :disabled="actingId === row.id"
            :aria-label="row.status === 'active' ? '禁用' : '启用'"
            @click="toggleStatus(row)"
          >
            <Ban v-if="row.status === 'active'" class="w-3.5 h-3.5" />
            <CheckCircle2 v-else class="w-3.5 h-3.5" />
          </button>
        </div>
      </template>

      <template #cell-role_name-mobile="{ row }">
        {{ roleLabels[row.role_name] || row.role_name }}
      </template>
    </AppTable>
  </div>
</template>
