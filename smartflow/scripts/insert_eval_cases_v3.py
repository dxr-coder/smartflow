# -*- coding: utf-8 -*-
"""
⑫ 金标扩容入库（分批追加，幂等）
数据流：按批定义列表插入 eval_cases（负例 expect_doc=NULL, is_answerable=0）
       → 多标签用例同步插 eval_case_docs
幂等：按 question 去重，已存在则跳过；重复执行安全
批定义：
  批1 NEGATIVES  —— 15 条不可回答负例（已逐条 grep 知识库核验无答案）
  批2/3/4 后续追加（补薄正例 / 硬负例 / 口语化）
用法：python insert_eval_cases_v3.py [batch]（batch: negatives|all，默认 negatives）
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.database import get_db

# ---------- 批1：不可回答负例（category 固定 unanswerable） ----------
NEGATIVES = [
    "公司年会的预算是多少？",
    "公司有股权或期权激励计划吗？",
    "公司有海外派驻或外派工作机会吗？",
    "我的住房公积金账户目前余额是多少？",
    "公司食堂今天供应什么菜？",
    "明天的天气怎么样，适合户外团建吗？",
    "公司去年的营业收入是多少？",
    "公司计划上市吗？",
    "公司允许带宠物来上班吗？",
    "公司圣诞节放假吗？",
    "公司有员工健身房吗，开放时间是几点到几点？",
    "下个月的员工生日会是什么主题？",
    "帮我查一下我的工资卡余额还有多少？",
    "公司的股票现在多少钱一股？",
    "公司有通勤班车吗，都走哪些线路？",
]

# 批2 补薄正例：(question, expect_doc, category, extra_docs[(filename, grade)]) 元组列表
# 每篇薄文档 +5 条，覆盖不同章节；行号依据见 docs/knowledge/ 正文（2026-10-19 逐条核对）
POSITIVE_CASES = [
    # ---- 预算管理制度（finance） ----
    ("各部门需要在什么时候前提交下一年度预算初稿？", "预算管理制度.md", "finance", []),
    ("培训费按什么标准纳入部门人力发展预算？", "预算管理制度.md", "finance", []),
    ("预算执行进度超过时间进度多少会触发黄色预警？", "预算管理制度.md", "finance", []),
    ("部门超年度预算10%-30%属于哪种超支情形，需要谁审批？", "预算管理制度.md", "finance", []),
    ("年末没用完的差旅费预算可以结转下一年吗？", "预算管理制度.md", "finance", []),
    # ---- 资金支付与审批权限办法（finance） ----
    ("出差备用金跨省最多可以借多少？", "资金支付与审批权限办法.md", "finance", []),
    ("借款逾期多少天没冲账会冻结借款权限？", "资金支付与审批权限办法.md", "finance", []),
    ("紧急付款每月每个部门限用几次？", "资金支付与审批权限办法.md", "finance", []),
    ("员工报销款每周哪几天付款？", "资金支付与审批权限办法.md", "finance", []),
    ("网银密码多久强制更换一次？", "资金支付与审批权限办法.md", "finance", []),
    # ---- 固定资产折旧与盘点制度（finance） ----
    ("笔记本电脑按几年折旧？", "固定资产折旧与盘点制度.md", "finance", []),
    ("固定资产确认的单位价值标准是多少？", "固定资产折旧与盘点制度.md", "finance", []),
    ("全面资产盘点每年几次、什么时间？", "固定资产折旧与盘点制度.md", "finance", []),
    ("离职时遗失公司资产按什么标准赔偿？", "固定资产折旧与盘点制度.md", "finance", []),
    ("办公装修支出单项多少万以上按长期待摊费用摊销？", "固定资产折旧与盘点制度.md", "finance", []),
    # ---- 发票与税务管理办法（finance） ----
    ("发票抬头必须写什么公司全称？", "发票与税务管理办法.md", "finance", []),
    ("收据可以报销吗，有什么限额？", "发票与税务管理办法.md", "finance", []),
    ("餐饮服务的进项税可以抵扣吗？", "发票与税务管理办法.md", "finance", []),
    ("电子发票报销必须提交什么格式？", "发票与税务管理办法.md", "finance", []),
    ("住房租金专项附加扣除每月多少元？", "发票与税务管理办法.md", "finance", []),
    # ---- 数据备份与恢复管理办法（it） ----
    ("RTO和RPO分别指什么？", "数据备份与恢复管理办法.md", "it", []),
    ("误删了共享文件多长时间内能自己找回？", "数据备份与恢复管理办法.md", "it", []),
    ("恢复演练多久至少组织一次？", "数据备份与恢复管理办法.md", "it", []),
    ("企业网盘算不算完整备份？", "数据备份与恢复管理办法.md", "it", []),
    ("发现服务器中了勒索病毒第一步做什么？", "数据备份与恢复管理办法.md", "it", []),
    # ---- 网络与系统运维规范（it） ----
    ("公司WiFi同一账号最多几台设备同时在线？", "网络与系统运维规范.md", "it", []),
    ("常规网络变更窗口是周几几点？", "网络与系统运维规范.md", "it", []),
    ("IT服务台的分机号是多少，工作时间？", "网络与系统运维规范.md", "it", []),
    ("访客WiFi叫什么，有什么限制？", "网络与系统运维规范.md", "it", []),
    ("存储可用空间低于多少会触发告警？", "网络与系统运维规范.md", "it", []),
    # ---- 批3 硬负例（multi-label）：主文档权威、配对文档内容重叠但非操作依据 ----
    # ① 差旅住宿：细则 L93-104 限额表 vs 财务制度 L52-61 同表（上位制度）
    ("普通员工去深圳出差住宿标准是多少每晚？", "差旅费报销实施细则.md", "finance",
     [("财务报销制度.md", 1)]),
    ("出差当天往返，最晚几点前能到家就不安排住宿？", "差旅费报销实施细则.md", "finance",
     [("财务报销制度.md", 1)]),
    # ② 请假权限：细则 L144-153 vs 手册 L57-61 同口径（细则声明基础口径以手册为准）
    ("请假3天以上需要谁审批？", "考勤与请休假细则.md", "hr",
     [("HR员工手册.md", 1)]),
    ("年假连续休3天以上要提前几个工作日申请？", "考勤与请休假细则.md", "hr",
     [("HR员工手册.md", 1)]),
    # ③ 办公采购：办公用品制度 L54 vs 财务制度 L82 同句式 500 元口径
    ("部门专属的特殊办公用品什么情况下可以自行购买？", "办公用品与资产管理制度.md", "admin",
     [("财务报销制度.md", 1)]),
    ("自行购买特殊办公用品的报销限额是多少元？", "办公用品与资产管理制度.md", "admin",
     [("财务报销制度.md", 1)]),
    # ④ 备份运维：备份办法 L74 vs 运维规范 L153 同为中级告警 2 小时响应
    ("备份任务失败后的告警响应时限是多少？", "数据备份与恢复管理办法.md", "it",
     [("网络与系统运维规范.md", 1)]),
    ("核心系统恢复目标（RTO）未达成时按什么级别处理？", "数据备份与恢复管理办法.md", "it",
     [("网络与系统运维规范.md", 1)]),
    # ⑤ 会议室取消：会议室规范 L89/L170 vs 行政管理规范 L34 同规则
    ("预订了会议室临时取消，算违约吗？", "会议室预订与使用规范.md", "admin",
     [("行政管理规范.md", 1)]),
    ("连续几次预订未使用会被暂停预订权限，暂停多久？", "会议室预订与使用规范.md", "admin",
     [("行政管理规范.md", 1)]),
    # ---- 批4 口语化（colloquial）：高频正例的口语改写，专测 query rewriter ----
    ("那个出差住酒店最多报多少来着？", "差旅费报销实施细则.md", "colloquial", []),
    ("我年假还剩几天没休，能拖到明年不？", "考勤与请休假细则.md", "colloquial", []),
    ("手机连不上公司WiFi咋整啊？", "IT服务指南.md", "colloquial", []),
    ("报销单交上去多久能到账啊？", "财务报销制度.md", "colloquial", []),
    ("电脑坏了是自己拿去修还是找谁？", "IT服务指南.md", "colloquial", []),
    ("试用期那会儿算工龄不，年假有份吗？", "HR员工手册.md", "colloquial", []),
    ("帮我订明天下午的会议室，6个人那种", "会议室预订与使用规范.md", "colloquial", []),
    ("月底了发票还没来得及开，还能报上吗？", "财务报销制度.md", "colloquial", []),
]


def insert_negative(db, question):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM eval_cases WHERE question=%s", (question,))
        if cur.fetchone():
            return None  # 幂等：已存在
        cur.execute("""INSERT INTO eval_cases (question, expect_doc, category, is_answerable)
                       VALUES (%s, NULL, 'unanswerable', 0)""", (question,))
        return cur.lastrowid


def insert_positive(db, question, expect_doc, category, extra_docs=()):
    with db.cursor() as cur:
        cur.execute("SELECT id FROM eval_cases WHERE question=%s", (question,))
        if cur.fetchone():
            return None
        cur.execute("""INSERT INTO eval_cases (question, expect_doc, category, is_answerable)
                       VALUES (%s, %s, %s, 1)""", (question, expect_doc, category))
        case_id = cur.lastrowid
        cur.execute("INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s, %s, 2)",
                    (case_id, expect_doc))
        for fn, g in extra_docs:
            cur.execute("INSERT INTO eval_case_docs (case_id, doc_filename, grade) VALUES (%s, %s, %s)",
                        (case_id, fn, g))
        return case_id


if __name__ == "__main__":
    # seed_demo.py 可 import 本模块的 NEGATIVES/POSITIVE_CASES 复用清单（import 时不执行入库）
    which = sys.argv[1] if len(sys.argv) > 1 else "negatives"
    db = get_db()
    try:
        added_neg = added_pos = skipped = 0
        if which in ("negatives", "all"):
            for q in NEGATIVES:
                cid = insert_negative(db, q)
                if cid:
                    added_neg += 1
                else:
                    skipped += 1
            db.commit()
        if which == "all":
            for q, doc, cat, extra in POSITIVE_CASES:
                cid = insert_positive(db, q, doc, cat, extra)
                if cid:
                    added_pos += 1
                else:
                    skipped += 1
            db.commit()

        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) AS c FROM eval_cases WHERE is_active=1")
            total = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(*) AS c FROM eval_cases WHERE is_answerable=0")
            n_neg = cur.fetchone()["c"]
        print(f"插入完成：负例 +{added_neg} | 正例 +{added_pos} | 跳过(已存在) {skipped}")
        print(f"当前启用用例 {total} 条（其中负例 {n_neg} 条）")
    finally:
        db.close()
