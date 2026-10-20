<!--
  AppCommandPalette — ⌘K 命令面板
  模糊搜索页面跳转 + 动作（新建对话 / 新建工单 / 切换主题 / 退出）
  触发：window 'sf-open-palette' 事件 或 ⌘K / Ctrl+K
-->
<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import {
  Search, MessageSquare, Ticket, ArrowRightLeft, LayoutDashboard,
  FileText, Users, BookOpen, ScrollText, FlaskConical, Target,
  Sun, Moon, LogOut, CornerDownLeft,
} from 'lucide-vue-next'
import { useAuth, ensureUserLoaded } from '../../composables/useAuth'
import { useTheme } from '../../composables/useTheme'
import AppAvatar from '../ui/AppAvatar.vue'

const router = useRouter()
const { userInfo, logout } = useAuth()
const { isLight, toggle } = useTheme()

const open = ref(false)
const query = ref('')
const inputRef = ref(null)
const selectedIndex = ref(0)

const isAdmin = computed(() => userInfo.value?.role_name === 'admin')

const commands = computed(() => {
  const list = [
    { id: 'chat', label: '对话', group: '页面', icon: MessageSquare, keywords: 'chat duihua 对话', run: () => router.push('/chat') },
    { id: 'tickets', label: '工单', group: '页面', icon: Ticket, keywords: 'tickets gongdan 工单', run: () => router.push('/tickets') },
    { id: 'transfer', label: '转接', group: '页面', icon: ArrowRightLeft, keywords: 'transfer zhuanjie 转接', run: () => router.push('/transfer') },
  ]
  if (isAdmin.value) {
    list.push(
      { id: 'admin', label: '管理后台', group: '页面', icon: LayoutDashboard, keywords: 'admin dashboard 管理', run: () => router.push('/admin') },
      { id: 'admin-users', label: '用户管理', group: '管理', icon: Users, keywords: 'users 用户', run: () => router.push('/admin/users') },
      { id: 'admin-kb', label: '知识库', group: '管理', icon: BookOpen, keywords: 'kb documents 知识库', run: () => router.push('/admin/kb') },
      { id: 'admin-audit', label: '审计日志', group: '管理', icon: ScrollText, keywords: 'audit 日志', run: () => router.push('/admin/audit') },
      { id: 'admin-ab', label: 'A/B 测试', group: '管理', icon: FlaskConical, keywords: 'abtest 实验', run: () => router.push('/admin/abtest') },
      { id: 'admin-eval', label: 'RAG 评测', group: '管理', icon: Target, keywords: 'eval rag 评测 金标', run: () => router.push('/admin/eval') },
    )
  }
  list.push(
    { id: 'new-ticket', label: '新建工单', group: '动作', icon: FileText, keywords: 'new ticket 新建工单', run: () => router.push('/tickets?create=1') },
    { id: 'theme', label: isLight.value ? '切换暗色主题' : '切换亮色主题', group: '动作', icon: isLight.value ? Moon : Sun, keywords: 'theme dark light 主题', run: () => toggle() },
    { id: 'logout', label: '退出登录', group: '动作', icon: LogOut, keywords: 'logout 退出', run: () => logout() },
  )
  return list
})

// 简易模糊匹配：query 逐字符命中 label 或 keywords
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  if (!q) return commands.value
  return commands.value.filter((c) => {
    const hay = (c.label + ' ' + c.keywords).toLowerCase()
    let i = 0
    for (const ch of q) {
      i = hay.indexOf(ch, i)
      if (i === -1) return false
      i++
    }
    return true
  })
})

const grouped = computed(() => {
  const map = new Map()
  for (const c of filtered.value) {
    if (!map.has(c.group)) map.set(c.group, [])
    map.get(c.group).push(c)
  }
  return map
})

const run = (cmd) => {
  close()
  cmd.run()
}

const close = () => {
  open.value = false
  query.value = ''
  selectedIndex.value = 0
}

