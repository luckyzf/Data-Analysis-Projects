"""
信贷风控策略模块
包含：评分卡、准入规则、额度定价、风险分级
"""

import datetime
from dataclasses import dataclass, field
from enum import Enum




# ── 风险等级 ──────────────────────────────────────────────

class RiskLevel(Enum):
    LOW = "低风险"
    MEDIUM = "中风险"
    HIGH = "高风险"
    REJECT = "拒绝"


# ── 申请人数据 ─────────────────────────────────────────────

@dataclass
class Applicant:
    name: str
    age: int
    monthly_income: float          # 月收入（元）
    debt_ratio: float              # 负债率（0~1）
    credit_score: int              # 央行征信评分（300~900）
    overdue_count_2y: int          # 近2年逾期次数
    overdue_max_days: int          # 最长逾期天数
    employment_years: float        # 工作年限
    has_house: bool                # 是否有房
    has_car: bool                  # 是否有车
    loan_amount: float             # 申请金额（元）
    loan_term_months: int          # 申请期限（月）


# ── 风控结果 ─────────────────────────────────────────────

@dataclass
class RiskResult:
    approved: bool
    risk_level: RiskLevel
    score: int                              # 综合评分
    credit_limit: float                     # 审批额度
    interest_rate: float                    # 年化利率
    reject_reasons: list = field(default_factory=list)
    review_time: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"))


# ── 1. 准入规则引擎（硬规则，命中即拒） ──────────────────────

def check_admission_rules(app: Applicant) -> list[str]:
    """准入规则校验，返回拒绝原因列表（空列表表示通过）"""
    reasons = []

    if app.age < 22 or app.age > 55:
        reasons.append("年龄不在22~55岁准入范围")

    if app.monthly_income < 3000:
        reasons.append("月收入低于3000元最低门槛")

    if app.debt_ratio > 0.7:
        reasons.append("负债率超过70%上限")

    if app.credit_score < 550:
        reasons.append("征信评分低于550分准入线")

    if app.overdue_count_2y > 6:
        reasons.append("近2年逾期次数超过6次")

    if app.overdue_max_days > 90:
        reasons.append("存在逾期超过90天的严重违约记录")

    if app.employment_years < 0.5:
        reasons.append("工作年限不足6个月")

    return reasons


# ── 2. 信用评分卡 ───────────────────────────────────────

def calculate_credit_score(app: Applicant) -> int:
    """基于申请人特征计算综合信用评分（0~100）"""
    score = 0

    # 征信评分（满分30分）
    if app.credit_score >= 750:
        score += 30
    elif app.credit_score >= 700:
        score += 25
    elif app.credit_score >= 650:
        score += 20
    elif app.credit_score >= 600:
        score += 12
    else:
        score += 5

    # 收入水平（满分20分）
    if app.monthly_income >= 30000:
        score += 20
    elif app.monthly_income >= 15000:
        score += 16
    elif app.monthly_income >= 8000:
        score += 12
    elif app.monthly_income >= 5000:
        score += 8
    else:
        score += 4

    # 负债率（满分15分）
    if app.debt_ratio <= 0.2:
        score += 15
    elif app.debt_ratio <= 0.35:
        score += 12
    elif app.debt_ratio <= 0.5:
        score += 8
    else:
        score += 3

    # 逾期情况（满分15分）
    if app.overdue_count_2y == 0:
        score += 15
    elif app.overdue_count_2y <= 2:
        score += 10
    elif app.overdue_count_2y <= 4:
        score += 5
    else:
        score += 0

    # 工作年限（满分10分）
    if app.employment_years >= 5:
        score += 10
    elif app.employment_years >= 3:
        score += 7
    elif app.employment_years >= 1:
        score += 4
    else:
        score += 2

    # 资产加分（满分10分）
    if app.has_house:
        score += 6
    if app.has_car:
        score += 4

    return score


# ── 3. 风险分级 ─────────────────────────────────────────

