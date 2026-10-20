<!--
  Login — 分屏签名页
  左（lg+）：固定品牌墙（深空靛蓝 + 极光 + 单句标语），双主题下恒定深色
  右：登录/注册玻璃卡片；移动端折叠为顶部紧凑 Logo
  数据流：POST /auth/login|register → access_token → localStorage → 跳 /chat
-->
<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { Eye, EyeOff, ArrowRight } from 'lucide-vue-next'
import api from '../api'
import { useAuth } from '../composables/useAuth'
import { toast } from '../composables/useToast'
import AppInput from '../components/ui/AppInput.vue'
import AppButton from '../components/ui/AppButton.vue'

const router = useRouter()
const { setToken } = useAuth()

const mode = ref('login')
const username = ref('')
const password = ref('')
const showPwd = ref(false)
const loading = ref(false)

// 品牌墙鼠标视差
const px = ref(0)
const py = ref(0)
const onParallax = (e) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const r = e.currentTarget.getBoundingClientRect()
  px.value = (e.clientX - r.left) / r.width - 0.5
  py.value = (e.clientY - r.top) / r.height - 0.5
}
const onParallaxEnd = () => { px.value = 0; py.value = 0 }

// 登录卡片 3D 倾斜（与 NotFound / AiCore 同一套 tilt 变量）
const rx = ref(0)
const ry = ref(0)
const gx = ref(50)
const gy = ref(50)
const tilting = ref(false)
const onCardMove = (e) => {
  if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return
  const r = e.currentTarget.getBoundingClientRect()
  const nx = (e.clientX - r.left) / r.width - 0.5
  const ny = (e.clientY - r.top) / r.height - 0.5
  ry.value = nx * 6
  rx.value = -ny * 6
  gx.value = (nx + 0.5) * 100
  gy.value = (ny + 0.5) * 100
  tilting.value = true
}
const onCardLeave = () => {
  rx.value = 0; ry.value = 0
  tilting.value = false
}

