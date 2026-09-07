from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from product_guidance import build_caution_points, build_guidance_points

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
load_dotenv(BASE_DIR / ".env")

PRODUCT_PAIN_POINTS = {
    "P001": ["전문용어 이해", "보장 범위 이해", "보험료 비교"],
    "P002": ["보장 범위 이해", "상품 보장 비교", "보험료 비교", "보장 제외 조건"],
    "P003": ["보장 범위 이해", "보장 제외 조건", "갱신 조건", "상담 질문 준비"],
    "P004": ["보장 범위 이해", "상품 보장 비교", "보장 제외 조건"],
    "P005": ["상품 보장 비교", "보장 범위 이해", "상담 질문 준비"],
    "P006": ["보험료 비교", "보장 범위 이해", "보장 제외 조건"],
}

DEFAULT_LIGHT_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
FALLBACK_MODELS = ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]


def load_products() -> list[dict]:
    with (DATA_DIR / "products.json").open(encoding="utf-8") as file:
        return json.load(file)


def load_survey_analysis() -> dict | None:
    path = DATA_DIR / "survey_analysis.json"
    if path.exists():
        with path.open(encoding="utf-8") as file:
            return json.load(file)
    # API 서버만 실행해도 최초 배포 시 분석 JSON을 생성한다.
    try:
        from analyze_data import analyze_survey
        return analyze_survey(DATA_DIR / "survey_results.csv", path)
    except Exception:
        return None


def parse_json_object(raw: str) -> dict:
    cleaned = re.sub(r"^\s*```(?:json)?\s*|\s*```\s*$", "", raw.strip(), flags=re.I)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.S)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def get_gemini_client():
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=key)
    except ImportError:
        return None


def generate_with_gemini(client, instructions: str, prompt: str) -> tuple[str, str]:
    models = list(dict.fromkeys([DEFAULT_LIGHT_GEMINI_MODEL, *FALLBACK_MODELS]))
    last_error: Exception | None = None
    for model in models:
        try:
            response = client.models.generate_content(
                model=model,
                contents=f"{instructions}\n\n{prompt}",
            )
            if not response.text:
                raise ValueError("모델이 텍스트 응답을 반환하지 않았습니다.")
            return response.text, model
        except Exception as exc:
            last_error = exc
            continue
    raise last_error or RuntimeError("사용 가능한 Gemini 모델이 없습니다.")


def age_to_group(age: int) -> str:
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대 이상"


def infer_customer_type(age_group: str, concern: str, budget: str, existing: str, family_status: str) -> str:
    if concern == "간병" or age_group == "50대 이상":
        return "중장년·건강/간병 집중형"
    if age_group in {"20대", "30대"} and existing == "없음":
        return "사회초년생·기본 보장 점검형"
    if family_status == "자녀 있음":
        return "가족 보장 강화형"
    if existing == "있음" and budget in {"5만~8만원", "8만~12만원", "12만원 이상"}:
        return "기존 보험 재점검·보완형"
    return "상품 비교·정보 탐색형"


def rank_survey_priorities(analysis: dict | None, profile: dict) -> list[dict]:
    if not analysis:
        return []
    age_group = profile.get("age_group", "")
    concerns = profile.get("concerns") or []
    concern = concerns[0] if concerns else ""
    budget = profile.get("budget", "")
    existing = profile.get("existing", "")
    family_status = profile.get("family_status", "")
    customer_type = profile.get("customer_type", "")
    relevance = set({
        "암": ["보장 범위 이해", "상품 보장 비교", "보장 제외 조건"],
        "질병": ["보장 범위 이해", "보장 제외 조건", "상품 보장 비교"],
        "입원": ["보장 범위 이해", "상품 보장 비교", "보험료 비교"],
        "간병": ["보장 범위 이해", "보장 제외 조건", "상담 질문 준비"],
    }.get(concern, []))
    if existing == "없음":
        relevance.update(["전문용어 이해", "보험료 비교", "상담 질문 준비"])
    if existing == "있음":
        relevance.update(["상품 보장 비교", "보장 제외 조건", "갱신 조건"])
    if budget in {"3만원 이하", "3만~5만원", "5만 원 이하"}:
        relevance.add("보험료 비교")
    if family_status == "자녀 있음":
        relevance.update(["보장 범위 이해", "상품 보장 비교"])
    if customer_type == "중장년·건강/간병 집중형":
        relevance.update(["보장 제외 조건", "갱신 조건", "상담 질문 준비"])
    clusters = analysis.get("clusters", [])
    max_ratio = max((float(row.get("ratio", 0)) for row in clusters), default=1.0) or 1.0
    result = []
    for row in clusters:
        ratio = float(row.get("ratio", 0))
        related = 1.0 if row.get("label") in relevance else 0.0
        score = 0.50 * (ratio / max_ratio) + 0.30 * (float(row.get("avg_severity", 0)) / 5) + 0.20 * related
        result.append({
            **row,
            "priority_score": round(score, 4),
            "priority_reason": f"응답 비율 {ratio:.1%}, 평균 심각도 {float(row.get('avg_severity', 0)):.1f}/5" + (f", 고객 조건 관련성 높음({concern})" if related else ""),
        })
    return sorted(result, key=lambda row: (-row["priority_score"], str(row.get("label", ""))))


