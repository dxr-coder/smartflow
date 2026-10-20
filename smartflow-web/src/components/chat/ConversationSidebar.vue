<!--
  ConversationSidebar — 会话侧栏
  数据流：GET /conversations 拉列表；点击会话 emit select；新建 emit new
  编辑标签：PUT /conversations/:id/tags?tags=
  视觉：mesh 呼吸底 + 磁吸新建钮 + 激活项渐变左条发光 + 错峰入场
-->
<script setup>
import { ref } from 'vue'
import { Plus, MessageSquare, Tag, Sparkles } from 'lucide-vue-next'
import api from '../../api'
import { toast } from '../../composables/useToast'
import AppDrawer from '../ui/AppDrawer.vue'
import AppInput from '../ui/AppInput.vue'
import AppButton from '../ui/AppButton.vue'

defineProps({
  conversations: { type: Array, default: () => [] },
  activeId: { type: [Number, String], default: null },
  mobileOpen: Boolean,
})
const emit = defineEmits(['select', 'new', 'update:mobileOpen', 'tags-saved'])

const editingId = ref(null)
const tagText = ref('')

const startEdit = (conv) => {
  editingId.value = conv.id
  tagText.value = (conv.tags || []).join(', ')
}
const saveTags = async () => {
  try {
    const tags = tagText.value.split(/[,，\s]+/).map((t) => t.trim()).filter(Boolean)
    await api.put(`/conversations/${editingId.value}/tags`, null, { params: { tags: tags.join(',') } })
    editingId.value = null
    toast.success('标签已更新')
    emit('tags-saved')
  } catch (e) {
    toast.error('标签保存失败')
  }
}

