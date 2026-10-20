# SmartFlow — AI 智能客服系统 产品需求文档（PRD）

> 项目代号：SmartFlow
> 版本：v2.0
> 日期：2026-09-22

---

## 一、产品定位

**帮企业解决"内部知识找不到、客服效率低"的问题。**

用户（企业员工/客户）提问 → AI 基于企业私有知识库准确回答 → 复杂问题自动创建工单 → 需要时无缝转人工。

**不是聊天机器人 demo，是完整的客服业务系统。**

### 目标用户

| 角色 | 使用场景 |
|------|---------|
| 普通用户（员工/客户） | 提问、查问题、提交工单 |
| 客服人员 | 接管 AI 无法回答的对话、处理工单 |
| 管理员 | 管理知识库、用户、查看数据统计 |

---

## 二、核心业务流程

```
用户来了
  │
  ├─ "退货政策是什么"     → AI 基于知识库回答（RAG）
  │
  ├─ "我的订单什么状态"   → AI 查订单系统（Agent 调 API）
  │
  ├─ "我要退款"          → AI 引导填写工单 → 自动分类 → 创建工单
  │
  ├─ "转人工"            → AI 判断 → 转接人工客服
  │
  └─ "连续2次不确定"     → AI 自动建议转人工
```

---

## 三、功能清单（按版本）

### v1：AI 自动问答（已完成）

| 功能 | 说明 |
|------|------|
| 文档上传 | TXT → 切分 → 向量化 → ChromaDB |
| 智能问答 | RAG 检索 + LLM 生成 + 多轮对话 |
| Agent 工具 | 计算器（预留扩展） |
| 日志追踪 | 耗时、Token、决策链 |
| Docker 部署 | docker-compose 一键启动 |

### v2：多用户 + 权限 + 业务闭环

| 功能 | 说明 | 优先级 |
|------|------|--------|
| JWT 认证 | 注册/登录/access_token + refresh_token | P0 |
| RBAC 权限 | 管理员/客服/普通用户三级 | P0 |
| 权限隔离 | 管理员看全部，客服看分配的，用户只看自己的 | P0 |
| 工单系统 | 创建→AI自动分类→状态流转→关闭 | P0 |
| 转人工机制 | AI不确定/用户主动要求 → 转接 → AI退场 | P0 |
| SSE 流式输出 | 回答逐字显示 | P0 |
| PDF 解析 | pypdf 提取文本 → 切分 → 向量化 | P0 |
| Redis 缓存 | 语义缓存，重复问题省 Token | P0 |
| 使用配额 | 普通用户每天 50 次 | P1 |

### v3：前端 + 数据分析

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 用户端聊天界面 | Vue3 气泡 + Markdown + 打字机效果 | P0 |
| 工单提交/查看 | 用户端工单管理 | P0 |
| 管理后台 | 知识库/工单/用户管理 | P0 |
| 数据看板 | ECharts 图表（对话量/解决率/响应时间/Token） | P0 |
| Agent 推理可视化 | 实时展示 AI 每步决策 | P1 |
| WebSocket 通知 | 新工单/转人工实时推送 | P1 |

### v4：多 Agent 协作

| 功能 | 说明 | 优先级 |
|------|------|--------|
| 意图分类 Agent | 判断用户意图（知识库/工单/转人工/闲聊） | P0 |
| 知识库 Agent | RAG 检索和回答 | P0 |
| 工单 Agent | 工单创建/查询/流转 | P0 |
| 搜索 Agent | 知识库没有时联网搜索 | P1 |
| 协调 Agent | 路由+汇总 | P0 |
| 插件系统 | 新工具自动注册 | P0 |
| 工作流引擎 | LangGraph 状态机 | P1 |
| 对话分支 | 多个回答供选择 | P2 |
| 自动摘要 | 长对话压缩 token | P2 |

### v5：生产级上线

| 功能 | 说明 | 优先级 |
|------|------|--------|
| K8s 部署 | Deployment + Service + Ingress + HPA | P0 |
| CI/CD | GitHub Actions 自动构建部署 | P0 |
| 安全加固 | SQL注入/XSS/速率限制/文件校验/日志脱敏 | P0 |
| 成本优化 | 语义缓存/模型路由/Token预算 | P0 |
| 监控告警 | Prometheus + Grafana + 飞书通知 | P0 |
| 压力测试 | locust 压测 + 报告 + 扩容方案 | P1 |

---

## 四、数据库设计

### MySQL

```sql
-- 用户表
CREATE TABLE users (
    id INT PRIMARY KEY AUTO_INCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    password_hash VARCHAR(200) NOT NULL,
    role ENUM('admin', 'support', 'user') DEFAULT 'user',
    quota_daily INT DEFAULT 50,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话表
CREATE TABLE conversations (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    title VARCHAR(200) DEFAULT '新对话',
    status ENUM('active', 'transferred', 'closed') DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- 消息表
CREATE TABLE messages (
    id INT PRIMARY KEY AUTO_INCREMENT,
    conversation_id INT NOT NULL,
    role ENUM('user', 'assistant', 'system') NOT NULL,
    content TEXT NOT NULL,
    tool_calls JSON,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
);

-- 工单表
CREATE TABLE tickets (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    conversation_id INT,
    category ENUM('refund', 'complaint', 'consult', 'other') NOT NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    status ENUM('pending', 'processing', 'resolved', 'closed') DEFAULT 'pending',
    assigned_to INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (assigned_to) REFERENCES users(id)
);

-- 日志表
CREATE TABLE logs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id INT,
    conversation_id INT,
    event_type ENUM('request', 'agent_step', 'tool_call', 'error') NOT NULL,
    input TEXT,
    output TEXT,
    duration_ms INT,
    tokens_used INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 五、API 设计（v2）

### 认证

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /auth/register | 注册 |
| POST | /auth/login | 登录（返回 access_token + refresh_token） |
| POST | /auth/refresh | 刷新 token |

### 知识库

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /documents | admin | 上传文档 |
| GET | /documents | admin | 文档列表 |
| DELETE | /documents/{id} | admin | 删除文档 |

### 对话

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /conversations | 新建对话 |
| GET | /conversations | 对话列表（按权限过滤） |
| DELETE | /conversations/{id} | 删除对话 |
| POST | /conversations/{id}/messages | 发送消息（SSE 流式返回） |
| GET | /conversations/{id}/messages | 获取历史 |

### 工单

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| POST | /tickets | user | 创建工单 |
| GET | /tickets | support/admin | 工单列表 |
| PUT | /tickets/{id}/status | support/admin | 更新工单状态 |
| PUT | /tickets/{id}/assign | admin | 分配客服 |

### 用户管理

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /users | admin | 用户列表 |
| PUT | /users/{id}/role | admin | 修改角色 |
| PUT | /users/{id}/status | admin | 禁用/启用 |

### 可观测

| 方法 | 路径 | 权限 | 说明 |
|------|------|------|------|
| GET | /stats/overview | admin | 数据概览 |
| GET | /stats/trends | admin | 趋势数据 |
| GET | /logs | admin | 日志查询 |
| GET | /health | public | 健康检查 |

---

## 六、非功能需求

| 项目 | 要求 |
|------|------|
| 响应时间 | 普通问答 < 5s，工具调用 < 10s |
| 并发 | v1: 10人 / v5: 100+人 |
| 数据安全 | 密钥走 .env，密码 bcrypt，日志脱敏 |
| 可观测 | 关键操作有日志，异常有堆栈 |
| 可部署 | Docker 一键启动（v1-v2）/ K8s（v5） |
| 成本控制 | 语义缓存 + 模型路由 + Token 预算（v5） |