def _chosen(value: Any) -> bool:
    return value not in (None, "", "선택", "잘 모르겠음")


def calculate_core_label_score(product: dict, profile: dict) -> tuple[int, list[str]]:
    match = product.get("match_profile", {})
    score = 0
    reasons: list[str] = []
    age = profile.get("insurance_age")
    age_range = match.get("insurance_age_range", {})
    if isinstance(age, (int, float)) and age_range and age_range.get("min", 0) <= age <= age_range.get("max", 100):
        score += 15
        reasons.append("보험나이 조건에 부합합니다.")
    concerns = [item for item in profile.get("concerns", []) if _chosen(item)]
    overlaps = [item for item in concerns if item in product.get("concerns", product.get("coverage", []))]
    if overlaps:
        score += min(20, 10 * len(overlaps))
        reasons.append("관심 보장(" + ", ".join(overlaps) + ")을 포함합니다.")
    aliases = {"3만원 이하": ["5만 원 이하"], "3만~5만원": ["5만 원 이하", "5만~8만 원"], "5만~8만원": ["5만~8만 원"], "8만~12만원": ["8만 원 이상"], "12만원 이상": ["8만 원 이상"]}
    budget = profile.get("budget")
    if _chosen(budget) and (budget in product.get("budget_bands", []) or any(x in product.get("budget_bands", []) for x in aliases.get(budget, []))):
        score += 15
        reasons.append("희망 예산 범위에서 비교할 수 있습니다.")
    if _chosen(profile.get("family_status")) and profile["family_status"] in match.get("family_types", []):
        score += 10
        reasons.append("가족 구성과 관련된 대상 조건을 포함합니다.")
    if profile.get("existing") in match.get("existing_statuses", []):
        score += 10
        reasons.append("기존 보험 보유 여부와 상품 대상 조건이 맞습니다.")
    return min(score, 70), reasons or ["선택한 핵심 조건과 상품 정보를 비교합니다."]


def calculate_survey_score(product: dict, priorities: list[dict]) -> int:
    pains = product.get("pain_points", PRODUCT_PAIN_POINTS.get(product.get("product_id"), []))
    alignment = sum(float(row.get("priority_score", 0)) for row in priorities if row.get("label") in pains)
    return min(10, max(0, round(alignment * 5)))


def product_sort_key(product: dict) -> tuple:
    return (-int(product.get("_match_score", 0)), -float(product.get("_survey_alignment", 0)), str(product.get("name", "")))


def build_base_recommendations(products: list[dict], profile: dict, priorities: list[dict]) -> list[dict]:
    result = []
    for product in products:
        hard, reasons = calculate_core_label_score(product, profile)
        survey = calculate_survey_score(product, priorities)
        pains = product.get("pain_points", PRODUCT_PAIN_POINTS.get(product.get("product_id"), []))
        result.append({
            **product,
            "_hard_score": hard,
            "_survey_points": survey,
            "_llm_bonus": 0,
            "_match_score": hard + survey,
            "_match_reasons": reasons,
            "_survey_alignment": survey,
            "_survey_pain_points": [row for row in priorities if row.get("label") in pains][:3],
        })
    return sorted(result, key=product_sort_key)


