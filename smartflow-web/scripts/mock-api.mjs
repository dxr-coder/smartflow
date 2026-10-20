/**
 * mock-api.mjs — 仅用于前端视觉审计的假后端（Node 零依赖，监听 8000）
 * 数据流：vite proxy 把 /auth /chat /tickets 等转发到这里；响应结构对齐真实后端契约
 * 用法：node scripts/mock-api.mjs
 */
import http from 'node:http'

let convSeq = 100
let ticketSeq = 30

const conversations = [
  { id: 1, title: 'VPN 连不上公司内网', tags: ['IT', '网络'], created_at: '2026-10-09T09:12:00Z' },
  { id: 2, title: '年假余额怎么查', tags: ['HR'], created_at: '2026-10-08T14:02:00Z' },
  { id: 3, title: '打印机驱动安装', tags: ['IT', '行政'], created_at: '2026-10-07T11:30:00Z' },
  { id: 4, title: '报销单被退回的原因', tags: ['财务'], created_at: '2026-10-05T16:45:00Z' },
  { id: 5, title: '新电脑领用流程', tags: ['行政'], created_at: '2026-10-03T10:00:00Z' },
]

const messages = {
  1: [
    { role: 'user', content: 'VPN 连不上公司内网了，一直提示认证失败' },
    {
      role: 'assistant',
      message_id: 'm1',
      agent_name: 'IT 助手',
      source: 'kb',
      citations: [
        { index: 0, document_name: 'IT服务手册.pdf' },
        { index: 1, document_name: 'VPN常见问题.md' },
      ],
      content:
        'VPN 认证失败通常有三个原因，按顺序排查：\n\n1. **客户端版本过旧** — 请确认使用 v3.2 及以上版本（帮助 → 关于）\n2. **密码未同步** — 如果刚改过密码，去[账号中心](https://account.internal)重置 VPN 密码，同步延迟约 5 分钟\n3. **双因素令牌过期** — 打开企业助手 App 重新生成 6 位验证码\n\n```bash\n# Windows 下快速清缓存\nipconfig /flushdns\n```\n\n如果以上都试过仍不行，回复「转人工」，IT 值班同学会接入。',
    },
    { role: 'user', content: '重置密码后还是不行' },
    {
      role: 'assistant',
      message_id: 'm2',
      agent_name: 'IT 助手',
      source: 'web',
      citations: [],
      content:
        '已为你创建工单 **#12**（IT 支持 · 紧急），值班工程师会在 15 分钟内响应。你也可以直接回复「转人工」立即接通在线值班。',
    },
  ],
  2: [
    { role: 'user', content: '年假还剩多少天怎么看？' },
    {
      role: 'assistant',
      message_id: 'm3',
      agent_name: 'HR 助手',
      source: 'kb',
      citations: [{ index: 0, document_name: '员工手册2026.pdf' }],
      content:
        '打开 **自助服务台 → 假期额度**，可以看到年假、调休、病假的实时余额与到期日。也可以在企业微信搜索「假期助手」小程序随时查。',
    },
  ],
  3: [
    { role: 'user', content: '怎么安装公司打印机的驱动？' },
    {
      role: 'assistant',
      message_id: 'm4',
      agent_name: '行政助手',
      source: 'kb',
      citations: [{ index: 0, document_name: '打印服务指引.md' }],
      content:
        '连接公司 Wi-Fi 后访问 **print.internal.corp**，双击对应打印机的安装包即可自动安装驱动。 macOS 用户在「系统设置 → 打印机」点 + 号自动发现。',
    },
  ],
}