const onKeydown = async (e) => {
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault()
    if (open.value) close()
    else {
      open.value = true
      await nextTick()
      inputRef.value?.focus()
    }
    return
  }
  if (!open.value) return
  if (e.key === 'Escape') { close(); return }
  if (e.key === 'ArrowDown') { e.preventDefault(); selectedIndex.value = Math.min(selectedIndex.value + 1, filtered.value.length - 1) }
  if (e.key === 'ArrowUp') { e.preventDefault(); selectedIndex.value = Math.max(selectedIndex.value - 1, 0) }
  if (e.key === 'Enter' && filtered.value[selectedIndex.value]) { e.preventDefault(); run(filtered.value[selectedIndex.value]) }
}

const onOpenEvent = async () => {
  open.value = true
  await nextTick()
  inputRef.value?.focus()
}

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
  window.addEventListener('sf-open-palette', onOpenEvent)
  ensureUserLoaded()
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  window.removeEventListener('sf-open-palette', onOpenEvent)
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      leave-active-class="transition-opacity duration-120"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[120] flex items-start justify-center pt-[18vh] px-4 bg-black/55 backdrop-blur-[4px]"
        @click.self="close"
      >
        <Transition
          appear
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 scale-95 -translate-y-2"
          leave-active-class="transition-all duration-120"
          leave-to-class="opacity-0 scale-95"
        >
          <div class="w-full max-w-lg bg-surface-3 border border-line-2 rounded-card shadow-[var(--shadow-pop)] overflow-hidden">
            <!-- 搜索框 -->
            <div class="flex items-center gap-2.5 px-4 border-b border-line">
              <Search class="w-4 h-4 text-ink-3 shrink-0" />
              <input
                ref="inputRef"
                v-model="query"
                type="text"
                placeholder="搜索页面或动作…"
                class="flex-1 bg-transparent text-sm text-ink placeholder-ink-3 outline-none py-3.5"
              />
              <kbd class="text-[11px] text-ink-3 border border-line rounded px-1.5 py-0.5 font-mono">ESC</kbd>
            </div>
            <!-- 结果 -->
            <div class="max-h-[320px] overflow-y-auto p-1.5">
              <template v-if="filtered.length">
                <template v-for="[group, items] in grouped" :key="group">
                  <p class="px-2.5 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-ink-3">{{ group }}</p>
                  <button
                    v-for="cmd in items"
                    :key="cmd.id"
                    class="w-full flex items-center gap-2.5 px-2.5 py-2 rounded-[8px] text-sm transition-colors duration-75 text-left"
                    :class="filtered[selectedIndex] === cmd ? 'bg-brand-soft text-brand' : 'text-ink-2 hover:bg-surface-2 hover:text-ink'"
                    @click="run(cmd)"
                    @mouseenter="selectedIndex = filtered.indexOf(cmd)"
                  >
                    <component :is="cmd.icon" class="w-4 h-4 shrink-0" :stroke-width="1.8" />
                    <span class="flex-1 truncate">{{ cmd.label }}</span>
                    <CornerDownLeft v-if="filtered[selectedIndex] === cmd" class="w-3.5 h-3.5 opacity-60" />
                  </button>
                </template>
              </template>
              <p v-else class="py-10 text-center text-sm text-ink-3">无匹配结果</p>
            </div>
            <!-- 底部 -->
            <div class="flex items-center gap-3 px-4 py-2.5 border-t border-line bg-surface-2/50">
              <span class="flex items-center gap-1 text-[11px] text-ink-3"><kbd class="font-mono border border-line rounded px-1">↑</kbd><kbd class="font-mono border border-line rounded px-1">↓</kbd> 导航</span>
              <span class="flex items-center gap-1 text-[11px] text-ink-3"><kbd class="font-mono border border-line rounded px-1">↵</kbd> 执行</span>
              <span class="ml-auto flex items-center gap-1.5 text-[11px] text-ink-3">
                <AppAvatar :name="userInfo?.username || '?'" size="xs" />
                {{ userInfo?.username || '' }}
              </span>
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