def recommend_products_with_gemini(products: list[dict], profile: dict, priorities: list[dict], use_llm: bool = True) -> tuple[list[dict], str]:
    fallback = build_base_recommendations(products, profile, priorities)
    client = get_gemini_client() if use_llm else None
    if not client:
        return fallback, "기본 규칙 추천 · Gemini 미사용"
    context = [{
        "product_id": p.get("product_id"), "name": p.get("name"), "type": p.get("type"),
        "target": p.get("target"), "concerns": p.get("concerns"), "coverage": p.get("coverage"),
        "renewal": p.get("renewal"), "premium_example": p.get("premium_example"),
        "caution": p.get("caution"), "match_profile": p.get("match_profile"),
        "base_score": p.get("_hard_score", 0), "survey_score": p.get("_survey_points", 0),
    } for p in products]
    instructions = """보험상품 정보 탐색용 추천 도우미다. 제공된 고객 입력·설문·상품 데이터만 근거로 정렬하고, 가입 가능성이나 최종 가입 판단은 하지 않는다. 핵심 점수와 설문 점수는 유지하고 추가 상황 해석 점수만 0~20점으로 계산한다. JSON만 반환한다."""
    prompt = json.dumps({"customer": profile, "survey_priorities": priorities[:8], "products": context}, ensure_ascii=False, indent=2) + '\n형식: {"recommendations":[{"product_id":"P001","additional_score":0,"reasons":["..."],"cautions":["..."]}]}'
    try:
        raw, model = generate_with_gemini(client, instructions, prompt)
        rows = parse_json_object(raw).get("recommendations", [])
        by_id = {str(p.get("product_id")): p for p in products}
        base = {str(p.get("product_id")): p for p in fallback}
        output = []
        seen = set()
        for row in rows if isinstance(rows, list) else []:
            pid = str(row.get("product_id", "")) if isinstance(row, dict) else ""
            if pid not in by_id or pid in seen:
                continue
            seen.add(pid)
            try:
                bonus = max(0, min(20, int(float(row.get("additional_score", 0)))))
            except (TypeError, ValueError):
                bonus = 0
            item = dict(base[pid])
            item["_llm_bonus"] = bonus
            item["_match_score"] = min(100, int(item.get("_hard_score", 0)) + int(item.get("_survey_points", 0)) + bonus)
            item["_ai_score"] = item["_match_score"]
            item["_ai_reasons"] = [str(x)[:180] for x in (row.get("reasons", []) if isinstance(row.get("reasons", []), list) else [row.get("reasons")]) if str(x).strip()][:3] or ["고객 입력과 상품 정보를 함께 검토한 결과입니다."]
            item["_ai_cautions"] = [str(x)[:180] for x in (row.get("cautions", []) if isinstance(row.get("cautions", []), list) else [row.get("cautions")]) if str(x).strip()][:2] or build_caution_points(item)
            item["_recommendation_mode"] = f"Gemini AI 종합 추천 · {model}"
            output.append(item)
        for p in products:
            if str(p.get("product_id")) not in seen:
                item = dict(base[str(p.get("product_id"))])
                item["_ai_score"] = item["_match_score"]
                item["_ai_reasons"] = ["AI 응답에서 별도 추천 근거가 제시되지 않은 상품입니다."]
                item["_ai_cautions"] = build_caution_points(item)
                item["_recommendation_mode"] = f"Gemini AI 종합 추천 · {model}"
                output.append(item)
        return sorted(output, key=lambda p: (-int(p.get("_match_score", 0)), str(p.get("name", "")))), f"Gemini AI 종합 추천 · {model}"
    except Exception as exc:
        return fallback, f"Gemini 추천 실패 · 기본 규칙 추천 ({type(exc).__name__}: {str(exc)[:120]})"


def classify_question(question: str) -> str:
    q = question.lower()
    if any(x in q for x in ["비교", "차이", "어떤 상품"]): return "상품 비교"
    if any(x in q for x in ["갱신", "보험료가 오", "보험료 변동"]): return "갱신 조건"
    if any(x in q for x in ["제외", "보장 안", "받을 수 없", "기존 질환"]): return "보장 제외·주의사항"
    if any(x in q for x in ["보장", "암", "입원", "간병"]): return "보장 설명"
    if any(x in q for x in ["상담", "물어", "질문"]): return "상담 준비"
    return "용어 설명"


def answer_question(question: str, selected: list[dict], use_llm: bool = True) -> tuple[str, str, str]:
    intent = classify_question(question)
    client = get_gemini_client() if use_llm else None
    if client:
        instructions = "보험상품 데이터에 있는 내용만 사용해 한국어로 핵심 답변·주의사항·근거를 간결히 설명한다. 가입 판단을 대신하지 않는다."
        try:
            raw, model = generate_with_gemini(client, instructions, json.dumps({"question": question, "products": selected}, ensure_ascii=False, indent=2))
            return intent, raw, f"Gemini API · {model}"
        except Exception as exc:
            fallback_mode = f"Gemini 호출 실패 · 기본 답변 ({type(exc).__name__}: {str(exc)[:140]})"
    else:
        fallback_mode = "기본 템플릿"
    if intent == "상품 비교":
        text = "선택한 상품을 같은 기준으로 비교하면 다음과 같습니다.\n\n" + "\n".join(f"- **{p['name']}**: {p.get('renewal')}, {', '.join(p.get('coverage', []))}, {p.get('premium_example')}" for p in selected)
    elif intent == "갱신 조건":
        text = "갱신형은 일정 기간마다 계약을 갱신하는 방식으로, 갱신 시점에 보험료가 변동될 수 있습니다."
    elif intent == "보장 제외·주의사항":
        text = "보장 제외 조건은 상품별 약관에 따라 다르므로 기존 질환, 면책기간, 고지 의무를 확인해야 합니다."
    elif intent == "보장 설명":
        text = "보장 내용은 상품별 진단 기준과 지급 조건을 함께 확인해야 합니다."
    elif intent == "상담 준비":
        text = "상담 시 갱신 여부, 보장 제외 조건, 보험료 변동 가능성, 중도 해지 조건을 확인해 보세요."
    else:
        text = "보험 용어는 상품 설명서의 정의와 보장 조건을 함께 확인하는 것이 좋습니다."
    if selected:
        text += f"\n\n현재 선택 상품: **{selected[0]['name']}**\n근거: {selected[0].get('source')} ({selected[0].get('source_date')})"
    return intent, text, fallback_mode


