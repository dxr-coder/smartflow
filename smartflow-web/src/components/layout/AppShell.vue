<!--
  AppShell — 应用外壳
  桌面：左侧图标导航栏（logo / 页面图标 / 主题切换 + 头像菜单）
  移动端：底部标签栏 + 顶部极简条
  数据流：useAuth 提供用户信息与登出；useTheme 切换主题；router-link 高亮当前页
-->
<script setup>
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import {
  MessageSquare, Ticket, ArrowRightLeft, Package, LayoutDashboard,
  Sun, Moon, LogOut, Command,
} from 'lucide-vue-next'
import { useAuth, ensureUserLoaded } from '../../composables/useAuth'
import { useTheme } from '../../composables/useTheme'
import AppAvatar from '../ui/AppAvatar.vue'

const route = useRoute()
const router = useRouter()
const { userInfo, logout } = useAuth()
const { isLight, toggle } = useTheme()

const menuOpen = ref(false)
const isAdmin = computed(() => userInfo.value?.role_name === 'admin')

// 导航项：图标 + 路径；admin 项仅管理员可见
const navItems = computed(() => {
  const items = [
    { to: '/chat', icon: MessageSquare, label: '对话' },
    { to: '/tickets', icon: Ticket, label: '工单' },
    { to: '/transfer', icon: ArrowRightLeft, label: '转接' },
    { to: '/assets', icon: Package, label: '资产' },
  ]
  if (isAdmin.value) items.push({ to: '/admin', icon: LayoutDashboard, label: '管理' })
  return items
})

const isActive = (to) => route.path === to || route.path.startsWith(to + '/')

// 进入布局时补拉用户信息（判断 admin 项）
ensureUserLoaded()

const goLogin = () => router.push('/login')
const openPalette = () => window.dispatchEvent(new CustomEvent('sf-open-palette'))
</script>

