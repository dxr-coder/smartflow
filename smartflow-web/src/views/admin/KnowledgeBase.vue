<!--
  KnowledgeBase — 知识库管理
  数据流：GET /documents 列表；POST /documents multipart {file, department} 上传；
         GET /documents/:id/chunks 切片；GET /documents/:id/versions 版本；
         DELETE /documents/:id（AppModal 确认，替代原生 confirm）
-->
<script setup>
import { ref, onMounted } from 'vue'
import { FileText, Trash2, ChevronRight } from 'lucide-vue-next'
import api from '../../api'
import { toast } from '../../composables/useToast'
import { deptTones, docStatusTones } from '../../utils/badges'
import AppTable from '../../components/ui/AppTable.vue'
import AppBadge from '../../components/ui/AppBadge.vue'
import AppButton from '../../components/ui/AppButton.vue'
import AppSelect from '../../components/ui/AppSelect.vue'
import AppDropzone from '../../components/ui/AppDropzone.vue'
import AppModal from '../../components/ui/AppModal.vue'
import AppCard from '../../components/ui/AppCard.vue'
import AppSkeleton from '../../components/ui/AppSkeleton.vue'
import PageHero from '../../components/layout/PageHero.vue'

const documents = ref([])
const loading = ref(true)
const uploading = ref(false)
const department = ref('all')

const deptOptions = [
  { value: 'all', label: '全公司' },
  { value: 'hr', label: '人力资源' },
  { value: 'it', label: 'IT 技术' },
  { value: 'finance', label: '财务' },
  { value: 'admin', label: '行政' },
]
const deptLabels = Object.fromEntries(deptOptions.map((o) => [o.value, o.label]))

const columns = [
  { key: 'filename', label: '文件', primary: true },
  { key: 'department', label: '部门' },
  { key: 'status', label: '状态' },
  { key: 'created_at', label: '上传时间' },
]

// 展开行：切片 + 版本
const expandedId = ref(null)
const expandData = ref({ chunks: [], versions: [], loading: false })

// 删除确认
const deleteTarget = ref(null)
const deleting = ref(false)

const load = async () => {
  loading.value = true
  try {
    const res = await api.get('/documents')
    documents.value = res.data.items || res.data
  } catch (e) {
    toast.error('文档加载失败')
  } finally {
    loading.value = false
  }
}