def refine_answer_with_feedback(question: str, previous_answer: str, feedback: str, selected: list[dict], use_llm: bool = True) -> tuple[str, str]:
    """사용자 피드백을 반영해 기존 설명을 다시 작성한다."""
    client = get_gemini_client() if use_llm else None
    if client:
        instructions = "보험상품 데이터에 있는 내용만 사용해 기존 답변을 사용자의 피드백에 맞게 다시 작성한다. 가입 판단을 대신하지 않는다. 핵심 답변·주의사항·근거를 포함한다."
        prompt = json.dumps({"question": question, "previous_answer": previous_answer, "feedback": feedback, "products": selected}, ensure_ascii=False, indent=2)
        try:
            raw, model = generate_with_gemini(client, instructions, prompt)
            return raw, f"피드백 반영 Gemini API · {model}"
        except Exception as exc:
            mode = f"Gemini 피드백 반영 실패 · {type(exc).__name__}: {str(exc)[:120]}"
    else:
        mode = "LLM 미사용 · 기본 피드백 반영"
    return f"{previous_answer}\n\n[사용자 피드백]\n{feedback}\n\n현재는 AI 재생성을 사용할 수 없어 기존 답변과 피드백을 함께 표시합니다.", mode


def recommend_questions(profile: dict, selected: list[dict], priorities: list[dict], use_llm: bool = True) -> tuple[list[str], str]:
    labels = [row.get("label") for row in priorities]
    concern = (profile.get("concerns") or ["선택"])[0]
    templates = {
        "전문용어 이해": "설명서의 주요 보험 용어를 제 상황에 맞게 쉽게 설명해 주실 수 있나요?",
        "보장 범위 이해": f"제가 관심 있는 {concern} 보장은 어떤 조건에서 받을 수 있나요?",
        "상품 보장 비교": "비교한 상품들의 보장 범위와 지급 조건 중 가장 큰 차이는 무엇인가요?",
        "보험료 비교": "월 보험료 차이가 보장 범위와 어떤 관계가 있나요?",
        "보장 제외 조건": "기존 질환이나 면책기간 때문에 보장에서 제외될 수 있는 조건은 무엇인가요?",
        "갱신 조건": "갱신 주기와 갱신 시 보험료가 변동되는 조건은 무엇인가요?",
        "상담 질문 준비": "가입 전에 상담사에게 반드시 확인해야 하는 질문은 무엇인가요?",
    }
    fallback = list(dict.fromkeys([templates[x] for x in labels if x in templates]))[:4]
    fallback += ["상품의 보장 제외 조건은 무엇인가요?", "중도 해지 시 환급금은 어떻게 계산되나요?"]
    fallback = list(dict.fromkeys(fallback))[:4]
    client = get_gemini_client() if use_llm else None
    if not client:
        return fallback, "기본 질문 목록"
    instructions = "고객이 상담사에게 물어볼 보험 질문 4개를 한국어로 생성한다. 입력된 상품·고객·설문 내용만 근거로 하며 각 줄은 질문 하나만 출력한다."
    prompt = json.dumps({"customer": profile, "survey_priorities": priorities[:5], "products": selected}, ensure_ascii=False, indent=2)
    try:
        raw, model = generate_with_gemini(client, instructions, prompt)
        questions = []
        for line in re.split(r"[\r\n]+|(?<=[?？])\s+", raw):
            line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            if len(line) >= 8 and ("?" in line or "？" in line or re.search(r"(까요|나요|습니까)\s*$", line)):
                questions.append(line)
        questions = list(dict.fromkeys(questions))[:4]
        if len(questions) >= 3:
            return questions, f"Gemini API · {model}"
    except Exception:
        pass
    return fallback, "Gemini 실패 · 기본 질문 목록"


def survey_summary() -> dict:
    analysis = load_survey_analysis()
    if analysis:
        clusters = analysis.get("clusters", [])
        return {"analysis": analysis, "clusters": clusters, "method": analysis.get("method"), "n_clusters": analysis.get("n_clusters")}
    return {"analysis": None, "clusters": [], "method": None, "n_clusters": 0}
