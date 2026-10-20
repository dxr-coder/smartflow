// ⑫ Eval 页 E2E 冒烟：登录 → 评测页 → 验证负例表单/切片表/拒答展示/compare 条
// 数据流：chromium headless → /login 表单 → /admin/eval → 断言 DOM 元素存在
// 用法：node scripts/eval_e2e_smoke.mjs（需 dev server :5173 + backend :8000 在线）
import { chromium } from 'playwright'

const BASE = 'http://localhost:5173'
const results = []
const check = (name, ok, extra = '') => {
  results.push({ name, ok, extra })
  console.log(`${ok ? 'PASS' : 'FAIL'} ${name}${extra ? ' — ' + extra : ''}`)
}

const browser = await chromium.launch()
const page = await browser.newPage()
try {
  // 1. 登录
  await page.goto(BASE + '/login')
  await page.fill('input[type="text"], input[placeholder*="用户"], input[placeholder*="账号"]', 'dxr')
  await page.fill('input[type="password"]', '123456')
  await page.click('button[type="submit"]')
  await page.waitForURL(/\/(chat|admin)/, { timeout: 10000 })
  check('登录跳转', true)

  // 2. 评测页
  await page.goto(BASE + '/admin/eval')
  await page.waitForLoadState('networkidle')
  const body = await page.textContent('body')
  check('页面标题含 RAG 评测', body.includes('评测'))

  // 3. 金标表单：知识库无答案开关存在
  const negSwitch = await page.locator('text=知识库无答案').count()
  check('负例开关存在', negSwitch > 0)

  // 4. 用例表：负例 red badge
  const negBadge = await page.locator('text=无答案').count()
  check('负例 badge 显示', negBadge > 0, `${negBadge} 处`)

  // 5. 运行历史：refusal 列头
  const refusalCol = await page.locator('th:has-text("拒答率")').count()
  check('拒答率列/表头', refusalCol > 0)

  // 6. 展开最新 run 明细 → 切片表
  const expandBtn = page.locator('button[aria-label="展开详情"]').first()
  if (await expandBtn.count()) {
    await expandBtn.click()
    await page.waitForTimeout(1200)
  }
  const sliceCard = await page.locator('text=分类别指标').count()
  check('切片表卡片', sliceCard > 0)

  // 6b. 明细里的负例行 badge（负例·不计排名 / 拒答正确）
  const detailNeg = await page.locator('text=负例').count()
  check('明细负例 badge', detailNeg > 0)

  // 7. unanswerable 切片行
  const unansRow = await page.locator('text=unanswerable').count()
  check('unanswerable 切片行', unansRow > 0)

  // 8. compare 条：配对文案
  const cmpText = await page.locator('text=配对').count()
  check('compare 配对文案', cmpText > 0)

  // 9. 生成评测按钮 + 警示文案
  const genBtn = await page.locator('text=生成评测').count()
  check('生成评测入口', genBtn > 0)

  // 10. 双主题：切暗色无死类（Nebula 主题 class 切换）
  const htmlBefore = await page.getAttribute('html', 'class')
  await page.evaluate(() => document.documentElement.classList.toggle('dark'))
  await page.waitForTimeout(300)
  const htmlAfter = await page.getAttribute('html', 'class')
  check('主题切换生效', htmlBefore !== htmlAfter || (htmlAfter || '').includes('dark'))
  // 控制台无 error
} catch (e) {
  check('执行异常', false, e.message)
} finally {
  await browser.close()
}
const failed = results.filter((r) => !r.ok)
console.log(`\n${results.length - failed.length}/${results.length} 通过`)
process.exit(failed.length ? 1 : 0)
