/**
 * shots.mjs — 视觉审计截图（Playwright）
 * 数据流：登录 mock 后端 → 逐视图导航 → 375/1440 × light/dark 截图到 shots/
 * 用法：node scripts/shots.mjs [nameFilter]
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const BASE = 'http://localhost:5199'
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'shots')
mkdirSync(OUT, { recursive: true })

const authedViews = [
  { name: 'chat-empty', path: '/chat' },
  { name: 'chat-conv', path: '/chat', action: 'open-conv' },
  { name: 'tickets', path: '/tickets' },
  { name: 'ticket-detail', path: '/tickets/12' },
  { name: 'transfer', path: '/transfer' },
  { name: 'dashboard', path: '/admin' },
  { name: 'users', path: '/admin/users' },
  { name: 'kb', path: '/admin/kb' },
  { name: 'audit', path: '/admin/audit' },
  { name: 'abtest', path: '/admin/abtest' },
]
const anonViews = [
  { name: 'login', path: '/login' },
  { name: 'notfound', path: '/no-such-page' },
]

const filter = process.argv[2] || ''
const widths = [375, 1440]
const themes = ['light', 'dark']

const browser = await chromium.launch()

async function shoot(p, view, theme, w) {
  await p.goto(BASE + view.path, { waitUntil: 'networkidle' }).catch(() => {})
  await p.waitForTimeout(600)
  if (view.action === 'open-conv') {
    if (w < 1024) {
      await p.click('button[aria-label="打开会话列表"]').catch(() => {})
      await p.waitForTimeout(350)
    }
    await p.getByText('VPN 连不上公司内网', { exact: true }).locator('visible=true').first().click().catch(() => {})
    await p.waitForTimeout(900)
  }
  if (view.name.startsWith('chat')) await p.waitForTimeout(700)
  const file = join(OUT, `${view.name}--${theme}--${w}.png`)
  await p.screenshot({ path: file })
  console.log('shot', file)
}

for (const theme of themes) {
  for (const w of widths) {
    const vp = { width: w, height: w < 500 ? 812 : 900 }

    // 未登录（无 token）
    const anonCtx = await browser.newContext({ viewport: vp })
    await anonCtx.addInitScript((t) => localStorage.setItem('sf-theme', t), theme)
    for (const v of anonViews) {
      if (filter && !v.name.includes(filter)) continue
      const p = await anonCtx.newPage()
      await shoot(p, v, theme, w)
      await p.close()
    }
    await anonCtx.close()

    // 已登录
    const ctx = await browser.newContext({ viewport: vp })
    await ctx.addInitScript((t) => {
      localStorage.setItem('sf-theme', t)
      localStorage.setItem('token', 'mock-token')
    }, theme)
    for (const v of authedViews) {
      if (filter && !v.name.includes(filter)) continue
      const p = await ctx.newPage()
      await shoot(p, v, theme, w)
      await p.close()
    }
    await ctx.close()
  }
}
await browser.close()
console.log('done')