def classify_risk(score: int) -> RiskLevel:
    """根据综合评分划分风险等级"""
    if score >= 75:
        return RiskLevel.LOW
    elif score >= 55:
        return RiskLevel.MEDIUM
    elif score >= 40:
        return RiskLevel.HIGH
    else:
        return RiskLevel.REJECT


# ── 4. 额度与定价策略 ──────────────────────────────────────

def determine_limit_and_rate(app: Applicant, score: int, risk_level: RiskLevel) -> tuple[float, float]:
    """根据风险等级确定额度和利率"""

    # 基础额度 = 月收入 × 倍数
    multiplier_map = {
        RiskLevel.LOW: 12,
        RiskLevel.MEDIUM: 8,
        RiskLevel.HIGH: 4,
    }
    multiplier = multiplier_map.get(risk_level, 0)
    base_limit = app.monthly_income * multiplier

    # 负债率调整
    debt_adj = max(0, 1 - app.debt_ratio)
    credit_limit = round(base_limit * debt_adj, 2)

    # 额度上限控制
    limit_cap = {RiskLevel.LOW: 300000, RiskLevel.MEDIUM: 150000, RiskLevel.HIGH: 50000}
    credit_limit = min(credit_limit, limit_cap.get(risk_level, 0))

    # 利率定价（年化）
    rate_map = {RiskLevel.LOW: 0.065, RiskLevel.MEDIUM: 0.109, RiskLevel.HIGH: 0.156}
    interest_rate = rate_map.get(risk_level, 0.24)

    # 优质客户利率优惠
    if score >= 85 and app.overdue_count_2y == 0:
        interest_rate *= 0.9

    return credit_limit, round(interest_rate, 4)


# ── 5. 风控主流程 ───────────────────────────────────────

def evaluate(app: Applicant) -> RiskResult:
    """信贷风控主入口：准入 → 评分 → 分级 → 额度定价"""

    # Step 1: 准入规则
    reject_reasons = check_admission_rules(app)
    if reject_reasons:
        return RiskResult(
            approved=False,
            risk_level=RiskLevel.REJECT,
            score=0,
            credit_limit=0,
            interest_rate=0,
            reject_reasons=reject_reasons,
        )

    # Step 2: 信用评分
    score = calculate_credit_score(app)

    # Step 3: 风险分级
    risk_level = classify_risk(score)
    if risk_level == RiskLevel.REJECT:
        return RiskResult(
            approved=False,
            risk_level=RiskLevel.REJECT,
            score=score,
            credit_limit=0,
            interest_rate=0,
            reject_reasons=["综合评分不足，低于准入评分线"],
        )

    # Step 4: 额度与定价
    credit_limit, interest_rate = determine_limit_and_rate(app, score, risk_level)

    # 申请金额超出额度时降额审批
    final_limit = min(credit_limit, app.loan_amount)

    return RiskResult(
        approved=True,
        risk_level=risk_level,
        score=score,
        credit_limit=final_limit,
        interest_rate=interest_rate,
    )


# ── 示例运行 ─────────────────────────────────────────────

if __name__ == "__main__":
    # 构造测试申请人
    test_cases = [
        Applicant("张三", 30, 15000, 0.3, 720, 0, 0, 5, True, False, 100000, 12),
        Applicant("李四", 45, 8000, 0.55, 620, 3, 30, 2, False, True, 50000, 24),
        Applicant("王五", 20, 2500, 0.8, 500, 8, 120, 0.3, False, False, 30000, 6),
    ]

    for applicant in test_cases:
        result = evaluate(applicant)
        print(f"\n{'='*50}")
        print(f"申请人: {applicant.name}")
        print(f"审批结果: {'通过' if result.approved else '拒绝'}")
        print(f"风险等级: {result.risk_level.value}")
        print(f"综合评分: {result.score}")
        if result.approved:
            print(f"审批额度: {result.credit_limit:,.2f} 元")
            print(f"年化利率: {result.interest_rate:.2%}")
        else:
            print(f"拒绝原因: {'; '.join(result.reject_reasons)}")
        print(f"审核时间: {result.review_time}")
