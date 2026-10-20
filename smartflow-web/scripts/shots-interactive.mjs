/**
 * shots-interactive.mjs — 交互覆盖层截图（Playwright）
 * 覆盖：命令面板、新建工单弹窗、删除确认弹窗、移动端会话抽屉、Toast、标签编辑、流式消息
 * 数据流：登录 mock → 触发各交互态 → 截图到 shots/ix-*
 */
import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const BASE = 'http://localhost:5199'
const OUT = join(dirname(fileURLToPath(import.meta.url)), '..', 'shots')
mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch()

async function authedPage(w = 1440, h = 900, theme = 'dark') {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } })
  const p = await ctx.newPage()
  await p.goto(BASE + '/login', { waitUntil: 'networkidle' }).catch(() => {})
  await p.evaluate((t) => {
    localStorage.setItem('token', 'mock-admin-token')
    document.documentElement.classList.toggle('light', t === 'light')
  }, theme)
  return p
}

// 1. 命令面板（⌘K）
{
  const p = await authedPage()
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(500)
  await p.keyboard.press('Control+k')
  await p.waitForTimeout(350)
  await p.screenshot({ path: join(OUT, 'ix-palette--dark--1440.png') })
  // 搜索过滤态
  await p.keyboard.type('工单')
  await p.waitForTimeout(250)
  await p.screenshot({ path: join(OUT, 'ix-palette-search--dark--1440.png') })
  await p.context().close()
  console.log('shot palette')
}

// 2. 新建工单弹窗
{
  const p = await authedPage()
  await p.goto(BASE + '/tickets?create=1', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  await p.screenshot({ path: join(OUT, 'ix-ticket-modal--dark--1440.png') })
  await p.context().close()
  console.log('shot ticket-modal')
}

// 3. 删除确认弹窗（KB 展开行 → 删除）
{
  const p = await authedPage()
  await p.goto(BASE + '/admin/kb', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  await p.locator('button[aria-label="展开详情"]').first().click()
  await p.waitForTimeout(700)
  await p.getByText('删除文档', { exact: true }).first().click().catch(() => {})
  await p.waitForTimeout(400)
  await p.screenshot({ path: join(OUT, 'ix-kb-delete--dark--1440.png') })
  await p.context().close()
  console.log('shot kb-delete')
}

// 4. 移动端会话抽屉（375）
{
  const p = await authedPage(375, 812)
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(500)
  await p.click('button[aria-label="打开会话列表"]').catch(() => {})
  await p.waitForTimeout(400)
  await p.screenshot({ path: join(OUT, 'ix-chat-drawer--dark--375.png') })
  await p.context().close()
  console.log('shot chat-drawer')
}

// 5. Toast（触发一次失败反馈或成功操作 — 用主题切换不行，用创建空表单提交触发校验 toast）
{
  const p = await authedPage()
  await p.goto(BASE + '/tickets?create=1', { waitUntil: 'networkidle' })
  await p.waitForTimeout(500)
  // 空表单提交 → 校验 toast
  await p.getByRole('button', { name: '创建工单' }).click().catch(() => {})
  await p.waitForTimeout(300)
  await p.screenshot({ path: join(OUT, 'ix-toast--dark--1440.png') })
  await p.context().close()
  console.log('shot toast')
}

// 6. 流式消息（发送一条，截流式中状态）
{
  const p = await authedPage()
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  const input = p.locator('textarea').first()
  await input.fill('VPN 连不上怎么办？')
  await p.waitForTimeout(150)
  await input.press('Enter')
  // 流式中截一张（mock 流式较快，多试几个时间点）
  await p.waitForTimeout(400)
  await p.screenshot({ path: join(OUT, 'ix-streaming--dark--1440.png') })
  await p.waitForTimeout(1500)
  await p.screenshot({ path: join(OUT, 'ix-stream-done--dark--1440.png') })
  await p.context().close()
  console.log('shot streaming')
}

// 7. 对话标签编辑（桌面侧栏 hover → 编辑标签按钮）
{
  const p = await authedPage()
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  const firstConv = p.locator('aside button').filter({ hasText: 'VPN' }).first()
  await firstConv.hover().catch(() => {})
  await p.waitForTimeout(200)
  await p.locator('button[aria-label="编辑标签"]').first().click().catch(() => {})
  await p.waitForTimeout(300)
  await p.screenshot({ path: join(OUT, 'ix-tag-edit--dark--1440.png') })
  await p.context().close()
  console.log('shot tag-edit')
}

// 8. 移动端新建工单弹窗 375
{
  const p = await authedPage(375, 812)
  await p.goto(BASE + '/tickets?create=1', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  await p.screenshot({ path: join(OUT, 'ix-ticket-modal--dark--375.png') })
  await p.context().close()
  console.log('shot ticket-modal-375')
}

// 9. 亮色命令面板 + 亮色 Toast 对照
{
  const p = await authedPage(1440, 900, 'light')
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(500)
  await p.keyboard.press('Control+k')
  await p.waitForTimeout(350)
  await p.screenshot({ path: join(OUT, 'ix-palette--light--1440.png') })
  await p.context().close()
  console.log('shot palette-light')
}

// 10. 键盘 focus-visible（Tab 导航到登录按钮/导航项）
{
  const p = await authedPage()
  await p.goto(BASE + '/chat', { waitUntil: 'networkidle' })
  await p.waitForTimeout(500)
  // Tab 几次让 focus 落到左侧导航
  for (let i = 0; i < 6; i++) { await p.keyboard.press('Tab'); await p.waitForTimeout(60) }
  await p.screenshot({ path: join(OUT, 'ix-focus-ring--dark--1440.png') })
  await p.context().close()
  console.log('shot focus-ring')
}

// 11. KB 移动端展开行 375
{
  const p = await authedPage(375, 812)
  await p.goto(BASE + '/admin/kb', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  await p.locator('button[aria-label*="展开"], button[aria-label*="expand"]').first().click().catch(() => {})
  await p.waitForTimeout(700)
  await p.screenshot({ path: join(OUT, 'ix-kb-expand--dark--375.png') })
  await p.context().close()
  console.log('shot kb-expand-375')
}

// 12. AuditLogs 移动端 375
{
  const p = await authedPage(375, 812, 'light')
  await p.goto(BASE + '/admin/audit', { waitUntil: 'networkidle' })
  await p.waitForTimeout(600)
  await p.screenshot({ path: join(OUT, 'ix-audit--light--375.png') })
  await p.context().close()
  console.log('shot audit-375')
}

await browser.close()
console.log('done')
