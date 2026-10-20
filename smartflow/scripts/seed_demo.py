# -*- coding: utf-8 -*-
"""
一键重建演示数据
数据流：assets 台账列升级（已存在跳过） → TRUNCATE 业务表 → 重插 8 个用户 / 5 段对话 / 14 张工单 / 12 台资产（含购置/保修/位置） / 工具表数据 / 审计 / trace
不动的表：roles（角色定义）、documents + document_chunks（知识库要真实 embedding，假数据塞不进 Chroma）
所有用户密码统一沿用 testuser 的 bcrypt 哈希 = 123456
"""
import os
import sys
import json
import uuid
import random
import pymysql
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db

NOW = datetime.now()


def d(days=0, hours=0, minutes=0):
    return NOW - timedelta(days=days, hours=hours, minutes=minutes)


# ============ 清空顺序：先子表后主表无所谓，TRUNCATE 都是整表 ============
WIPE = [
    "messages", "conversations", "ticket_approvals", "sla_events", "tickets",
    "csat_ratings", "asset_logs", "assets", "audit_logs", "feedback", "ab_assignments",
    "ab_experiments", "transfer_sessions", "request_traces", "chat_history",
    "leave_requests", "leave_balances", "reimbursements", "it_assets",
    "room_bookings", "meeting_rooms",
    "eval_results", "eval_runs", "eval_case_docs", "eval_cases",
]

db = get_db()
cur = db.cursor()