const tickets = [
  { id: 12, title: 'VPN 认证持续失败，需人工介入', content: '已按手册排查客户端版本与密码同步，仍无法连接 vpn.internal.corp', status: 'pending', created_at: '2026-10-09T09:20:00Z' },
  { id: 11, title: '申请开通 Jira 项目权限', content: '需要 PROJ 项目的 Contributor 权限', status: 'processing', created_at: '2026-10-08T13:10:00Z' },
  { id: 10, title: '显示器申请更换', content: '当前显示器有竖线，工位 A3-21', status: 'resolved', created_at: '2026-10-06T10:05:00Z' },
  { id: 9, title: '报销单 #8891 被退回', content: '退回理由显示信息不完整，需要补充发票明细', status: 'closed', created_at: '2026-10-04T15:42:00Z' },
  { id: 8, title: '新员工入职设备领用', content: '10 月 15 日入职，需要 MacBook + 显示器 + 门禁卡', status: 'escalated', created_at: '2026-10-02T09:00:00Z' },
]

const transfers = [
  { id: 3, ticket_id: 12, ticket_title: 'VPN 认证持续失败，需人工介入', reason: '自助排查未解决，需要远程协助', status: 'pending', created_at: '2026-10-09T09:25:00Z' },
  { id: 2, ticket_id: 11, ticket_title: '申请开通 Jira 项目权限', reason: '需要项目经理审批后开通', status: 'accepted', created_at: '2026-10-08T13:30:00Z' },
]

const users = [
  { id: 1, username: 'admin', role_name: 'admin', status: 'active' },
  { id: 2, username: 'zhangsan', role_name: 'support', status: 'active' },
  { id: 3, username: 'lisi', role_name: 'user', status: 'active' },
  { id: 4, username: 'wangwu', role_name: 'user', status: 'disabled' },
  { id: 5, username: 'zhaoliu', role_name: 'user', status: 'active' },
]

const documents = [
  { id: 1, filename: 'IT服务手册2026.pdf', department: 'IT', status: 'active', created_at: '2026-09-28T08:00:00Z' },
  { id: 2, filename: '员工手册2026.pdf', department: 'HR', status: 'active', created_at: '2026-09-20T08:00:00Z' },
  { id: 3, filename: '报销制度v3.md', department: '财务', status: 'active', created_at: '2026-09-15T08:00:00Z' },
  { id: 4, filename: '办公设备领用指引.md', department: '行政', status: 'processing', created_at: '2026-10-09T10:00:00Z' },
  { id: 5, filename: 'VPN常见问题.md', department: 'IT', status: 'active', created_at: '2026-09-10T08:00:00Z' },
  { id: 6, filename: '旧版打印指引.docx', department: '行政', status: 'failed', created_at: '2026-08-30T08:00:00Z' },
]

const auditLogs = Array.from({ length: 47 }, (_, i) => {
  const actions = ['login', 'document_upload', 'role_change', 'sensitive_blocked', 'ticket_create', 'feedback']
  const names = ['admin', 'zhangsan', 'lisi', 'wangwu', 'zhaoliu']
  return {
    id: i + 1,
    action: actions[i % actions.length],
    username: names[i % names.length],
    detail: [
      '用户登录',
      '上传文档 IT服务手册2026.pdf',
      '将 lisi 角色改为 support',
      '消息包含手机号，已脱敏拦截',
      '创建工单 #12',
      '对消息 m1 点赞',
    ][i % 6],
    created_at: new Date(Date.UTC(2026, 9, 9 - Math.floor(i / 8), 9 + (i % 9), (i * 7) % 60)).toISOString(),
  }
})

const abStats = [
  { variant: 'A', likes: 326, dislikes: 41 },
  { variant: 'B', likes: 402, dislikes: 28 },
]

const json = (res, data, code = 200) => {
  res.writeHead(code, { 'Content-Type': 'application/json; charset=utf-8' })
  res.end(JSON.stringify(data))
}

const readBody = async (req) => {
  const chunks = []
  for await (const c of req) chunks.push(c)
  return Buffer.concat(chunks).toString('utf8')
}

