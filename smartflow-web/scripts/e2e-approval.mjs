/**
 * 审批流 E2E（真后端 8000 + dev 5173）
 * 覆盖：登录 → 建紧急单 → 审批链展示 → 客服批一级 → 等待上级；驳回路径 → 已驳回终态
 * 前置：testuser 临时角色 agent；后端 uvicorn 在 8000
 * 注意：agent 不在后端限流白名单（10次/分钟，GET 也计数），
 *      脚本开头和中段会各清一次 Redis 计数（rate:1:* / quota:1:*），否则中途必 429
 */
import { chromium } from 'playwright'
import fs from 'node:fs'
import { execFileSync } from 'node:child_process'

// 清 testuser(user_id=1) 的限流计数，只删测试数据 key，不碰后端代码
const flushRate = () =>
  execFileSync('D:/DevCache/conda/envs/mianshi/python.exe', [
    '-c',
    "import redis;r=redis.Redis(host='127.0.0.1',port=6379,db=0);[r.delete(k) for p in ('rate:1:*','quota:1:*') for k in r.scan_iter(p)]",
  ])

const BASE = 'http://localhost:5173'
const SHOTS = 'shots/e2e-approval'
fs.mkdirSync(SHOTS, { recursive: true })

const results = []
const ok = (name, pass, extra = '') => {
  results.push({ name, pass, extra })
  console.log(`${pass ? 'PASS' : 'FAIL'}  ${name}${extra ? '  → ' + extra : ''}`)
}

// 每次跑生成唯一后缀，避免重跑时同名工单让点击选择器命中多个
const runId = Date.now().toString().slice(-6)
const T1 = `E2E-机房割接停机8小时-${runId}`
const T2 = `E2E-驳回测试单-${runId}`

flushRate()  // 开跑前清限流

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } })

try {
  // ── 登录 ──
  await page.goto(`${BASE}/login`)
  await page.fill('input[placeholder="请输入用户名"]', 'testuser')
  await page.fill('input[placeholder="请输入密码"]', '123456')
  await page.click('button[type="submit"]')
  await page.waitForURL('**/chat', { timeout: 10000 })
  ok('登录跳转 /chat', true)

  // ── 建紧急单 ──
  await page.goto(`${BASE}/tickets`)
  await page.click('button:has-text("新建工单")')
  await page.fill('input[placeholder="一句话概括问题"]', T1)
  await page.fill('textarea', 'E2E 自动化测试建单：明晨02:00-10:00核心交换机割接')
  await page.locator('select').nth(1).selectOption('urgent')
  await page.screenshot({ path: `${SHOTS}/1-create-urgent.png` })
  await page.click('button:has-text("创建工单")')
  // 弹窗关闭 = 标题 h3 被 v-if 卸载；顶部按钮里的"新建工单"不是 h3，不会误命中
  await page.waitForSelector('h3:has-text("新建工单")', { state: 'detached', timeout: 8000 })
  ok('紧急单创建（弹窗关闭）', true)

  // 列表出现新单 → 点进详情
  await page.click(`p:has-text("${T1}")`)
  await page.waitForSelector('text=审批链', { timeout: 8000 })
  ok('详情页出现审批链卡片', true)

  // ── 审批链展示断言 ──
  const hasApproveBtn = await page.locator('button:has-text("通过")').count()
  const hasRejectBtn = await page.locator('button:has-text("驳回")').count()
  const waitAdmin = await page.locator('text=等待管理员审批').count()
  ok('第1级显示通过/驳回按钮', hasApproveBtn === 1 && hasRejectBtn === 1, `通过×${hasApproveBtn} 驳回×${hasRejectBtn}`)
  ok('第2级显示等待管理员审批', waitAdmin === 1)
  await page.screenshot({ path: `${SHOTS}/2-detail-chain.png`, fullPage: true })

  // ── 客服批第1级 ──
  await page.fill('input[placeholder="审批意见（可选）"]', 'E2E：确认割接窗口')
  await page.click('button:has-text("通过")')
  // 注意：toast 文案"第1级已通过，等待上级审批"自带"已通过/等待上级"字样，
  // 直接等全局 text 会被 toast 提前满足（计数落在骨架屏空窗期）。必须圈进审批链 ol 再等。
  await page.locator('ol').filter({ hasText: '已通过' }).waitFor({ state: 'visible', timeout: 8000 })
  ok('批1级后审批链出现已通过', true)
  const stillPending = await page.locator('text=待处理').count()
  const waitAdmin2 = await page.locator('text=等待管理员审批').count()
  ok('批1级后工单仍待处理', stillPending >= 1, `待处理×${stillPending}`)
  ok('批1级后第2级仍等待管理员', waitAdmin2 === 1, `等待管理员×${waitAdmin2}`)
  await page.screenshot({ path: `${SHOTS}/3-level1-approved.png`, fullPage: true })

  // ── 驳回路径：再建 high 单，驳回 ──
  flushRate()  // 前半段已消耗约10次请求配额，进后半段前再清一次
  await page.goto(`${BASE}/tickets`)
  await page.click('button:has-text("新建工单")')
  await page.fill('input[placeholder="一句话概括问题"]', T2)
  await page.fill('textarea', 'E2E：这单会被驳回')
  await page.locator('select').nth(1).selectOption('high')
  await page.click('button:has-text("创建工单")')
  await page.waitForSelector('h3:has-text("新建工单")', { state: 'detached', timeout: 8000 })
  await page.click(`p:has-text("${T2}")`)
  await page.waitForSelector('text=审批链', { timeout: 8000 })
  await page.fill('input[placeholder="审批意见（可选）"]', 'E2E：预算不足')
  await page.click('button:has-text("驳回")')
  // 同样圈进 ol：toast 文案可能含"已驳回"，全局等待会被提前满足
  await page.locator('ol').filter({ hasText: '已驳回' }).waitFor({ state: 'visible', timeout: 8000 })
  const heroRejected = await page.locator('text=已驳回').count()
  ok('驳回后出现已驳回状态', heroRejected >= 1, `已驳回×${heroRejected}`)
  // 驳回是终态：流转操作卡片应该消失
  const flowCard = await page.locator('text=流转操作').count()
  ok('驳回后无流转操作（终态）', flowCard === 0)
  await page.screenshot({ path: `${SHOTS}/4-rejected.png`, fullPage: true })

} catch (e) {
  ok('脚本执行', false, e.message)
  await page.screenshot({ path: `${SHOTS}/99-error.png`, fullPage: true }).catch(() => {})
} finally {
  await browser.close()
  const failed = results.filter(r => !r.pass)
  console.log(`\n===== ${results.length - failed.length}/${results.length} 通过 =====`)
  process.exit(failed.length ? 1 : 0)
}