const upload = async (file) => {
  uploading.value = true
  const fd = new FormData()
  fd.append('file', file)
  fd.append('department', department.value)
  try {
    await api.post('/documents', fd)
    toast.success(`「${file.name}」上传成功，正在解析`)
    load()
  } catch (e) {
    toast.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

const toggleExpand = async (id) => {
  if (expandedId.value === id) { expandedId.value = null; return }
  expandedId.value = id
  expandData.value = { chunks: [], versions: [], loading: true }
  try {
    const [ch, ver] = await Promise.all([
      api.get(`/documents/${id}/chunks`),
      api.get(`/documents/${id}/versions`),
    ])
    expandData.value = {
      chunks: ch.data.items || ch.data || [],
      versions: ver.data.items || ver.data || [],
      loading: false,
    }
  } catch (e) {
    expandData.value.loading = false
    toast.error('切片加载失败')
  }
}

const confirmDelete = async () => {
  if (!deleteTarget.value) return
  deleting.value = true
  try {
    await api.delete(`/documents/${deleteTarget.value.id}`)
    toast.success('文档已删除')
    deleteTarget.value = null
    load()
  } catch (e) {
    toast.error('删除失败')
  } finally {
    deleting.value = false
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
  <div>
    <PageHero
      title="知识库"
      subtitle="上传文档，AI 即可引用作答"
      :count="documents.length ? `${documents.length} 份` : ''"
      accent="ai"
    />

    <!-- 上传区 -->
    <AppCard class="mb-6">
      <div class="flex flex-col sm:flex-row sm:items-end gap-4">
        <div class="flex-1">
          <AppDropzone @file="upload" />
        </div>
        <div class="w-full sm:w-36 shrink-0">
          <p class="text-[13px] font-medium text-ink-2 mb-1.5">归属部门</p>
          <AppSelect v-model="department" :options="deptOptions" />
        </div>
      </div>
    </AppCard>

    <!-- 文档表 -->
    <AppTable
      :columns="columns"
      :rows="documents"
      :loading="loading"
      empty-text="暂无文档，上传后 AI 即可引用作答"
      expandable
      :expanded-id="expandedId"
      @toggle-expand="toggleExpand"
    >
      <template #cell-filename="{ row }">
        <div class="flex items-center gap-2.5 min-w-0">
          <div class="w-7 h-7 rounded-[8px] bg-brand-soft border border-brand/20 flex items-center justify-center shrink-0">
            <FileText class="w-3.5 h-3.5 text-brand" />
          </div>
          <span class="font-medium text-ink truncate">{{ row.filename }}</span>
        </div>
      </template>

      <template #cell-department="{ row }">
        <AppBadge :tone="deptTones[row.department] || 'gray'" size="sm">
          {{ deptLabels[row.department] || row.department }}
        </AppBadge>
      </template>

      <template #cell-status="{ row }">
        <AppBadge :tone="docStatusTones[row.status] || 'gray'" size="sm" :dot="row.status === 'processing'">
          {{ row.status === 'active' ? '可用' : row.status === 'processing' ? '解析中' : '失败' }}
        </AppBadge>
      </template>

      <template #cell-created_at="{ row }">
        <span class="tabular-nums text-[13px]">{{ fmtTime(row.created_at) }}</span>
      </template>

      <!-- 展开：切片 + 版本 + 删除 -->
      <template #expand="{ row }">
        <AppSkeleton v-if="expandData.loading" variant="table" :rows="3" />
        <div v-else class="grid md:grid-cols-2 gap-5">
          <div>
            <p class="text-[12px] font-semibold uppercase tracking-wider text-ink-3 mb-2">切片（{{ expandData.chunks.length }}）</p>
            <div class="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              <div
                v-for="(c, i) in expandData.chunks"
                :key="i"
                class="px-3 py-2 bg-surface border border-line rounded-ctl text-[12px] text-ink-2 leading-relaxed"
              >{{ typeof c === 'string' ? c : c.content || JSON.stringify(c) }}</div>
              <p v-if="!expandData.chunks.length" class="text-[12px] text-ink-3">暂无切片</p>
            </div>
          </div>
          <div>
            <p class="text-[12px] font-semibold uppercase tracking-wider text-ink-3 mb-2">版本历史</p>
            <div class="space-y-1.5">
              <div
                v-for="(v, i) in expandData.versions"
                :key="i"
                class="flex items-center gap-2 px-3 py-2 bg-surface border border-line rounded-ctl text-[12px]"
              >
                <ChevronRight class="w-3 h-3 text-ink-3" />
                <span class="text-ink-2 flex-1 truncate">{{ typeof v === 'string' ? v : v.filename || v.version || JSON.stringify(v) }}</span>
                <span class="text-ink-3 tabular-nums shrink-0">{{ fmtTime(v.created_at) }}</span>
              </div>
              <p v-if="!expandData.versions.length" class="text-[12px] text-ink-3">暂无版本记录</p>
            </div>
          </div>
          <div class="md:col-span-2 flex justify-end pt-1 border-t border-line">
            <AppButton variant="danger" size="sm" @click="deleteTarget = row">
              <Trash2 class="w-3.5 h-3.5" />
              删除文档
            </AppButton>
          </div>
        </div>
      </template>

      <!-- 表尾操作（移动端卡片展开时也可删除） -->
      <template #header-actions>
        <div v-if="uploading" class="px-4 py-2.5 border-t border-line bg-brand-soft/50 text-[12px] text-brand flex items-center gap-2">
          <span class="w-3 h-3 border-2 border-brand/30 border-t-brand rounded-full animate-spin-dot" />
          正在上传并解析…
        </div>
      </template>
    </AppTable>

    <!-- 删除确认 -->
    <AppModal v-model="deleteTarget" title="删除文档" size="sm">
      <p class="text-sm text-ink-2 leading-relaxed">
        确认删除「<span class="text-ink font-medium">{{ deleteTarget?.filename }}</span>」？删除后 AI 将无法引用该文档作答，此操作不可撤销。
      </p>
      <template #footer>
        <AppButton variant="secondary" size="sm" @click="deleteTarget = null">取消</AppButton>
        <AppButton variant="danger" size="sm" :loading="deleting" @click="confirmDelete">确认删除</AppButton>
      </template>
    </AppModal>
  </div>
</template>
