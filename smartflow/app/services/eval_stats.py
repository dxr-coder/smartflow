"""
评测统计工具

功能：A/B 两轮评测的配对显著性检验（读时计算，不落库）
数据流：compare_runs 传入两轮逐用例指标 → 二值指标走 exact McNemar、连续指标走 paired bootstrap
        → 返回 {delta, ci_low, ci_high, p, significant}，纯 stdlib 无三方依赖
设计要点：
  - McNemar 只看不一致对（a对b错 / a错b对），小样本下用 exact 二项式而非卡方近似
  - bootstrap 固定 seed=42 保证同输入同结果（评测可复现纪律）
  - CI 用 percentile 法；显著判定 = 95% CI 不含 0
"""
import math
import random


def mcnemar_exact(hits_a: list, hits_b: list) -> dict:
    """
    exact McNemar 检验（二值配对结果，如 Hit@1 的逐用例 0/1）
    b = a对b错的用例数，c = a错b对的用例数；H0 下 b~Binomial(b+c, 0.5)
    双侧 p = min(1, 2 * P(X <= min(b,c)))
    """
    if len(hits_a) != len(hits_b):
        raise ValueError("配对长度必须一致")
    b = c = 0
    for x, y in zip(hits_a, hits_b):
        if x == 1 and y == 0:
            b += 1
        elif x == 0 and y == 1:
            c += 1
    n_disc = b + c
    delta = (sum(hits_a) - sum(hits_b)) / len(hits_a) if hits_a else 0.0
    if n_disc == 0:
        # 完全一致：没有不一致对，p=1 不显著
        return {"delta": round(delta, 4), "ci_low": None, "ci_high": None,
                "p": 1.0, "significant": False, "test": "mcnemar_exact",
                "discordant": {"a_only": 0, "b_only": 0}}
    k = min(b, c)
    tail = sum(math.comb(n_disc, i) for i in range(k + 1)) * (0.5 ** n_disc)
    p = min(1.0, 2 * tail)
    return {"delta": round(delta, 4), "ci_low": None, "ci_high": None,
            "p": round(p, 4), "significant": p < 0.05, "test": "mcnemar_exact",
            "discordant": {"a_only": b, "b_only": c}}


def paired_bootstrap(vals_a: list, vals_b: list, n_rounds: int = 1000, seed: int = 42) -> dict:
    """
    配对 bootstrap（连续指标：分数化 Recall@5 / MRR / NDCG@5 / faithfulness）
    对用例下标有放回重采样，算 mean(a)-mean(b) 的分布
    返回 percentile 95% CI + 双侧 bootstrap p（2*min 双尾比例，下限 2/n_rounds）
    """
    if len(vals_a) != len(vals_b):
        raise ValueError("配对长度必须一致")
    n = len(vals_a)
    if n == 0:
        raise ValueError("没有可配对的用例")
    diffs = [a - b for a, b in zip(vals_a, vals_b)]
    delta = sum(diffs) / n
    rng = random.Random(seed)
    boots = []
    for _ in range(n_rounds):
        s = 0.0
        for _ in range(n):
            s += diffs[rng.randrange(n)]
        boots.append(s / n)
    boots.sort()
    ci_low = boots[int(0.025 * n_rounds)]
    ci_high = boots[min(n_rounds - 1, int(0.975 * n_rounds))]
    le0 = sum(1 for x in boots if x <= 0) / n_rounds
    ge0 = sum(1 for x in boots if x >= 0) / n_rounds
    p = min(1.0, 2 * min(le0, ge0))
    p = max(p, 2.0 / n_rounds)  # 分辨率下限，避免 0 次重采样就报 p=0
    return {"delta": round(delta, 4), "ci_low": round(ci_low, 4), "ci_high": round(ci_high, 4),
            "p": round(p, 4), "significant": bool(ci_low > 0 or ci_high < 0),
            "test": "paired_bootstrap"}


def percentile_nearest_rank(values: list, p: float):
    """
    nearest-rank 分位数（p50/p95 延迟口径）
    排序后取 sorted[max(0, ceil(p*n)-1)]，n=0 返回 None
    """
    if not values:
        return None
    s = sorted(values)
    k = max(0, math.ceil(p * len(s)) - 1)
    return s[k]