const fmtTime = (iso) => {
  if (!iso) return ''
  const d = new Date(iso)
  const now = new Date()
  if (d.toDateString() === now.toDateString()) {
    return `${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
  }
  return `${d.getMonth() + 1}/${d.getDate()}`
}
</script>

<template>
  <!-- 桌面：常驻侧栏 -->
  <aside class="hidden lg:flex w-72 shrink-0 flex-col bg-surface border-r border-line h-full relative overflow-hidden">
    <!-- mesh 呼吸底 -->
    <div
      class="absolute inset-0 opacity-[0.45] animate-mesh-drift pointer-events-none"
      style="background: radial-gradient(120% 60% at 0% 0%, var(--brand-soft) 0%, transparent 50%), radial-gradient(90% 50% at 100% 100%, var(--ai-soft) 0%, transparent 45%); background-size: 140% 140%"
      aria-hidden="true"
    />

    <div class="relative flex items-center justify-between px-4 pt-4 pb-3">
      <h2 class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">
        <Sparkles class="w-3 h-3 text-ai" :stroke-width="2" />
        会话
      </h2>
      <button
        class="w-7 h-7 rounded-ctl flex items-center justify-center text-ink-3 hover:text-brand hover:bg-brand-soft hover:shadow-[0_0_16px_-4px_var(--brand-glow)] transition-all active:scale-95"
        aria-label="新建对话"
        @click="emit('new')"
      >
        <Plus class="w-4 h-4" />
      </button>
    </div>

    <div class="relative flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
      <p v-if="!conversations.length" class="text-center py-10 text-ink-3 text-[13px]">暂无会话</p>
      <button
        v-for="(c, i) in conversations"
        :key="c.id"
        class="group w-full text-left px-3 py-2.5 rounded-ctl transition-all duration-150 relative animate-rise"
        :class="activeId === c.id ? 'bg-brand-soft/80 shadow-[inset_0_0_0_1px_var(--brand-glow)]' : 'hover:bg-surface-2/80'"
        :style="{ animationDelay: `${i * 35}ms`, animationDuration: '360ms' }"
        @click="emit('select', c.id)"
      >
        <!-- 激活渐变左条 + 发光 -->
        <span
          v-if="activeId === c.id"
          class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-gradient-to-b from-brand to-ai shadow-[0_0_10px_var(--brand-glow)]"
        />
        <div class="flex items-start gap-2">
          <MessageSquare class="w-3.5 h-3.5 mt-0.5 shrink-0 transition-colors" :class="activeId === c.id ? 'text-brand' : 'text-ink-3 group-hover:text-ink-2'" />
          <div class="flex-1 min-w-0">
            <p class="text-[13px] truncate transition-colors" :class="activeId === c.id ? 'text-ink font-medium' : 'text-ink-2 group-hover:text-ink'">
              {{ c.title || '未命名对话' }}
            </p>
            <div class="flex items-center gap-1.5 mt-1 flex-wrap">
              <span class="text-[11px] text-ink-3 tabular-nums">{{ fmtTime(c.updated_at || c.created_at) }}</span>
              <span
                v-for="t in (c.tags || []).slice(0, 2)"
                :key="t"
                class="text-[11px] px-1 py-px rounded bg-surface-3 text-ink-3 border border-line"
              >{{ t }}</span>
            </div>
          </div>
          <button
            class="opacity-0 group-hover:opacity-100 focus:opacity-100 p-1 rounded text-ink-3 hover:text-ink transition-all shrink-0"
            aria-label="编辑标签"
            @click.stop="startEdit(c)"
          >
            <Tag class="w-3 h-3" />
          </button>
        </div>
      </button>
    </div>
  </aside>

  <!-- 移动端：抽屉 -->
  <AppDrawer :model-value="mobileOpen" side="left" @update:model-value="emit('update:mobileOpen', $event)">
    <div class="flex flex-col h-full">
      <div class="flex items-center justify-between px-4 pt-4 pb-3">
        <h2 class="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-ink-3">
          <Sparkles class="w-3 h-3 text-ai" :stroke-width="2" />
          会话
        </h2>
        <button
          class="w-7 h-7 rounded-ctl flex items-center justify-center text-ink-3 hover:text-brand hover:bg-brand-soft transition-all active:scale-95"
          @click="emit('new')"
        >
          <Plus class="w-4 h-4" />
        </button>
      </div>
      <div class="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        <p v-if="!conversations.length" class="text-center py-10 text-ink-3 text-[13px]">暂无会话</p>
        <button
          v-for="c in conversations"
          :key="c.id"
          class="w-full text-left px-3 py-2.5 rounded-ctl transition-all duration-150"
          :class="activeId === c.id ? 'bg-brand-soft text-ink' : 'text-ink-2 hover:bg-surface-2'"
          @click="emit('select', c.id)"
        >
          <div class="flex items-start gap-2">
            <MessageSquare class="w-3.5 h-3.5 mt-0.5 shrink-0" :class="activeId === c.id ? 'text-brand' : 'text-ink-3'" />
            <div class="flex-1 min-w-0">
              <p class="text-[13px] truncate" :class="activeId === c.id ? 'font-medium' : ''">
                {{ c.title || '未命名对话' }}
              </p>
              <span class="text-[11px] text-ink-3 tabular-nums">{{ fmtTime(c.updated_at || c.created_at) }}</span>
            </div>
          </div>
        </button>
      </div>
    </div>
  </AppDrawer>

  <!-- 标签编辑弹窗 -->
  <AppDrawer :model-value="editingId !== null" side="right" @update:model-value="(v) => { if (!v) editingId = null }">
    <div class="p-4 space-y-4" v-if="editingId !== null">
      <h3 class="text-sm font-semibold text-ink">编辑标签</h3>
      <AppInput v-model="tagText" label="标签" placeholder="用逗号分隔，如：IT,紧急" @keyup.enter="saveTags" />
      <div class="flex gap-2 justify-end">
        <AppButton variant="secondary" size="sm" @click="editingId = null">取消</AppButton>
        <AppButton size="sm" @click="saveTags">保存</AppButton>
      </div>
    </div>
  </AppDrawer>
</template>
