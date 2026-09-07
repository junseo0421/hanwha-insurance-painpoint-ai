"""상품 카드의 고객용 설명. 점수 계산과 LLM 호출은 하지 않는다."""
from __future__ import annotations

from html import escape

QUESTION_TEMPLATES = {
    "전문용어 이해": "설명서의 주요 보험 용어를 쉽게 설명해 주세요.",
    "보장 범위 이해": "주요 보장은 어떤 상황에서 받을 수 있나요?",
    "상품 보장 비교": "다른 상품과 비교할 때 어떤 보장 조건을 확인해야 하나요?",
    "보험료 비교": "예시 보험료의 적용 조건과 추가로 확인할 비용은 무엇인가요?",
    "보장 제외 조건": "보장에서 제외되거나 지급이 제한되는 경우는 무엇인가요?",
    "갱신 조건": "갱신 여부와 보험료가 변동될 수 있는 조건은 무엇인가요?",
    "상담 질문 준비": "가입 전 상담사에게 반드시 확인할 내용은 무엇인가요?",
    "상담 정보 전달": "상담 전에 제 상황과 기존 보험 정보를 어떻게 준비하면 좋을까요?",
}


def build_guidance_reason(product: dict) -> str:
    """계산에 사용된 근거만 풀어 쓴다. 예산 구간 일치를 실제 견적으로 단정하지 않는다."""
    phrases = []
    for reason in product.get("_match_reasons", []):
        if reason.startswith("관심 보장(") and reason.endswith(") 포함"):
            concern = reason[len("관심 보장("):-len(") 포함")]
            phrases.append(f"관심 있는 {concern} 보장을 포함한다는 점")
        elif reason.endswith(" 대상 범위"):
            age = reason[:-len(" 대상 범위")]
            phrases.append(f"입력하신 {age}가 상품의 안내 대상 연령대에 해당한다는 점")
        elif reason.startswith("예산(") and reason.endswith(") 범위"):
            budget = reason[len("예산("):-len(") 범위")]
            phrases.append(f"등록된 예산 구간이 입력하신 {budget} 조건과 일치한다는 점")
        elif reason == "첫 보험 가입자 대상":
            phrases.append("첫 보험 가입자를 대상으로 구성됐다는 점")
        elif reason in ("가족 보장에 적합", "자녀 있는 가족의 종합 보장"):
            phrases.append("자녀가 있는 가족의 보장을 살펴볼 수 있도록 구성됐다는 점")
        elif reason == "암 보장 우선 점검":
            phrases.append("암 보장을 우선 살펴볼 수 있도록 구성됐다는 점")
        elif reason == "낮은 예산의 입원·질병 보장":
            phrases.append("낮은 예산의 입원·질병 보장을 살펴볼 수 있도록 구성됐다는 점")
        elif reason == "건강·간병 집중형":
            phrases.append("건강·간병 보장을 중심으로 살펴볼 수 있도록 구성됐다는 점")
    phrases = list(dict.fromkeys(phrases))
    if phrases:
        return ", ".join(phrases) + "을 바탕으로 살펴볼 상품으로 안내했습니다."
    return "입력 조건과 직접 일치하는 근거가 부족하여, 보장 내용과 조건을 확인할 비교 대상으로 안내했습니다."


def build_guidance_points(product: dict) -> list[str]:
    """매칭 근거를 고객이 읽기 쉬운 상세 bullet로 변환한다."""
    points: list[str] = []
    for reason in product.get("_match_reasons", []):
        if reason.startswith("관심 보장(") and reason.endswith(") 포함"):
            concern = reason[len("관심 보장("):-len(") 포함")]
            points.append(f"고객님이 가장 관심 있다고 선택한 {escape(concern)} 보장을 중심으로 확인할 수 있는 상품이에요.")
        elif reason.endswith(" 대상 범위"):
            age = reason[:-len(" 대상 범위")]
            points.append(f"고객님이 선택한 {escape(age)} 연령대에서 먼저 살펴보기 좋은 보장 조건을 포함하고 있어요.")
        elif reason.startswith("예산(") and reason.endswith(") 범위"):
            budget = reason[len("예산("):-len(") 범위")]
            points.append(f"고객님이 선택한 월 보험료 {escape(budget)} 예산 구간에서 먼저 비교해보기 좋은 상품이에요.")
        elif reason == "첫 보험 가입자 대상":
            points.append("첫 보험을 준비하는 고객이 기본 보장부터 확인하기 좋은 상품으로 구성되어 있어요.")
        elif reason in ("가족 보장에 적합", "자녀 있는 가족의 종합 보장"):
            points.append("자녀가 있는 가족이 질병·상해·입원 보장을 함께 비교해보기 좋은 상품이에요.")
        elif reason == "암 보장 우선 점검":
            points.append("암 보장을 우선 확인하려는 고객이 진단·수술 조건을 살펴보기 좋은 상품이에요.")
        elif reason == "낮은 예산의 입원·질병 보장":
            points.append("비교적 낮은 예산에서 입원·질병 보장을 먼저 확인할 수 있는 상품이에요.")
        elif reason == "건강·간병 집중형":
            points.append("건강·간병 보장을 중심으로 살펴보려는 고객에게 적합한 비교 대상이에요.")
    points = list(dict.fromkeys(points))
    return points or ["입력하신 조건과 상품의 보장 내용·보험료·가입 조건을 먼저 비교해보기 좋은 상품이에요."]


def build_caution_points(product: dict) -> list[str]:
    """상품 데이터의 주의사항과 제외 조건을 가입 전 확인 문장으로 변환한다."""
    points: list[str] = []
    if product.get("renewal") == "갱신형":
        points.append("갱신형 상품이라면 향후 보험료가 달라질 수 있으므로 갱신 주기와 보험료 변동 조건을 상담 시 확인해보세요.")
    elif product.get("renewal") == "비갱신형":
        points.append("비갱신형 상품이라도 초기 보험료, 납입 기간과 보장 범위를 함께 비교해보세요.")
    if product.get("exclusions"):
        exclusions = ", ".join(str(item) for item in product["exclusions"])
        points.append(f"다음 보장 제외 조건을 약관에서 확인해보세요: {exclusions}.")
    if product.get("caution") and not any(product["caution"] in point for point in points):
        points.append(str(product["caution"]))
    return list(dict.fromkeys(points))


def build_survey_questions(product: dict, limit: int = 2) -> list[dict]:
    """등록된 설문 우선순위 순서로 질문을 만들며, 알 수 없는 라벨도 누락하지 않는다."""
    pains = sorted(
        product.get("_survey_pain_points", []),
        key=lambda item: float(item.get("priority_score", 0)),
        reverse=True,
    )
    result, seen = [], set()
    for item in pains:
        label = item.get("label")
        if not label or label in seen:
            continue
        seen.add(label)
        question = QUESTION_TEMPLATES.get(label, f"'{label}'와 관련해 가입 전에 확인할 내용은 무엇인가요?")
        result.append({"label": label, "text": question,
                       "question": f"{product['name']}에 대해 질문합니다. {question}"})
        if len(result) >= limit:
            break
    return result