try:
    # ---------- 0. assets 台账列升级（1060 = 列已存在，跳过） ----------
    new_cols = [
        ("purchase_date", "DATE NULL COMMENT '购置日期' AFTER model"),
        ("price", "DECIMAL(10,2) NULL COMMENT '采购价格' AFTER purchase_date"),
        ("warranty_end", "DATE NULL COMMENT '保修到期日' AFTER price"),
        ("location", "VARCHAR(50) NOT NULL DEFAULT '' COMMENT '存放位置' AFTER warranty_end"),
        ("note", "VARCHAR(200) NOT NULL DEFAULT '' COMMENT '备注' AFTER location"),
    ]
    added = 0
    for col, decl in new_cols:
        try:
            cur.execute(f"ALTER TABLE assets ADD COLUMN {col} {decl}")
            added += 1
        except pymysql.err.OperationalError as e:
            if e.args[0] != 1060:  # Duplicate column
                raise
    print(f"[0/9] assets 台账列：新增 {added} 列（已存在则跳过）")

    # ---------- 0.5 CSAT 评分表（一单一评靠 ticket_id 唯一键兜底） ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS csat_ratings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            ticket_id INT NOT NULL UNIQUE COMMENT '一单一评',
            user_id INT NOT NULL COMMENT '评分人=工单提交人',
            score TINYINT NOT NULL COMMENT '1-5星',
            comment VARCHAR(500) NOT NULL DEFAULT '',
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            KEY idx_user (user_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # ---------- 0.8 RAG 评测三表（回归运行落库；eval_results 不建外键，删用例不毁历史） ----------
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id INT AUTO_INCREMENT PRIMARY KEY,
            question VARCHAR(200) NOT NULL,
            expect_doc VARCHAR(200) NULL COMMENT '主期望文档 documents.filename；负例为 NULL',
            category VARCHAR(30) NOT NULL DEFAULT 'general',
            is_answerable TINYINT NOT NULL DEFAULT 1 COMMENT '0=知识库无答案负例（只评拒答率）',
            is_active TINYINT NOT NULL DEFAULT 1,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    # 多标签期望文档：一条用例可期望多份文档，grade 2=主 / 1=可接受（NDCG 区分主次的依据）
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_case_docs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            case_id INT NOT NULL COMMENT 'eval_cases.id',
            doc_filename VARCHAR(200) NOT NULL COMMENT 'documents.filename',
            grade TINYINT NOT NULL COMMENT '2=主期望 1=可接受',
            KEY idx_case (case_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            variant CHAR(1) NOT NULL,
            case_count INT NOT NULL,
            top_k INT NOT NULL,
            rewrite TINYINT NOT NULL DEFAULT 0 COMMENT '是否开启查询重写',
            mode VARCHAR(16) NOT NULL DEFAULT 'retrieval' COMMENT 'retrieval|generation',
            hit1 DECIMAL(5,4) NOT NULL,
            recall5 DECIMAL(5,4) NOT NULL,
            mrr DECIMAL(5,4) NOT NULL,
            ndcg5 DECIMAL(5,4) NULL COMMENT '分级排序质量',
            faithfulness DECIMAL(5,4) NULL COMMENT '生成层评审均值/5归一',
            relevance DECIMAL(5,4) NULL,
            lat_p50_ms INT NULL COMMENT 'per-case 耗时分位',
            lat_p95_ms INT NULL,
            duration_ms INT NOT NULL,
            kb_snapshot JSON NULL,
            note VARCHAR(200) NULL,
            refusal_rate DECIMAL(5,4) NULL COMMENT '生成层负例拒答正确率',
            judged_count INT NULL COMMENT 'generation 评审成功正例数',
            answerable_count INT NULL COMMENT '可回答用例数（排名指标分母）'
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_results (
            id INT AUTO_INCREMENT PRIMARY KEY,
            run_id INT NOT NULL,
            case_id INT NOT NULL,
            question VARCHAR(200) NOT NULL,
            expected_doc VARCHAR(200) NULL COMMENT '负例为 NULL',
            hit TINYINT NOT NULL COMMENT '负例存 0（NOT NULL 妥协），统计只用 answerable 分母',
            first_rank INT NULL COMMENT 'best_rank：任一期望文档的最好名次',
            retrieved JSON NULL,
            recall5 DECIMAL(5,4) NULL COMMENT 'per-case 分数化',
            ndcg5 DECIMAL(5,4) NULL,
            expected_docs JSON NULL COMMENT '运行时期望快照 [{doc_filename,grade}]',
            duration_ms INT NULL COMMENT 'per-case 管线耗时',
            answer MEDIUMTEXT NULL COMMENT 'generation 模式生成答案',
            judge JSON NULL COMMENT 'generation 评审 {faithfulness,relevance,reason}',
            KEY idx_run (run_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)

    # ---------- 1. 清空（feedback→conversations 有外键，先关检查才能 TRUNCATE） ----------
    cur.execute("SET FOREIGN_KEY_CHECKS=0")
    for t in WIPE:
        cur.execute("TRUNCATE TABLE `" + t + "`")
    cur.execute("SET FOREIGN_KEY_CHECKS=1")
    print(f"[1/9] 已清空 {len(WIPE)} 张表")

    # ---------- 2. 用户（保留 1/2，密码哈希沿用 testuser 的 = 123456） ----------
    cur.execute("SELECT password_hash FROM users WHERE id=1")
    PH = cur.fetchone()["password_hash"]

    cur.execute("UPDATE users SET username='testuser', role='user', role_id=3, status='active' WHERE id=1")
    cur.execute("UPDATE users SET username='dxr', role='admin', role_id=1, status='active' WHERE id=2")
    cur.execute("DELETE FROM users WHERE id > 2")  # 重跑种子时清掉上次插的员工，防撞主键

    new_users = [
        (3, "kefu01",  "support", 2, d(days=60)),
        (4, "kefu02",  "support", 2, d(days=60)),
        (5, "zhangwei", "user",   3, d(days=120)),
        (6, "lina",     "user",   3, d(days=120)),
        (7, "wangfang", "user",   3, d(days=90)),
        (8, "chenjun",  "user",   3, d(days=30)),
    ]
    for uid, name, enum_role, rid, created in new_users:
        cur.execute(
            "INSERT INTO users (id, username, password_hash, role, role_id, status, created_at) "
            "VALUES (%s,%s,%s,%s,%s,'active',%s)",
            (uid, name, PH, enum_role, rid, created),
        )
    print("[2/9] 用户 8 个：dxr(管理员) kefu01/kefu02(客服) testuser+zhangwei+lina+wangfang+chenjun(员工)，密码都是 123456")

    # ---------- 3. 会话 + 消息 ----------
    convs = [
        (1, 1, "年假制度与余额查询", d(days=12), "HR,制度", None, 0),
        (2, 1, "公司 WiFi 连不上", d(days=8), "IT", None, 0),
        (3, 1, "本月报销进度", d(days=5), "财务", None, 0),
        (4, 6, "预订明天下午的会议室", d(days=3), "行政", None, 0),
        (5, 5, "笔记本蓝屏 0x0000007B", d(days=1), "IT,硬件", None, 0),
    ]
    for c in convs:
        cur.execute(
            "INSERT INTO conversations (id, user_id, title, created_at, updated_at, tags, conversation_summary, summary_msg_count) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (c[0], c[1], c[2], c[3], c[3] + timedelta(hours=1), c[4], c[5], c[6]),
        )

    # (conv_id, role, agent, source, content, citations, 距今天数)
    msgs = [
        (1, "user", None, None, "年假制度是什么？一年几天？", None, 12),
        (1, "assistant", "faq", "kb",
         "根据《HR员工手册-假期管理》：正式员工入职满一年后享有 **5 天**带薪年假，之后每满一年增加 1 天，上限 15 天。年假按自然年计算，当年未休完的部分可延续至次年 3 月底前使用。\n\n来源：[1]",
         [{"index": 1, "document_name": "HR员工手册-假期管理.pdf"}], 12),
        (1, "user", None, None, "那我的年假还剩几天？", None, 12),
        (1, "assistant", "function", "tool",
         "你当前的假期余额：**年假 8.0 天**、调休 2.0 天、病假 5.0 天。需要帮你发起请假申请吗？", None, 12),

        (2, "user", None, None, "我的 WiFi 连不上了，一直显示无法获取 IP", None, 8),
        (2, "assistant", "it", "web",
         "先试三步排查：\n\n1. 在设备上「忘记」该网络后重新连接\n2. 路由器断电 30 秒再上电\n3. 命令行执行 `ipconfig /release` 再 `ipconfig /renew` 重新获取 IP\n\n第 3 步能解决大部分情况。如果还不行，拨打 IT 内线 8100 或直接创建工单，我们上门处理。", None, 8),
        (2, "user", None, None, "好了，第③步搞定的，谢谢", None, 8),
        (2, "assistant", "it", "none", "不客气！问题解决就好。后面再出现随时找我，也可以创建工单找人工。", None, 8),

        (3, "user", None, None, "帮我查一下我这个月的报销进度", None, 5),
        (3, "assistant", "function", "tool",
         "你本月有 2 笔报销记录：\n\n1. **256.50 元** 团队建设聚餐 — 审批中\n2. **1500.00 元** 上海出差高铁票 — 已通过，等待打款\n\n打款一般在审批通过后 5 个工作日内到账。", None, 5),

        (4, "user", None, None, "帮我订明天下午的会议室，要能开视频会议的", None, 3),
        (4, "assistant", "function", "tool",
         "已为你预订 **会议室B**（12 人 · 3 楼西 · 投影仪+视频会议），明天 14:00-15:30，用途：产品评审。如需调整时间或换会议室，告诉我即可。", None, 3),

        (5, "user", None, None, "笔记本开机蓝屏，代码 0x0000007B，怎么办", None, 1),
        (5, "assistant", "it", "web",
         "0x0000007B 通常是硬盘模式（AHCI/IDE）不匹配或磁盘故障。建议：\n\n1. 进 BIOS 把 SATA 模式改成 AHCI 后重启\n2. 如果最近加装过内存/硬盘，拔下来重新插紧\n3. 仍蓝屏就别自己拆了——属于硬件故障，直接报修等 IT 上门", None, 1),
        (5, "user", None, None, "报修了，等 IT 上门", None, 1),
        (5, "assistant", "it", "none", "好的，工单已经记录。IT 同学会在 SLA 时限内联系你，保持手机畅通。", None, 1),
    ]
    msg_ids = {}  # (conv_id, 序号) -> message id，反馈表要用
    for i, (cid, role, agent, source, content, cites, days_ago) in enumerate(msgs):
        ts = d(days=days_ago, hours=-(i % 5))
        cur.execute(
            "INSERT INTO messages (conversation_id, role, agent_name, source, content, citations, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (cid, role, agent, source, content, json.dumps(cites, ensure_ascii=False) if cites else None, ts),
        )
        msg_ids[(cid, i)] = cur.lastrowid
    print(f"[3/9] 会话 5 段、消息 {len(msgs)} 条")

    # ---------- 4. 反馈（1=赞 0=踩） ----------
    # msg_ids 的下标是 msgs 列表的全局序号（不是会话内第几条）
    fb = [
        (1, msg_ids[(1, 1)], 1, 1, "faq"),
        (1, msg_ids[(1, 3)], 1, 1, "function"),
        (2, msg_ids[(2, 5)], 1, 1, "it"),
        (2, msg_ids[(2, 7)], 1, 1, "it"),
        (3, msg_ids[(3, 9)], 1, 1, "function"),
        (4, msg_ids[(4, 11)], 1, 6, "function"),
        (5, msg_ids[(5, 13)], 0, 5, "it"),      # 一条踩：回答太技术化
        (5, msg_ids[(5, 15)], 1, 5, "it"),
    ]
    for i, (cid, mid, rating, uid, agent) in enumerate(fb):
        cur.execute(
            "INSERT INTO feedback (conversation_id, message_id, user_id, rating, agent_name, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (cid, mid, uid, rating, agent, d(days=[11, 11, 7, 7, 4, 2, 0, 0][i], hours=i)),
        )
    print(f"[4/9] 反馈 {len(fb)} 条（6 赞 2 踩）")

    # ---------- 5. 工单 + 审批链 + SLA 事件 ----------
    # (id, user_id, title, content, category, status, department, priority, escalated, created_days_ago, sla_hours)
    tickets = [
        (1, 5, "办公电脑无法开机，电源灯不亮", "按下电源键后风扇转一下就停，电源灯闪两下熄灭。", "it", "resolved", "it", "normal", 0, 10, 24),
        (2, 6, "申请开通设计软件正版账号", "市场部做物料需要正版 Photoshop/AI 账号，申请公司采购授权。", "it", "resolved", "it", "normal", 0, 9, 24),
        (3, 7, "新员工公积金账户查询", "上月入职的同事不知道公积金开了哪个账户，帮忙查一下。", "hr", "processing", "hr", "normal", 0, 2, 24),
        (4, 8, "季度报销发票查验不通过", "深圳培训的住宿发票在税局查验一直失败，卡在打款环节。", "finance", "resolved", "finance", "high", 1, 1, 8),
        (5, 5, "申请批量安装开发工具链", "新入职 3 名后端，需要统一预装 JDK17/Docker/IDEA 全家桶。", "it", "pending", "it", "high", 0, 0, 8),
        (6, 7, "机房割接需要停机 8 小时", "核心交换机升级，需要周末凌晨割接，预计中断 8 小时，需提前审批并通知全员。", "it", "pending", "it", "urgent", 0, 0, 4),
        (7, 6, "申请提前转正", "入职 3 个月，业绩达标，申请提前转正。", "hr", "rejected", "hr", "normal", 0, 6, 24),
        (8, 1, "会议室投影仪无信号", "3 楼东会议室 A 投影仪接笔记本无信号，换线也试过。", "admin", "resolved", "admin", "normal", 0, 7, 24),
        (9, 8, "员工报销打款延迟咨询", "10 号提交的报销到现在没到账，帮忙查一下卡在哪。", "finance", "processing", "finance", "normal", 1, 4, 48),
        (10, 5, "VPN 外网访问异常", "在家连 VPN 后无法访问 git 内网仓库，提示连接超时。", "it", "resolved", "it", "high", 0, 5, 8),
        (11, 6, "市场部物料印刷费用超预算", "秋季推广印刷费超出部门预算 3 万，申请特批追加。", "finance", "pending", "finance", "urgent", 0, 0, 4),
        (12, 7, "社保基数调整咨询", "今年社保基数调整后，到手工资变化多少？什么时候生效？", "hr", "resolved", "hr", "normal", 0, 3, 24),
        (13, 1, "显示器申请加装支架", "长期伏案脖子疼，申请给工位配一个显示器升降支架。", "admin", "processing", "admin", "low", 0, 1, 48),
        (14, 8, "申请周末加班调休两天", "上周末连续加班两天，申请本周四、五调休。", "hr", "rejected", "hr", "normal", 0, 8, 24),
    ]
    for tid, uid, title, content, cat, status, dept, pri, esc, days_ago, sla_h in tickets:
        created = d(days=days_ago, hours=-(tid % 6))
        deadline = created + timedelta(hours=sla_h)
        cur.execute(
            "INSERT INTO tickets (id, user_id, title, content, category, status, department, priority, "
            "sla_deadline, escalated, created_at, updated_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (tid, uid, title, content, cat, status, dept, pri, deadline, esc, created, created + timedelta(hours=2)),
        )

    # CSAT 评分：评分人=工单提交人，只挂 resolved 工单；分流刻意对齐 A={zhangwei,wangfang} B={testuser,lina,chenjun}
    # 让 B 组（检索+2条候选）均分和 top-2-box 都略高，演示"实验组更好"的故事线
    csat_rows = [
        (1, 5, 5, "处理很快，一次点亮，工程师还留了检查清单", 8),
        (10, 5, 3, "解决了，但中间来回沟通了三次", 4),
        (12, 7, 5, "政策讲得很清楚，还给了计算示例", 2),
        (8, 1, 5, "投影仪秒修，响应速度满分", 5),
        (2, 6, 4, "", 7),
        (4, 8, 5, "发票查验当天就解决了，效率很高", 1),
    ]
    for tid, uid, score, comment, days_ago in csat_rows:
        cur.execute(
            "INSERT INTO csat_ratings (ticket_id, user_id, score, comment, created_at) VALUES (%s,%s,%s,%s,%s)",
            (tid, uid, score, comment, d(days=days_ago)),
        )

    # 审批链：high=[(1,agent)] urgent=[(1,agent),(2,admin)]
    # (ticket_id, level, approver_role, status, comment, decided_by, 距今天数)
    approvals = [
        (5, 1, "agent", "pending", None, None, 0),
        (6, 1, "agent", "approved", "确认是真紧急，安排周末窗口", 3, 0),
        (6, 2, "admin", "pending", None, None, 0),
        (10, 1, "agent", "approved", "已远程协助修复 VPN 配置", 3, 5),
        (11, 1, "agent", "approved", "金额属实，转管理员终审", 4, 0),
        (11, 2, "admin", "pending", None, None, 0),
        (14, 1, "agent", "rejected", "本周排班已锁定，请走正常调休流程", 3, 8),
    ]
    for tid, level, role, status, comment, decider, days_ago in approvals:
        created = d(days_ago, hours=1)
        decided_at = d(days_ago - 1) if decider else None
        cur.execute(
            "INSERT INTO ticket_approvals (ticket_id, level, approver_role, status, comment, decided_by, decided_at, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
            (tid, level, role, status, comment, decider, decided_at, created),
        )

    # SLA 事件：warning / escalated
    sla_rows = [
        (3, "warning", None, None, "SLA 剩余不足 25%，请及时处理", 1),
        (4, "warning", None, None, "SLA 剩余不足 25%，请及时处理", 0),
        (9, "escalated", "low", "normal", "SLA超时，优先级 low → normal", 3),
        (13, "warning", None, None, "SLA 剩余不足 25%，请及时处理", 0),
    ]
    for tid, etype, frm, to, note, days_ago in sla_rows:
        cur.execute(
            "INSERT INTO sla_events (ticket_id, event_type, from_priority, to_priority, note, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s)",
            (tid, etype, frm, to, note, d(days=days_ago, hours=2)),
        )
    print(f"[5/9] 工单 {len(tickets)} 张（含 2 张待审、2 张驳回）、审批链 {len(approvals)} 级、SLA 事件 {len(sla_rows)} 条、CSAT 评分 {len(csat_rows)} 条")

    # ---------- 6. 资产 + 流水 ----------
    # (id, asset_no, category, model, status, holder, 创建距今, purchase_date, price, warranty_end, location, note, [流水])
    # 流水元素: (action, user_id, operator_id, note, 距今天数)
    assets = [
        (1, "NB-2026-001", "laptop", "ThinkPad T14", "in_use", 5, 30,
         "2025-03-12", 6499.00, "2028-03-12", "3楼研发区-A12", "",
         [("create", 2, 2, "入库", 30), ("borrow", 5, 5, "", 20)]),
        (2, "NB-2026-002", "laptop", "ThinkPad T14", "in_use", 1, 30,
         "2025-03-12", 6499.00, "2028-03-12", "3楼研发区-B07", "",
         [("create", 2, 2, "入库", 30), ("borrow", 1, 1, "", 25), ("return", 1, 1, "", 22), ("borrow", 1, 1, "", 22)]),
        (3, "NB-2026-003", "laptop", "MacBook Air M3", "available", None, 15,
         "2025-06-20", 8999.00, "2028-06-20", "IT库房-柜1", "设计岗专用",
         [("create", 2, 2, "入库", 15)]),
        (4, "NB-2026-004", "laptop", "ThinkPad X1", "available", None, 15,
         "2024-11-05", 7299.00, "2027-11-05", "IT库房-柜1", "",
         [("create", 2, 2, "入库", 15)]),
        (5, "NB-2026-005", "laptop", "Dell Latitude 5430", "retired", None, 40,
         "2022-04-18", 5599.00, "2025-04-18", "IT库房-报废区", "2019级校招标配机",
         [("create", 2, 2, "入库", 40), ("borrow", 8, 8, "", 35), ("return", 8, 8, "", 30), ("scrap", 8, 2, "屏幕碎裂", 5)]),
        (6, "MN-2026-001", "monitor", "Dell 27寸 P2723QE", "in_use", 6, 25,
         "2025-01-08", 2399.00, "2028-01-08", "3楼市场区-C03", "",
         [("create", 2, 2, "入库", 25), ("borrow", 6, 6, "", 10)]),
        (7, "MN-2026-002", "monitor", "Dell 24寸 P2422H", "available", None, 15,
         "2024-12-01", 1299.00, "2027-12-01", "IT库房-柜2", "",
         [("create", 2, 2, "入库", 15)]),
        (8, "MN-2026-003", "monitor", "LG 32寸 4K 32UN880", "available", None, 8,
         "2026-08-22", 3699.00, "2029-08-22", "IT库房-柜2", "新品，支持 Type-C 90W 反向供电",
         [("create", 2, 2, "入库", 8)]),
        (9, "PH-2026-001", "phone", "iPhone 15", "in_use", 7, 20,
         "2025-09-15", 5999.00, "2027-09-15", "", "HR 外出招聘用机",
         [("create", 2, 2, "入库", 20), ("borrow", 7, 7, "", 12)]),
        (10, "PH-2026-002", "phone", "Xiaomi 14", "available", None, 8,
         "2026-07-30", 4299.00, "2028-07-30", "IT库房-柜3", "",
         [("create", 2, 2, "入库", 8)]),
        (11, "BD-2026-001", "badge", "员工工牌", "available", None, 30,
         None, 20.00, None, "IT库房-抽屉1", "空白待发",
         [("create", 2, 2, "入职办理", 30)]),
        (12, "BD-2026-002", "badge", "员工工牌", "retired", None, 30,
         None, 20.00, None, "IT库房-报废区", "chenjun 离职回收",
         [("create", 2, 2, "入职办理", 30), ("scrap", 8, 2, "员工离职，工牌销毁", 9)]),
    ]
    for aid, no, cat, model, status, holder, cdays, pdate, price, wend, loc, note, logs in assets:
        cur.execute(
            "INSERT INTO assets (id, asset_no, category, model, status, holder_user_id, created_at, "
            "purchase_date, price, warranty_end, location, note) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (aid, no, cat, model, status, holder, d(days=cdays), pdate, price, wend, loc, note),
        )
        for action, uid, oid, lnote, ldays in logs:
            cur.execute(
                "INSERT INTO asset_logs (asset_id, user_id, operator_id, action, note, created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (aid, uid, oid, action, lnote, d(days=ldays, hours=1)),
            )
    print(f"[6/9] 资产 {len(assets)} 台（5 在库 / 5 领用 / 2 报废）+ 台账字段 + 配套流水")

    # ---------- 7. 工具表（Function Calling 的数据源） ----------
    balances = [(1, 8.0, 5.0, 2.0), (2, 6.5, 5.0, 1.0), (3, 10.0, 5.0, 3.0), (4, 9.0, 5.0, 2.0),
                (5, 12.0, 5.0, 4.0), (6, 7.5, 5.0, 1.0), (7, 11.0, 5.0, 2.5), (8, 5.0, 5.0, 0.0)]
    for uid, a, s, c in balances:
        cur.execute("INSERT INTO leave_balances (user_id, annual_leave, sick_leave, comp_leave, updated_at) VALUES (%s,%s,%s,%s,%s)",
                    (uid, a, s, c, d(days=5)))

    leave_reqs = [
        (1, "annual", d(days=5).date(), d(days=3).date(), 2.0, "回家探亲", 2, "approved"),
        (5, "sick", d(days=4).date(), d(days=4).date(), 1.0, "急性肠胃炎，医院开了病假条", 2, "approved"),
        (6, "annual", (NOW + timedelta(days=5)).date(), (NOW + timedelta(days=7)).date(), 3.0, "年假出行，提前规划", None, "pending"),
        (7, "comp", d(days=2).date(), d(days=2).date(), 0.5, "上周末加班换半天调休", 2, "rejected"),
    ]
    for uid, lt, sdate, edate, days_, reason, approver, status in leave_reqs:
        cur.execute("INSERT INTO leave_requests (user_id, leave_type, start_date, end_date, days, reason, approver_id, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (uid, lt, sdate, edate, days_, reason, approver, status, d(days=6)))

    reimburse = [
        (1, 256.50, "meal", "团队建设聚餐", "pending", 3),
        (1, 1500.00, "travel", "上海出差高铁票", "approved", 8),
        (5, 8990.00, "equipment", "开发用 4K 外接显示器", "paid", 20),
        (6, 320.00, "meal", "客户招待午餐", "pending", 1),
        (7, 156.00, "taxi", "加班打车费（超出报销范围）", "rejected", 6),
        (8, 4200.00, "travel", "深圳财务培训差旅（机票+酒店）", "approved", 10),
    ]
    for uid, amt, cat, desc, status, days_ago in reimburse:
        cur.execute("INSERT INTO reimbursements (user_id, amount, category, description, status, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (uid, amt, cat, desc, status, d(days=days_ago)))

    rooms = [(1, "会议室A", 8, "3楼东", "投影仪+白板"),
             (2, "会议室B", 12, "3楼西", "投影仪+视频会议"),
             (3, "会议室C", 6, "5楼北", "电视屏+白板"),
             (4, "会议室D", 20, "5楼南", "视频会议+电话会议")]
    for r in rooms:
        cur.execute("INSERT INTO meeting_rooms (id, name, capacity, location, equipment) VALUES (%s,%s,%s,%s,%s)", r)

    bookings = [
        (2, 6, (NOW + timedelta(days=1)).date(), "14:00:00", "15:30:00", "产品评审", "confirmed"),
        (1, 5, (NOW + timedelta(days=2)).date(), "10:00:00", "11:00:00", "迭代规划", "confirmed"),
        (3, 7, (NOW + timedelta(days=3)).date(), "15:00:00", "16:00:00", "社保政策宣讲", "pending"),
        (4, 1, (NOW + timedelta(days=4)).date(), "09:30:00", "10:00:00", "周会", "confirmed"),
    ]
    for room, uid, bdate, st, et, purpose, status in bookings:
        cur.execute("INSERT INTO room_bookings (room_id, user_id, book_date, start_time, end_time, purpose, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                    (room, uid, bdate, st, et, purpose, status, d(days=2)))

    it_assets = [(5, "laptop", "ThinkPad T14", "IT-2024-001", "normal", None),
                 (6, "monitor", "Dell 27寸", "IT-2024-101", "normal", None),
                 (7, "phone", "iPhone 15", "IT-2025-021", "normal", None),
                 (8, "laptop", "MacBook Air", "IT-2025-033", "repairing", None),
                 (1, "laptop", "ThinkPad X1", "IT-2024-002", "normal", None)]
    for row in it_assets:
        cur.execute("INSERT INTO it_assets (user_id, asset_type, asset_name, asset_tag, status, purchase_date) VALUES (%s,%s,%s,%s,%s,%s)",
                    (row[0], row[1], row[2], row[3], row[4], d(days=300).date()))

    cur.execute("INSERT INTO ab_experiments (id, name, variant_a, variant_b, is_active, created_at) VALUES (1,'检索广度对比','默认检索','检索+2条候选',1,%s)", (d(days=14),))
    # 分流映射：A={dxr,kefu01,zhangwei,wangfang} B={testuser,kefu02,lina,chenjun}
    # 对齐已评分工单的提交人——A 组 3 条评分、B 组 3 条，B 组分数略高（演示实验组胜出）
    variant_by_uid = {1: "B", 2: "A", 3: "A", 4: "B", 5: "A", 6: "B", 7: "A", 8: "B"}
    for uid in range(1, 9):
        cur.execute("INSERT INTO ab_assignments (experiment_id, user_id, variant, created_at) VALUES (1,%s,%s,%s)",
                    (uid, variant_by_uid[uid], d(days=13)))

    # 转接：挂在在办工单上（resolved/rejected 的单后端会拒绝转接），三种状态各留样例
    transfers = [
        (5, 5, 3, "批量安装工具链涉及服务器权限，请 IT 坐席接手", "waiting", 2),
        (11, 6, 2, "超预算特批需管理员复核，转 dxr", "waiting", 1),
        (3, 7, 4, "公积金问题属 HR 咨询，请 kefu02 解答", "declined", 5),
        (9, 8, 3, "打款延迟需财务与 IT 联查，转 kefu01", "connected", 8),
    ]
    for tid, uid, aid, reason, status, days_ago in transfers:
        cur.execute("INSERT INTO transfer_sessions (ticket_id, user_id, agent_id, reason, status, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (tid, uid, aid, reason, status, d(days=days_ago)))
    print("[7/9] 工具表：假期余额 8 / 请假 4 / 报销 6 / 会议室 4+预订 4 / 设备 5 / A-B 实验 / 转接 4")

    # ---------- 8. 审计日志 ----------
    audits = [
        (1, "login_success", "用户登录成功", "127.0.0.1", 0),
        (2, "login_success", "管理员登录成功", "127.0.0.1", 0),
        (2, "sensitive_blocked", "命中敏感词「辞职」: 我想辞职不干了", None, 6),
        (5, "login_success", "用户登录成功", "192.168.1.56", 1),
        (3, "ticket_approved", "ticket#6 level1: 确认是真紧急，安排周末窗口", None, 0),
        (3, "ticket_rejected", "ticket#14 level1: 本周排班已锁定，请走正常调休流程", None, 8),
        (4, "ticket_approved", "ticket#11 level1: 金额属实，转管理员终审", None, 0),
        (2, "asset_scrap", "asset#5 NB-2026-005 报废: 屏幕碎裂", None, 5),
        (2, "asset_scrap", "asset#12 BD-2026-002 报废: 员工离职，工牌销毁", None, 9),
        (2, "kb_upload", "上传文档 HR员工手册-假期管理.pdf v1", None, 14),
        (6, "login_success", "用户登录成功", "10.0.0.32", 2),
        (1, "ticket_created", "创建工单 ticket#13 显示器申请加装支架", None, 1),
        (7, "sensitive_blocked", "命中敏感词「机密」: 把公司机密发我一份", None, 4),
        (2, "role_update", "更新用户角色: kefu01 → agent", None, 30),
    ]
    for uid, action, detail, ip, days_ago in audits:
        cur.execute("INSERT INTO audit_logs (user_id, action, detail, ip, created_at) VALUES (%s,%s,%s,%s,%s)",
                    (uid, action, detail, ip, d(days=days_ago, hours=-(uid % 8))))
    print(f"[8/9] 审计日志 {len(audits)} 条")

    # ---------- 9. request_traces（最近 7 天，喂监控/排查页） ----------
    agents_pool = ["faq", "faq", "faq", "hr", "it", "function", "chat"]
    intents = ["faq", "hr", "finance", "smalltalk", "tool", "faq"]
    sents = ["positive", "neutral", "neutral", "neutral", "negative"]
    chat_paths = ["/chat", "/conversations", "/tickets", "/assets", "/auth/me"]
    for i in range(80):
        is_chat = random.random() < 0.55
        path = "/chat" if is_chat else random.choice(chat_paths[1:])
        method = "POST" if is_chat else random.choice(["GET", "GET", "GET", "POST"])
        fail = is_chat and random.random() < 0.08
        status = 500 if fail else (200 if is_chat else random.choice([200, 200, 200, 201]))
        agent = random.choice(agents_pool) if is_chat else None
        cur.execute(
            "INSERT INTO request_traces (trace_id, user_id, method, path, status_code, total_time, "
            "input_tokens, output_tokens, agent_name, sentiment, intent, error_msg, created_at) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                uuid.uuid4().hex[:12],
                random.randint(1, 8),
                method, path, status,
                round(random.uniform(3.5, 9.0) if fail else random.uniform(0.6, 4.2), 3),
                random.randint(300, 1200) if is_chat else 0,
                random.randint(150, 600) if is_chat and not fail else 0,
                agent,
                random.choice(sents) if is_chat else None,
                random.choice(intents) if is_chat else None,
                "LLM 调用超时，已降级为兜底回复" if fail else None,
                d(days=random.randint(0, 7), hours=random.randint(0, 23), minutes=random.randint(0, 59)),
            ),
        )
    print("[9/9] request_traces 80 条（含 8% 失败样本）")

    # ---------- 10. RAG 评测金标集（期望文档=documents.filename，运行时解析 is_latest） ----------
    # (id, question, 主期望文档, category)；可接受文档（grade=1）在 eval_case_docs_extra 里补
    eval_cases = [
        # 原 4 篇 16 条（行号已对照文档核验；#16 是多标签陷阱对的主文档侧）
        (1,  "年假满1年和满3年分别有多少天", "HR员工手册.md", "hr"),
        (2,  "年假最晚什么时候休完，跨年怎么处理", "HR员工手册.md", "hr"),
        (3,  "病假超过几天需要提供二级医院证明", "HR员工手册.md", "hr"),
        (4,  "周末加班按几倍工资计算或者可以调休", "HR员工手册.md", "hr"),
        (5,  "离职时未休年假按什么倍数折算工资", "HR员工手册.md", "hr"),
        (6,  "WiFi连不上提示无法获取IP地址怎么办", "IT服务指南.md", "it"),
        (7,  "密码至少要多少位、多久必须更换一次", "IT服务指南.md", "it"),
        (8,  "密码连续输错几次账号会被锁定多久", "IT服务指南.md", "it"),
        (9,  "全公司断网这类紧急故障的响应和解决时限是多少", "IT服务指南.md", "it"),
        (10, "VPN连不上第一步应该先检查什么", "IT服务指南.md", "it"),
        (11, "会议室最多能提前几天预订、单次最长几小时", "行政管理规范.md", "admin"),
        (12, "会议室预订后多久没有签到会被系统自动释放", "行政管理规范.md", "admin"),
        (13, "报销单和差旅费分别需要在多少天内提交", "财务报销制度.md", "finance"),
        (14, "业务招待费标准是多少，超过单次上限如何审批", "财务报销制度.md", "finance"),
        (15, "一线普通员工出差住宿标准每晚多少元", "财务报销制度.md", "finance"),
        (16, "培训费每人每年的预算是多少", "培训与发展管理办法.md", "ambiguous"),
        # HR 新文档 14 条
        (17, "P6到P7中级岗位的招聘审批链和审批时限", "招聘与录用制度.md", "hr"),
        (18, "到岗时间少于多少个工作日的招聘需求算加急", "招聘与录用制度.md", "hr"),
        (19, "新员工培训结业考试多少分算合格", "培训与发展管理办法.md", "hr"),
        (20, "新员工集中入职培训一共培训几天", "培训与发展管理办法.md", "hr"),
        (21, "弹性班次的核心工作时间段是几点到几点", "考勤与请休假细则.md", "hr"),
        (22, "请假的最小申请单位是多少天", "考勤与请休假细则.md", "hr"),
        (23, "餐补和交通补贴分别是每月多少元", "薪酬与调薪制度.md", "hr"),
        (24, "入职不满6个月的员工年度考核结果最高是什么", "绩效考核办法.md", "hr"),
        (25, "养老保险个人和公司各缴纳百分之多少", "社保与福利制度.md", "hr"),
        (26, "季度之星奖励是多少钱", "员工关系与奖惩制度.md", "hr"),
        (27, "违纪行为发生后几个月内未被发现不再追究", "员工关系与奖惩制度.md", "hr"),
        (28, "入职材料不齐可以在多少个工作日内补齐", "入职与离职指引.md", "hr"),
        (29, "资格津贴叠加部分合计每月不超过多少元", "职称与资格津贴管理办法.md", "hr"),
        (30, "A类高级稀缺资格的津贴区间是每月多少", "职称与资格津贴管理办法.md", "hr"),
        # IT 新文档 5 条
        (31, "离职员工的账号在什么时间点停用", "信息安全管理制度.md", "it"),
        (32, "办公网络月度可用率要求达到多少", "网络与系统运维规范.md", "it"),
        (33, "数据备份的3-2-1原则具体指什么", "数据备份与恢复管理办法.md", "it"),
        (34, "SmartFlow生产库最多允许丢失多长时间的数据", "数据备份与恢复管理办法.md", "it"),
        (35, "连续多少天未登录的软件席位会被回收", "软件使用与正版化制度.md", "it"),
        # 行政 新文档 5 条
        (36, "每人每天最多可以预订几个会议室时段", "会议室预订与使用规范.md", "admin"),
        (37, "固定资产的认定标准是什么", "办公用品与资产管理制度.md", "admin"),
        (38, "紧急用车事后需要在多少小时内补单", "公务用车与差旅行政规范.md", "admin"),
        (39, "连续驾驶多久必须停车休息", "公务用车与差旅行政规范.md", "admin"),
        (40, "5人以上团访需要提前几天预约", "来访接待与安全管理制度.md", "admin"),
        # 财务 新文档 10 条
        (41, "涉及出境的出差需要提前多少个工作日审批", "差旅费报销实施细则.md", "finance"),
        (42, "部门季度预算的可调节幅度不超过多少", "预算管理制度.md", "finance"),
        (43, "20000元以上的付款需要哪些角色审批", "资金支付与审批权限办法.md", "finance"),
        (44, "对公付款超过多少万元出纳需要电话复核", "资金支付与审批权限办法.md", "finance"),
        (45, "取得专用发票后多少个工作日内交给财务", "发票与税务管理办法.md", "finance"),
        (46, "固定资产残值率按原值的多少计提", "固定资产折旧与盘点制度.md", "finance"),
        (47, "报销款每周哪几天打款", "财务报销常见问题FAQ.md", "finance"),
        (48, "跨市出差伙食补贴每天多少元", "费用报销系统操作手册.md", "finance"),
        (49, "普通员工市内交通费每天上限多少元", "费用报销系统操作手册.md", "finance"),
        (50, "合住奖励按节省部分的百分之多少计算", "费用报销系统操作手册.md", "finance"),
        # ⑪ 扩容 10 条：补齐 4 篇未覆盖文档（助手指南/合规手册/行为准则/组织架构）各 2 条
        (51, "SmartFlow助手的Web端地址是什么、访问需要什么前置条件", "SmartFlow助手使用指南.md", "it"),
        (52, "能不能通过SmartFlow助手查询自己的工资和绩效", "SmartFlow助手使用指南.md", "it"),
        (53, "触碰公司合规红线会面临什么处理", "合规与商业道德手册.md", "compliance"),
        (54, "收到举报后公司须在多少个工作日内立项调查", "合规与商业道德手册.md", "compliance"),
        (55, "对违规处理结果有异议可以在多少个工作日内提出书面申诉", "员工行为准则.md", "hr"),
        (56, "简历学历造假经核实后如何处理", "员工行为准则.md", "hr"),
        (57, "星辰科技财务部的分机号是多少", "组织架构与部门职责.md", "admin"),
        (58, "员工入职手续由哪个部门主办", "组织架构与部门职责.md", "admin"),
        (59, "收到礼品价值多少元以上须上交行政部登记", "员工行为准则.md", "compliance"),
        (60, "特权账号审批需要谁批准", "组织架构与部门职责.md", "it"),
    ]
    # 可接受文档（grade=1）：一条用例除主文档外还期望的其他真实来源
    # case16 多标签陷阱：培训预算 5000 在专项办法（主）和 HR 手册（概述）都真实出现，
    #   单标签口径下检索器排手册第一会被误判 miss——多标签 + NDCG grade 区分正是为此
    # ⑪ 再升级 9 条现有用例 + 新增 59/60 的可接受侧，共 12 条多标签（消除单标签误判）
    eval_case_docs_extra = [
        (16, "HR员工手册.md", 1),
        (1, "考勤与请休假细则.md", 1), (3, "考勤与请休假细则.md", 1), (4, "考勤与请休假细则.md", 1),
        (7, "信息安全管理制度.md", 1), (8, "信息安全管理制度.md", 1),
        (11, "会议室预订与使用规范.md", 1), (12, "会议室预订与使用规范.md", 1),
        (14, "合规与商业道德手册.md", 1), (15, "差旅费报销实施细则.md", 1),
        (59, "合规与商业道德手册.md", 1), (60, "SmartFlow助手使用指南.md", 1),
    ]
    for cid, q, doc, cat in eval_cases:
        cur.execute(
            "INSERT INTO eval_cases (id, question, expect_doc, category) VALUES (%s,%s,%s,%s)",
            (cid, q, doc, cat),
        )
        cur.execute(
            "INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s,%s,2)",
            (cid, doc),
        )
    for cid, doc, grade in eval_case_docs_extra:
        cur.execute(
            "INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s,%s,%s)",
            (cid, doc, grade),
        )
    # ⑫ 扩容 63 条：清单复用 insert_eval_cases_v3.py（单一数据源，避免两处维护）
    # 负例 15（expect_doc=NULL, is_answerable=0）+ 补薄正例 30 + 硬负例 10 + 口语化 8
    from insert_eval_cases_v3 import NEGATIVES, POSITIVE_CASES
    for q in NEGATIVES:
        cur.execute(
            """INSERT INTO eval_cases (id, question, expect_doc, category, is_answerable)
               VALUES (NULL, %s, NULL, 'unanswerable', 0)""",
            (q,),
        )
        neg_id = cur.lastrowid
        # 负例不插 eval_case_docs（无期望文档）
    for q, doc, cat, extra in POSITIVE_CASES:
        cur.execute(
            """INSERT INTO eval_cases (id, question, expect_doc, category, is_answerable)
               VALUES (NULL, %s, %s, %s, 1)""",
            (q, doc, cat),
        )
        case_id = cur.lastrowid
        cur.execute(
            "INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s,%s,2)",
            (case_id, doc),
        )
        for fn, g in extra:
            cur.execute(
                "INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s,%s,%s)",
                (case_id, fn, g),
            )
    total_cases = len(eval_cases) + len(NEGATIVES) + len(POSITIVE_CASES)
    print(f"[10/10] 金标用例 {total_cases} 条（32/32 文档全覆盖，多标签 22 条，负例 15 条）")

    db.commit()
    print("\n全部完成，一次事务提交。")
except Exception:
    db.rollback()
    raise
finally:
    cur.close()
    db.close()

# Redis 限流/配额计数顺手清掉（用户 id 1/2 复用了，不清可能一登录就 429）
try:
    import redis
    r = redis.Redis(host=os.getenv("REDIS_HOST", "localhost"), port=int(os.getenv("REDIS_PORT", 6379)), decode_responses=True)
    n = 0
    for key in r.scan_iter("rate:*"):
        r.delete(key); n += 1
    for key in r.scan_iter("quota:*"):
        r.delete(key); n += 1
    print(f"Redis 限流计数清了 {n} 个 key")
except Exception as e:
    print(f"Redis 清理跳过（{e}）")