const submit = async () => {
  if (!username.value.trim() || !password.value) {
    toast.error('请填写用户名和密码')
    return
  }
  loading.value = true
  try {
    const res = await api.post(`/auth/${mode.value}`, null, {
      params: { username: username.value.trim(), password: password.value },
    })
    setToken(res.data.access_token)
    // refresh_token 用于无感续期；后端 register 不发，只在有值时存（undefined 会覆盖成字符串"undefined"）
    if (res.data.refresh_token) localStorage.setItem('refresh_token', res.data.refresh_token)
    if (mode.value === 'register') toast.success('注册成功，已自动登录')
    router.push('/chat')
  } catch (e) {
    toast.error(e.response?.data?.detail || (mode.value === 'login' ? '登录失败，请检查用户名密码' : '注册失败，用户名可能已存在'))
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-dvh grid lg:grid-cols-[1.15fr_1fr] bg-body">
    <!-- ===== 左：品牌墙（恒定深空靛蓝 + 鼠标视差） ===== -->
    <section
      class="relative hidden lg:flex flex-col justify-between overflow-hidden p-12 xl:p-16"
      @mousemove="onParallax"
      @mouseleave="onParallaxEnd"
    >
      <!-- 背景层 -->
      <div class="absolute inset-0 bg-[#09090f]"></div>
      <!-- 网格 -->
      <div
        class="absolute inset-[-40px] opacity-[0.45] transition-transform duration-300 ease-out"
        style="background-image: linear-gradient(rgba(255,255,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.03) 1px, transparent 1px); background-size: 48px 48px"
        :style="{ transform: `translate(${px * -14}px, ${py * -14}px)` }"
      ></div>
      <!-- 极光：靛蓝 -->
      <div
        class="absolute w-[600px] h-[600px] rounded-full opacity-[0.28] blur-[120px] animate-aurora transition-transform duration-500 ease-out"
        style="background: radial-gradient(circle, #6366f1 0%, transparent 65%); top: -14%; right: -16%"
        :style="{ transform: `translate(${px * 30}px, ${py * 30}px)` }"
      ></div>
      <!-- 极光：紫罗兰 -->
      <div
        class="absolute w-[500px] h-[500px] rounded-full opacity-[0.18] blur-[110px] animate-aurora transition-transform duration-500 ease-out"
        style="background: radial-gradient(circle, #22d3ee 0%, transparent 65%); bottom: -16%; left: -10%; animation-delay: -9s"
        :style="{ transform: `translate(${px * 46}px, ${py * 46}px)` }"
      ></div>
      <!-- 漂浮微粒 -->
      <span
        v-for="n in 6"
        :key="'p' + n"
        class="absolute w-[3px] h-[3px] rounded-full animate-float pointer-events-none"
        :style="{
          left: (n * 17 + 10) % 86 + '%',
          top: (n * 21 + 9) % 80 + '%',
          background: n % 2 ? '#818cf8' : '#22d3ee',
          opacity: 0.12 + (n % 3) * 0.06,
          animationDelay: (-n * 2.1) + 's',
          animationDuration: (7 + (n % 4) * 2) + 's',
        }"
        aria-hidden="true"
      />

      <!-- Logo -->
      <div class="relative animate-fade-up">
        <div class="flex items-center gap-3">
          <div class="w-10 h-10 rounded-[12px] bg-gradient-to-br from-[#818cf8]/25 to-[#818cf8]/5 border border-[#818cf8]/30 flex items-center justify-center shadow-[0_0_24px_-6px_rgba(129,140,248,0.5)]">
            <svg viewBox="0 0 24 24" class="w-5 h-5" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
              <path d="M4 14c2-4 5-6 8-6s6 2 8 6" class="text-[#818cf8]" />
              <circle cx="18" cy="7" r="2" fill="#22d3ee" stroke="none" />
            </svg>
          </div>
          <span class="text-[15px] font-semibold text-white tracking-tight">SmartFlow</span>
        </div>
      </div>

      <!-- 单句标语（视差深层） -->
      <div class="relative max-w-lg transition-transform duration-500 ease-out" :style="{ transform: `translate(${px * 16}px, ${py * 16}px)` }">
        <h1 class="animate-fade-up text-5xl xl:text-[56px] font-semibold text-white tracking-tight leading-[1.1]" style="animation-delay: 60ms">
          让每个请求，<br />都有<span class="bg-gradient-to-r from-[#818cf8] via-[#22d3ee] to-[#818cf8] bg-clip-text text-transparent bg-[length:200%_100%] animate-gradient-x">答案</span>
        </h1>
      </div>

      <div aria-hidden="true"></div>
    </section>

    <!-- ===== 右：表单面 ===== -->
    <section class="relative flex flex-col items-center justify-center px-5 py-10 sm:px-8 overflow-hidden">
      <!-- mesh 呼吸底 -->
      <div
        class="absolute inset-0 opacity-[0.5] animate-mesh-drift pointer-events-none"
        style="background: radial-gradient(90% 60% at 100% 0%, var(--brand-soft) 0%, transparent 50%), radial-gradient(70% 50% at 0% 100%, var(--ai-soft) 0%, transparent 45%); background-size: 140% 140%"
        aria-hidden="true"
      />
      <!-- 漂浮微粒 -->
      <span
        v-for="n in 5"
        :key="'r' + n"
        class="absolute w-[3px] h-[3px] rounded-full animate-float pointer-events-none"
        :style="{
          left: (n * 19 + 8) % 88 + '%',
          top: (n * 23 + 11) % 82 + '%',
          background: n % 2 ? 'var(--brand)' : 'var(--ai)',
          opacity: 0.13 + (n % 3) * 0.06,
          animationDelay: (-n * 1.9) + 's',
          animationDuration: (7 + (n % 4) * 2) + 's',
        }"
        aria-hidden="true"
      />

      <!-- 移动端紧凑品牌头 -->
      <div class="lg:hidden flex flex-col items-center mb-7 animate-fade-up">
        <div class="rounded-2xl bg-gradient-to-br from-brand/20 to-brand-soft border border-brand/25 flex items-center justify-center shadow-[0_0_40px_-8px_var(--brand-glow)] mb-4" style="width:52px;height:52px">
          <svg viewBox="0 0 24 24" style="width:26px;height:26px" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
            <path d="M4 14c2-4 5-6 8-6s6 2 8 6" class="text-brand" />
            <circle cx="18" cy="7" r="2" fill="var(--ai)" stroke="none" />
          </svg>
        </div>
        <h1 class="text-xl font-semibold text-ink tracking-tight">SmartFlow</h1>
        <p class="text-[13px] text-ink-3 mt-1">企业智能服务台</p>
      </div>

      <div class="relative w-full max-w-sm animate-rise z-10 tilt-scene">
        <div
          class="tilt-3d relative bg-glass backdrop-blur-xl border border-line rounded-lg shadow-[var(--shadow-pop)] p-6 transition-shadow duration-300 focus-within:shadow-[0_0_0_1px_var(--brand-soft),0_20px_56px_-20px_var(--brand-glow)]"
          :class="{ tilting }"
          :style="{ '--rx': rx + 'deg', '--ry': ry + 'deg' }"
          @mousemove="onCardMove"
          @mouseleave="onCardLeave"
        >
          <span class="tilt-gloss absolute inset-0 rounded-lg z-0 pointer-events-none" aria-hidden="true" />
          <!-- 模式切换 -->
          <div class="relative z-10 animate-fade-up flex items-center gap-1 p-1 bg-surface-2 border border-line rounded-ctl mb-5" style="animation-delay: 80ms">
            <button
              v-for="m in [['login', '登录'], ['register', '注册']]"
              :key="m[0]"
              class="flex-1 h-8 rounded-[8px] text-[13px] font-medium transition-all duration-150"
              :class="mode === m[0] ? 'bg-surface-3 text-ink shadow-[var(--shadow-card)]' : 'text-ink-3 hover:text-ink-2'"
              @click="mode = m[0]"
            >{{ m[1] }}</button>
          </div>

          <form class="relative z-10 space-y-4" @submit.prevent="submit">
            <div class="animate-fade-up" style="animation-delay: 140ms">
              <AppInput v-model="username" label="用户名" placeholder="请输入用户名" autocomplete="username" />
            </div>
            <div class="animate-fade-up" style="animation-delay: 200ms">
              <AppInput
                v-model="password"
                label="密码"
                :type="showPwd ? 'text' : 'password'"
                placeholder="请输入密码"
                autocomplete="current-password"
                @keyup.enter="submit"
              >
                <template #suffix>
                  <button type="button" class="p-0.5 hover:text-ink transition-colors" @click="showPwd = !showPwd">
                    <EyeOff v-if="showPwd" class="w-4 h-4" />
                    <Eye v-else class="w-4 h-4" />
                  </button>
                </template>
              </AppInput>
            </div>

            <div class="animate-fade-up" style="animation-delay: 260ms">
              <AppButton type="submit" block size="lg" :loading="loading">
                {{ mode === 'login' ? '登录' : '注册并登录' }}
                <ArrowRight class="w-4 h-4" />
              </AppButton>
            </div>
          </form>
        </div>

        <p class="animate-fade-up text-center text-[11px] text-ink-3 mt-6" style="animation-delay: 320ms">登录即代表你同意企业服务规范</p>
      </div>
    </section>
  </div>
</template>