<template>
  <div class="relative min-h-dvh bg-body">
    <!-- 全局活体背景：极光色斑（浓度更高）+ 常驻漂浮微粒 -->
    <div class="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden="true">
      <div
        class="absolute w-[46vw] h-[46vw] min-w-[420px] min-h-[420px] rounded-full opacity-[0.16] blur-[120px] animate-aurora"
        style="background: radial-gradient(circle, var(--brand) 0%, transparent 68%); top: -12%; right: -8%"
      />
      <div
        class="absolute w-[38vw] h-[38vw] min-w-[360px] min-h-[360px] rounded-full opacity-[0.12] blur-[110px] animate-aurora"
        style="background: radial-gradient(circle, var(--ai) 0%, transparent 68%); bottom: -10%; left: -6%; animation-delay: -9s"
      />
      <!-- 漂浮微粒 -->
      <span
        v-for="n in 9"
        :key="n"
        class="absolute w-[3px] h-[3px] rounded-full animate-float"
        :style="{
          left: (n * 11 + 7) % 96 + '%',
          top: (n * 17 + 13) % 90 + '%',
          background: n % 3 === 0 ? 'var(--ai)' : 'var(--brand)',
          opacity: 0.18 + (n % 4) * 0.06,
          animationDelay: (-n * 2.3) + 's',
          animationDuration: (7 + (n % 5) * 2) + 's',
        }"
      />
    </div>
    <!-- ===== 桌面左侧图标栏 ===== -->
    <aside
      class="hidden md:flex fixed left-0 top-0 bottom-0 z-40 w-16 flex-col items-center py-4 bg-surface border-r border-line"
    >
      <!-- Logo -->
      <router-link to="/chat" class="relative group mb-6" aria-label="SmartFlow">
        <div class="w-10 h-10 rounded-[12px] bg-gradient-to-br from-brand/20 to-brand-soft border border-brand/25 flex items-center justify-center transition-all duration-200 group-hover:shadow-[0_0_20px_-4px_var(--brand-glow)] group-hover:scale-105">
          <svg viewBox="0 0 24 24" class="w-5.5 h-5.5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M4 14c2-4 5-6 8-6s6 2 8 6" class="text-brand" />
            <circle cx="18" cy="7" r="2" fill="var(--ai)" stroke="none" />
          </svg>
        </div>
      </router-link>

      <!-- 导航 -->
      <nav class="flex flex-col items-center gap-1.5 flex-1">
        <router-link
          v-for="item in navItems"
          :key="item.to"
          :to="item.to"
          class="group relative w-10 h-10 rounded-[10px] flex items-center justify-center transition-all duration-150"
          :class="isActive(item.to) ? 'text-brand bg-brand-soft' : 'text-ink-3 hover:text-ink hover:bg-surface-2'"
        >
          <!-- 激活指示条 -->
          <span
            v-if="isActive(item.to)"
            class="absolute -left-4 top-1/2 -translate-y-1/2 w-[3px] h-5 rounded-r-full bg-brand shadow-[0_0_8px_var(--brand-glow)]"
          />
          <component :is="item.icon" class="w-[18px] h-[18px]" :stroke-width="1.8" />
          <!-- Tooltip -->
          <span
            class="pointer-events-none absolute left-full ml-3 px-2.5 py-1 rounded-md bg-surface-3 border border-line text-[12px] text-ink whitespace-nowrap opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-150 shadow-[var(--shadow-pop)] z-50"
          >{{ item.label }}</span>
        </router-link>

        <!-- ⌘K 命令面板入口 -->
        <button
          class="group relative w-10 h-10 rounded-[10px] flex items-center justify-center text-ink-3 hover:text-ink hover:bg-surface-2 transition-all duration-150 mt-1"
          aria-label="命令面板"
          @click="openPalette"
        >
          <Command class="w-[17px] h-[17px]" :stroke-width="1.8" />
          <span
            class="pointer-events-none absolute left-full ml-3 px-2.5 py-1 rounded-md bg-surface-3 border border-line text-[12px] text-ink whitespace-nowrap opacity-0 -translate-x-1 group-hover:opacity-100 group-hover:translate-x-0 transition-all duration-150 shadow-[var(--shadow-pop)] z-50"
          >命令面板 ⌘K</span>
        </button>
      </nav>

      <!-- 底部：主题 + 头像 -->
      <div class="flex flex-col items-center gap-2 mt-4">
        <button
          class="w-10 h-10 rounded-[10px] flex items-center justify-center text-ink-3 hover:text-ink hover:bg-surface-2 transition-all duration-150 group relative"
          :aria-label="isLight ? '切换暗色' : '切换亮色'"
          @click="toggle"
        >
          <Sun
            class="w-[18px] h-[18px] absolute transition-all duration-300"
            :class="isLight ? 'rotate-0 scale-100 opacity-100' : 'rotate-90 scale-50 opacity-0'"
            :stroke-width="1.8"
          />
          <Moon
            class="w-[18px] h-[18px] absolute transition-all duration-300"
            :class="!isLight ? 'rotate-0 scale-100 opacity-100' : '-rotate-90 scale-50 opacity-0'"
            :stroke-width="1.8"
          />
        </button>

        <!-- 头像下拉 -->
        <div class="relative">
          <button class="rounded-full ring-2 ring-transparent hover:ring-line-2 transition-all duration-150" @click="menuOpen = !menuOpen">
            <AppAvatar :name="userInfo?.username || '?'" size="sm" />
          </button>
          <Transition
            enter-active-class="transition-all duration-150"
            enter-from-class="opacity-0 scale-95 translate-y-1"
            leave-active-class="transition-all duration-100"
            leave-to-class="opacity-0 scale-95"
          >
            <div
              v-if="menuOpen"
              class="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-48 bg-surface-3 border border-line rounded-card shadow-[var(--shadow-pop)] p-1.5 z-50"
            >
              <div class="px-3 py-2 border-b border-line mb-1">
                <p class="text-[13px] font-medium text-ink truncate">{{ userInfo?.username || '未登录' }}</p>
                <p class="text-[11px] text-ink-3 mt-0.5">{{ userInfo?.role_name || 'user' }}</p>
              </div>
              <button
                class="w-full flex items-center gap-2 px-3 py-2 rounded-[8px] text-[13px] text-ink-2 hover:text-ink hover:bg-surface-2 transition-colors"
                @click="logout"
              >
                <LogOut class="w-3.5 h-3.5" />
                退出登录
              </button>
            </div>
          </Transition>
          <!-- 关闭遮罩 -->
          <div v-if="menuOpen" class="fixed inset-0 -z-10" @click="menuOpen = false" />
        </div>
      </div>
    </aside>

    <!-- ===== 主内容 ===== -->
    <main class="relative z-10 md:pl-16 pb-16 md:pb-0 min-h-dvh">
      <slot />
    </main>

    <!-- ===== 移动端底部标签栏 ===== -->
    <nav
      class="md:hidden fixed bottom-0 left-0 right-0 z-40 flex items-stretch bg-glass backdrop-blur-xl border-t border-line"
      style="padding-bottom: env(safe-area-inset-bottom)"
    >
      <router-link
        v-for="item in navItems"
        :key="item.to"
        :to="item.to"
        class="relative flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 transition-colors duration-150"
        :class="isActive(item.to) ? 'text-brand' : 'text-ink-3'"
      >
        <component :is="item.icon" class="w-5 h-5" :stroke-width="1.8" />
        <span class="text-[11px] font-medium">{{ item.label }}</span>
        <span v-if="isActive(item.to)" class="absolute bottom-1 w-1 h-1 rounded-full bg-brand" />
      </router-link>
      <button
        class="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5 text-ink-3"
        @click="toggle"
      >
        <Sun v-if="isLight" class="w-5 h-5" :stroke-width="1.8" />
        <Moon v-else class="w-5 h-5" :stroke-width="1.8" />
        <span class="text-[11px] font-medium">{{ isLight ? '亮色' : '暗色' }}</span>
      </button>
      <button class="flex-1 flex flex-col items-center justify-center gap-0.5 py-2.5" :class="menuOpen ? 'text-brand' : 'text-ink-3'" @click="menuOpen = !menuOpen">
        <AppAvatar :name="userInfo?.username || '?'" size="xs" />
        <span class="text-[11px] font-medium">我的</span>
      </button>
      <!-- 移动端头像弹层 -->
      <Transition
        enter-active-class="transition-all duration-200"
        enter-from-class="opacity-0 translate-y-2"
        leave-active-class="transition-all duration-150"
        leave-to-class="opacity-0 translate-y-2"
      >
        <div
          v-if="menuOpen"
          class="md:hidden fixed bottom-20 left-4 right-4 bg-surface-3 border border-line rounded-card shadow-[var(--shadow-pop)] p-2 z-50 animate-rise"
        >
          <div class="px-3 py-2.5 border-b border-line mb-1 flex items-center gap-2.5">
            <AppAvatar :name="userInfo?.username || '?'" size="md" />
            <div>
              <p class="text-sm font-medium text-ink">{{ userInfo?.username || '未登录' }}</p>
              <p class="text-[11px] text-ink-3">{{ userInfo?.role_name || 'user' }}</p>
            </div>
          </div>
          <button
            class="w-full flex items-center gap-2.5 px-3 py-2.5 rounded-[8px] text-sm text-ink-2 hover:text-ink hover:bg-surface-2 transition-colors"
            @click="logout"
          >
            <LogOut class="w-4 h-4" />
            退出登录
          </button>
        </div>
      </Transition>
      <div v-if="menuOpen" class="md:hidden fixed inset-0 -z-10" @click="menuOpen = false" />
    </nav>
  </div>
</template>
