// ⑫ 生成评测前端全链路 E2E：登录 → 前置 compare(9vs10) → 点"跑生成评测" → 真进度条递增
//      → 第二标签页并行点击得 409 toast → A/B 接力完成 → compare 切到新 pair 且无"跳过"徽章
// 数据流：chromium headless → /login → /admin/eval → 点按钮 → 5s 轮询进度 DOM → 断言 toast/徽章/表格
// 用法：node scripts/eval_e2e_gen.mjs（需 dev :5173 + backend :8000；全程约 16-20 分钟，24 例子集）
import { chromium } from 'playwright'

const BASE = 'http://localhost:5173'
const results = []
const ts = () => new Date().toTimeString().slice(0, 8)
const log = (msg) => console.log(`[${ts()}] ${msg}`)
const check = (name, ok, extra = '') => {
  results.push({ name, ok, extra })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`)
}

const browser = await chromium.launch()
const ctx = await browser.newContext()
const page = await ctx.newPage()
const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(e.message))

try {
  // 1. 登录
  await page.goto(BASE + '/login')
  await page.fill('input[type="text"], input[placeholder*="用户"], input[placeholder*="账号"]', 'dxr')
  await page.fill('input[type="password"]', '123456')
  await page.click('button[type="submit"]')
  await page.waitForURL(/\/(chat|admin)/, { timeout: 10000 })
  check('登录跳转', true)

  // 2. 前置断言：页面上已有的 run9(A)/run10(B) compare 渲染真实统计（12 正+12 负配对，不该有"跳过"）
  await page.goto(BASE + '/admin/eval')
  await page.waitForLoadState('networkidle')
  const body0 = await page.textContent('body')
  check('前置 compare 9vs10 上屏', body0.includes('Run #9') && body0.includes('Run #10'))
  check('前置 F/R/refusal 无跳过徽章', (await page.getByText('跳过', { exact: true }).count()) === 0)

  // 3. 点击"跑生成评测（A+B）"——前端自动 A 完成后接力 B
  log('点击生成评测，等待进度条…')
  await page.click('button:has-text("跑生成评测")')
  await page.waitForSelector('text=/\\d+\\/24/', { timeout: 30000 })
  check('进度条出现（x/24）', true)

  // 4. 真进度采样：35 秒后 done 必须增长（服务端真进度，不是假动画）
  const doneNow = () => page.evaluate(() => Number(document.body.innerText.match(/(\d+)\/24 ·/)?.[1] ?? -1))
  const d1 = await doneNow()
  log(`进度采样 t0: ${d1}/24，等 35s 复采…`)
  await page.waitForTimeout(35000)
  const d2 = await doneNow()
  check('进度递增（真轮询）', d2 > d1, `${d1}/24 → ${d2}/24`)

  // 5. 第二标签页并行点击 → 后端 409 → 前端 toast 展示 detail（A 组还在跑，窗口安全）
  log('开第二标签页测 409 互斥…')
  const page2 = await ctx.newPage()
  await page2.goto(BASE + '/admin/eval')
  await page2.waitForLoadState('networkidle')
  await page2.click('button:has-text("跑生成评测")')
  await page2.waitForSelector('text=已有生成评测在跑', { timeout: 15000 })
  check('二标签页 409 toast', true)
  await page2.close()

  // 6. 等 A 完成 toast（3s 短暂展示，持续轮询等它出现）→ B 组接力进度
  log('等 A 组完成 toast（约 6-8 分钟）…')
  await page.waitForSelector('text=A 组生成评测完成', { timeout: 12 * 60 * 1000 })
  check('A 组完成 toast', true)
  await page.waitForSelector('text=/B 组/', { timeout: 30000 })
  check('B 组接力进度', true)

  // 7. 等 B 完成 toast → loadRuns 刷新 → compare watch 切到新 pair
  log('等 B 组完成 toast（约 6-8 分钟）…')
  await page.waitForSelector('text=B 组生成评测完成', { timeout: 12 * 60 * 1000 })
  check('B 组完成 toast', true)

  // 8. compare 切到新 pair（run id 接力递增：9,10 之后是 11,12）；F/R/refusal 应有真实显著性块
  await page.waitForSelector('text=Run #11', { timeout: 60000 })
  const body1 = await page.textContent('body')
  check('compare 切到新 pair 11/12', body1.includes('Run #11') && body1.includes('Run #12'))
  check('新 pair 无跳过徽章', (await page.getByText('跳过', { exact: true }).count()) === 0)
  const sigCount =
    (await page.getByText('不显著', { exact: true }).count()) +
    (await page.getByText('显著', { exact: true }).count())
  check('F/R/refusal 显著性徽章 ≥3', sigCount >= 3, `${sigCount} 枚`)

  // 9. 运行历史前两行 = run12(B)/run11(A)，生成层带拒答率列
  const rows = await page.locator('tbody tr').allTextContents()
  check('历史表新行 12/11', rows.length >= 2 && rows[0].includes('12') && rows[1].includes('11'))

  // 10. 全程无未捕获前端异常
  check('无 pageerror', pageErrors.length === 0, pageErrors.join('; ').slice(0, 200))
} catch (e) {
  check('执行异常', false, e.message)
} finally {
  await browser.close()
}
const failed = results.filter((r) => !r.ok)
log(`${results.length - failed.length}/${results.length} 通过`)
process.exit(failed.length ? 1 : 0)
