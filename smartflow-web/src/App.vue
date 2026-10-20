<!--
  App — 根组件
  结构：登录页无外壳；其余页面包 AppShell（图标栏）；CommandPalette 全局；Toast 宿主
  路由过渡：page-* 动画，/chat 例外（meta.noTransition）
-->
<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppShell from './components/layout/AppShell.vue'
import CommandPalette from './components/layout/CommandPalette.vue'
import AppToastHost from './components/ui/AppToastHost.vue'

const route = useRoute()
const isPublic = computed(() => route.meta.public)
const noTransition = computed(() => route.meta.noTransition)
</script>

<template>
  <AppToastHost />
  <CommandPalette v-if="!isPublic" />

  <!-- 公开页（Login/NotFound）：直接渲染 -->
  <template v-if="isPublic || noTransition">
    <RouterView v-slot="{ Component }">
      <AppShell v-if="!isPublic">
        <component :is="Component" />
      </AppShell>
      <component v-else :is="Component" />
    </RouterView>
  </template>

  <!-- 带过渡的页面 -->
  <template v-else>
    <RouterView v-slot="{ Component }">
      <AppShell>
        <Transition name="page" mode="out-in">
          <component :is="Component" />
        </Transition>
      </AppShell>
    </RouterView>
  </template>
</template>
