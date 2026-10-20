<!--
  AdminLayout — 管理后台外壳
  桌面：左侧二级导航（mesh 呼吸底 + 图标+文字，激活品牌底 + 发光左色条）；移动端：AppTabs 横滚
  嵌套 router-view 短淡入过渡
-->
<script setup>
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { LayoutDashboard, Users, BookOpen, ScrollText, FlaskConical, Shield, Target } from 'lucide-vue-next'
import AppTabs from '../ui/AppTabs.vue'

const route = useRoute()
const router = useRouter()

const navItems = [
  { to: '/admin', exact: true, icon: LayoutDashboard, label: '概览' },
  { to: '/admin/users', icon: Users, label: '用户' },
  { to: '/admin/kb', icon: BookOpen, label: '知识库' },
  { to: '/admin/audit', icon: ScrollText, label: '审计日志' },
  { to: '/admin/abtest', icon: FlaskConical, label: 'A/B 测试' },
  { to: '/admin/eval', icon: Target, label: 'RAG 评测' },
]

const isActive = (item) =>
  item.exact ? route.path === item.to : route.path.startsWith(item.to)

const tabItems = navItems.map((i) => ({ value: i.to, label: i.label, icon: i.icon }))
const activeTab = computed({
  get: () => route.path,
  set: (v) => router.push(v),
})
</script>

<template>
  <div class="flex min-h-dvh">
    <!-- 桌面侧栏 -->
    <aside class="hidden md:flex w-52 shrink-0 flex-col border-r border-line bg-surface py-5 relative overflow-hidden">
      <!-- mesh 呼吸底 -->
      <div
        class="absolute inset-0 opacity-[0.4] animate-mesh-drift pointer-events-none"
        style="background: radial-gradient(120% 80% at 0% 0%, var(--brand-soft) 0%, transparent 50%), radial-gradient(100% 70% at 100% 100%, var(--ai-soft) 0%, transparent 45%); background-size: 150% 150%"
        aria-hidden="true"
      />

      <p class="relative px-5 mb-4 flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-ink-3">
        <Shield class="w-3.5 h-3.5" :stroke-width="2" />
        管理后台
      </p>
      <nav class="relative flex-1 space-y-0.5 px-2.5">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="relative flex items-center gap-2.5 px-3 h-9 rounded-ctl text-[13px] font-medium transition-all duration-150"
          :class="isActive(item) ? 'bg-brand-soft text-brand shadow-[inset_0_0_20px_-8px_var(--brand-glow)]' : 'text-ink-2 hover:text-ink hover:bg-surface-2'"
        >
          <span
            v-if="isActive(item)"
            class="absolute left-0 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-brand shadow-[0_0_10px_var(--brand-glow)]"
          />
          <component :is="item.icon" class="w-4 h-4" :stroke-width="1.8" />
          {{ item.label }}
        </router-link>
      </nav>
    </aside>

    <div class="flex-1 min-w-0">
      <!-- 移动端标签条 -->
      <div class="md:hidden sticky top-0 z-30 px-4 py-3 bg-glass backdrop-blur-xl border-b border-line">
        <AppTabs v-model="activeTab" :items="tabItems" />
      </div>

      <main class="p-4 sm:p-6 lg:p-8">
        <div class="mx-auto w-full max-w-5xl">
          <router-view v-slot="{ Component }">
            <Transition appear enter-active-class="transition-opacity duration-200" enter-from-class="opacity-0">
              <component :is="Component" />
            </Transition>
          </router-view>
        </div>
      </main>
    </div>
  </div>
</template>