const server = http.createServer(async (req, res) => {
  const u = new URL(req.url, 'http://localhost')
  const p = u.pathname
  const method = req.method

  // CORS（直连时用）
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Headers', '*')
  res.setHeader('Access-Control-Allow-Methods', '*')
  if (method === 'OPTIONS') return res.writeHead(204).end()

  // ---- auth ----
  if (p === '/auth/login') {
    return json(res, { access_token: 'mock-token', refresh_token: 'mock-refresh' })
  }
  if (p === '/auth/register') return json(res, { ok: true })
  if (p === '/auth/me') {
    return json(res, { id: 1, username: 'admin', role_name: 'admin', status: 'active', department: 'IT' })
  }

  // ---- conversations ----
  if (p === '/conversations' && method === 'GET') return json(res, { items: conversations })
  if (p === '/conversations' && method === 'POST') {
    convSeq += 1
    const c = { id: convSeq, title: '新对话', tags: [], created_at: new Date().toISOString() }
    conversations.unshift(c)
    messages[convSeq] = []
    return json(res, { id: convSeq })
  }
  let m = p.match(/^\/conversations\/(\d+)\/messages$/)
  if (m && method === 'GET') return json(res, { items: messages[m[1]] || [] })
  m = p.match(/^\/conversations\/(\d+)\/tags$/)
  if (m && method === 'PUT') {
    const conv = conversations.find((c) => c.id === Number(m[1]))
    const tags = (u.searchParams.get('tags') || '').split(',').filter(Boolean)
    if (conv) conv.tags = tags
    return json(res, { ok: true })
  }

  // ---- chat SSE ----
  if (p === '/chat/stream') {
    res.writeHead(200, {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache',
      Connection: 'keep-alive',
    })
    const meta = {
      agent_name: 'IT 助手',
      source: 'kb',
      citations: [
        { index: 0, document_name: '服务台白皮书.pdf' },
      ],
      message_id: 'm-' + Date.now(),
    }
    res.write(JSON.stringify(meta) + '\n')
    const answer =
      '你好！我是 SmartFlow 智能服务台。根据**服务台白皮书**，我可以帮你处理 IT、HR、行政、财务四类内部请求。\n\n' +
      '- 自助查询：VPN、打印机、账号权限\n- 流程咨询：报销、请假、入职\n- 复杂问题：自动创建工单并跟踪 SLA\n\n' +
      '试试问我「年假怎么查」或者「VPN 连不上怎么办」。'
    let i = 0
    const timer = setInterval(() => {
      if (i >= answer.length) {
        clearInterval(timer)
        res.end()
        return
      }
      res.write(answer.slice(i, i + 3))
      i += 3
    }, 16)
    return
  }
  if (p === '/feedback' && method === 'POST') {
    await readBody(req)
    return json(res, { ok: true })
  }

  // ---- tickets ----
  if (p === '/tickets' && method === 'GET') return json(res, { items: tickets })
  if (p === '/tickets' && method === 'POST') {
    const body = JSON.parse(await readBody(req) || '{}')
    ticketSeq += 1
    const t = { id: ticketSeq, title: body.title || '未命名工单', content: body.content || '', status: 'pending', created_at: new Date().toISOString() }
    tickets.unshift(t)
    return json(res, t)
  }
  m = p.match(/^\/tickets\/(\d+)$/)
  if (m && method === 'GET') {
    const t = tickets.find((x) => x.id === Number(m[1]))
    return t ? json(res, t) : json(res, { detail: 'not found' }, 404)
  }
  m = p.match(/^\/tickets\/(\d+)\/status$/)
  if (m && method === 'PUT') {
    const t = tickets.find((x) => x.id === Number(m[1]))
    if (t) t.status = u.searchParams.get('new_status') || t.status
    return json(res, { ok: true })
  }

  // ---- transfer ----
  if (p === '/transfer' && method === 'GET') return json(res, { items: transfers })
  m = p.match(/^\/transfer\/(\d+)\/accept$/)
  if (m && method === 'PUT') {
    const t = transfers.find((x) => x.id === Number(m[1]))
    if (t) t.status = 'accepted'
    return json(res, { ok: true })
  }

  // ---- users ----
  if (p === '/users' && method === 'GET') return json(res, { items: users })
  m = p.match(/^\/users\/(\d+)\/role$/)
  if (m && method === 'PUT') {
    const x = users.find((v) => v.id === Number(m[1]))
    if (x) x.role_name = u.searchParams.get('role_name') || x.role_name
    return json(res, { ok: true })
  }
  m = p.match(/^\/users\/(\d+)\/status$/)
  if (m && method === 'PUT') {
    const x = users.find((v) => v.id === Number(m[1]))
    if (x) x.status = u.searchParams.get('status') || x.status
    return json(res, { ok: true })
  }

  // ---- documents ----
  if (p === '/documents' && method === 'GET') return json(res, { items: documents })
  if (p === '/documents' && method === 'POST') {
    await readBody(req) // consume multipart
    documents.unshift({ id: documents.length + 10, filename: '新上传文档.pdf', department: 'IT', status: 'processing', created_at: new Date().toISOString() })
    return json(res, { ok: true })
  }
  m = p.match(/^\/documents\/(\d+)\/chunks$/)
  if (m) {
    return json(res, {
      items: [
        { content: 'VPN 客户端需使用 v3.2 及以上版本，认证服务器为 vpn.internal.corp。' },
        { content: '若提示认证失败，请先在账号中心重置 VPN 密码，密码同步延迟约 5 分钟。' },
        { content: '双因素令牌每日 0 点刷新，连续 5 次错误将锁定账号 30 分钟。' },
      ],
    })
  }
  m = p.match(/^\/documents\/(\d+)\/versions$/)
  if (m) {
    return json(res, {
      items: [
        { filename: 'v3 当前版本', created_at: '2026-09-28T08:00:00Z' },
        { filename: 'v2', created_at: '2026-06-12T08:00:00Z' },
        { filename: 'v1 初版', created_at: '2026-03-01T08:00:00Z' },
      ],
    })
  }
  m = p.match(/^\/documents\/(\d+)$/)
  if (m && method === 'DELETE') {
    const i = documents.findIndex((d) => d.id === Number(m[1]))
    if (i >= 0) documents.splice(i, 1)
    return json(res, { ok: true })
  }

  // ---- audit ----
  if (p === '/audit/logs') {
    const page = Number(u.searchParams.get('page') || 1)
    const size = 10
    return json(res, { items: auditLogs.slice((page - 1) * size, page * size), total: auditLogs.length })
  }

  // ---- ab test ----
  if (p === '/ab-test/stats') return json(res, { items: abStats })

  // ---- stats ----
  if (p === '/stats/overview') {
    return json(res, {
      total_conversations: 1284,
      today_conversations: 63,
      total_tickets: 217,
      today_tickets: 9,
      total_users: 86,
      total_documents: 42,
      ai_resolve_rate: 0.78,
    })
  }
  if (p === '/stats/trends') {
    const days = Number(u.searchParams.get('days') || 7)
    const dates = []
    const convs = []
    const tix = []
    for (let i = days - 1; i >= 0; i--) {
      const d = new Date(Date.UTC(2026, 9, 9 - i))
      dates.push(`${d.getUTCMonth() + 1}/${d.getUTCDate()}`)
      convs.push(40 + Math.round(Math.sin(i * 1.3) * 18 + i * 2))
      tix.push(5 + Math.round(Math.cos(i * 0.9) * 4 + i * 0.3))
    }
    return json(res, { dates, conversations: convs, tickets: tix })
  }

  json(res, { detail: `mock 未实现: ${method} ${p}` }, 404)
})

const PORT = Number(process.env.MOCK_PORT || 8001)
server.listen(PORT, '127.0.0.1', () => console.log(`mock-api on http://127.0.0.1:${PORT}`))
