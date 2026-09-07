from __future__ import annotations

import json
import os
import re
import time
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from product_guidance import build_caution_points, build_guidance_points, build_survey_questions


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
load_dotenv(BASE_DIR / ".env")

# 무료 플랜의 호출량을 고려한 기본 모델. 단순 분류·요약·질문 생성에 적합하다.
DEFAULT_LIGHT_GEMINI_MODEL = "gemini-3.5-flash-lite"
HEAVY_GEMINI_MODELS = {
    "gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash",
    "gemini-3.5-flash", "gemini-2.5-flash", "gemini-2.5-pro",
}

st.set_page_config(page_title="한화생명 Easy Guide AI", page_icon="🟠", layout="wide")

st.markdown(
    """
    <style>
    :root {
        --hanwha-orange: #f36f21;
        --hanwha-orange-dark: #d9570b;
        --hanwha-ink: #171717;
        --hanwha-warm: #faf7f4;
        --hanwha-line: #e9e2dc;
    }
    .stApp { background: #ffffff; color: var(--hanwha-ink); }
    .block-container { padding-top: 3rem; max-width: 1280px; }
    [data-testid="stSidebar"] { background: var(--hanwha-warm); border-right: 1px solid var(--hanwha-line); }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 { color: var(--hanwha-ink); }
    h1, h2, h3 { color: var(--hanwha-ink); letter-spacing: -0.035em; }
    h1 { font-weight: 800; }
    h2 { border-left: 4px solid var(--hanwha-orange); padding-left: 1.05rem; margin-left: .1rem; margin-top: 2.15rem; margin-bottom: 1rem; }
    [data-testid="stSidebar"] h2 { position: relative; border-left: 0; padding-left: 1.15rem; }
    [data-testid="stSidebar"] h2::before { content: ""; position: absolute; left: 0; top: 18%; width: 4px; height: 64%; background: var(--hanwha-orange); }
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
    [data-testid="stSidebar"] label p { font-weight: 750 !important; }
    [data-testid="stMetric"] { background: var(--hanwha-warm); border: 1px solid var(--hanwha-line); border-top: 4px solid var(--hanwha-orange); border-radius: 0.35rem; padding: .8rem 1rem; }
    [data-testid="stMetricLabel"] { color: #6e625a; font-size: .82rem; }
    [data-testid="stMetricValue"] { color: var(--hanwha-ink); font-weight: 800; font-size: .98rem !important; line-height: 1.25; white-space: normal !important; overflow: visible !important; text-overflow: clip !important; overflow-wrap: anywhere; }
    .hanwha-table-wrap { width: 100%; overflow: visible; margin: .35rem 0 1rem; }
    .hanwha-table { width: 100%; table-layout: fixed; border-collapse: separate; border-spacing: 0; border: 1px solid #f3c5a9; border-radius: .45rem; overflow: hidden; font-size: .86rem; line-height: 1.4; }
    .hanwha-table th { background: var(--hanwha-orange); color: #fff; font-weight: 700; text-align: left; }
    .hanwha-table th, .hanwha-table td { border-right: 1px solid #f3c5a9; border-bottom: 1px solid #f3c5a9; padding: .55rem .6rem; vertical-align: top; white-space: normal; overflow-wrap: anywhere; word-break: break-word; }
    .hanwha-table th:last-child, .hanwha-table td:last-child { border-right: 0; }
    .hanwha-table tbody tr:last-child td { border-bottom: 0; }
    .hanwha-table tbody tr:nth-child(even) td { background: #fff7f1; }
    .hanwha-table tbody tr:hover td { background: #ffe9dc; }
    @media (max-width: 760px) { .hanwha-table { font-size: .76rem; } .hanwha-table th, .hanwha-table td { padding: .42rem .45rem; } }
    .stButton > button { border-radius: .25rem; border: 1px solid var(--hanwha-orange); color: var(--hanwha-orange-dark); font-weight: 700; }
    .stButton > button:hover { border-color: var(--hanwha-orange-dark); color: #fff; background: var(--hanwha-orange); }
    button[kind="primary"] { background: var(--hanwha-orange) !important; color: #fff !important; border-color: var(--hanwha-orange) !important; }
    [data-testid="stExpander"] { border: 1px solid var(--hanwha-line); border-radius: .35rem; }
    .hanwha-kicker { display: flex; gap: 1rem; align-items: center; color: var(--hanwha-orange); font-size: .82rem; font-weight: 800; letter-spacing: .12em; text-transform: uppercase; line-height: 1.5; padding-top: .2rem; margin-bottom: .55rem; overflow: visible; }
    .hanwha-kicker span { color: #9b918b; font-weight: 500; letter-spacing: .16em; }
    .hanwha-hero { background: linear-gradient(100deg, #fff7f1 0%, #fff 72%); border-left: 6px solid var(--hanwha-orange); border-top: 1px solid var(--hanwha-line); border-bottom: 1px solid var(--hanwha-line); padding: 1.35rem 1.5rem 1.25rem; margin-bottom: 1.25rem; }
    .hanwha-hero .brand { color: var(--hanwha-orange); font-size: .78rem; font-weight: 800; letter-spacing: .16em; margin-bottom: .25rem; }
    .hanwha-hero .title { color: var(--hanwha-ink); font-size: 2.15rem; line-height: 1.12; font-weight: 850; letter-spacing: -.055em; }
    .hanwha-hero .subtitle { color: #6e625a; margin-top: .45rem; font-size: .98rem; }
    .section-divider { height: 1.5rem; border-top: 1px solid var(--hanwha-line); margin-top: 1.5rem; }
    /* 상품 추천 카드: 지표 카드와 같은 웜화이트·오렌지 상단 라인 박스 */
    [data-testid="stColumn"]:has(.product-card-marker) [data-testid="stVerticalBlock"]:has(.product-card-marker):not(:has([data-testid="stVerticalBlock"] .product-card-marker)) { min-height: 32rem; height: 32rem; overflow-y: auto; box-sizing: border-box; border: 1px solid var(--hanwha-line) !important; border-top: 4px solid var(--hanwha-orange) !important; border-radius: .35rem !important; background: var(--hanwha-warm) !important; }
    [data-testid="stColumn"]:has(.product-card-marker) [data-testid="stVerticalBlock"]:has(.product-card-marker):not(:has([data-testid="stVerticalBlock"] .product-card-marker)) > div { background: transparent !important; }
    [data-testid="stColumn"]:has(.product-card-marker) { display: flex; }
    [data-testid="stColumn"]:has(.product-card-marker) > [data-testid="stVerticalBlock"] { width: 100%; }
    .product-card-marker { display: none; }
    .product-guidance { color: #29211c; font-size: 1rem; line-height: 1.55; background: #fffaf7; border: 1px solid #f3d7c5; border-top: 3px solid #f36f21; padding: .8rem .95rem; border-radius: .45rem; margin: 0; overflow-wrap: anywhere; }
    .product-caution { color: #174a7c; font-size: .96rem; line-height: 1.55; background: #f6f9fd; border: 1px solid #d6e3f1; border-top: 3px solid #6b9ed1; padding: .8rem .95rem; border-radius: .45rem; margin: 0; overflow-wrap: anywhere; }
    .product-guidance-list, .product-caution-list { display: block; margin: 0; padding: 0; }
    .product-guidance-item, .product-caution-item { position: relative; margin: 0; padding: 0 0 0 1rem; line-height: 1.55; }
    .product-guidance-item + .product-guidance-item, .product-caution-item + .product-caution-item { margin-top: .35rem; }
    .product-guidance-item::before, .product-caution-item::before { content: "•"; position: absolute; left: .05rem; top: 0; font-weight: 800; }
    .product-guidance-item::before { color: #f36f21; }
    .product-caution-item::before { color: #6b9ed1; }
    .chat-message { border: 1px solid var(--hanwha-line); border-radius: .65rem; padding: .85rem 1rem; margin: .45rem 0; overflow-wrap: anywhere; }
    .chat-window { height: 26rem; max-height: 58vh; min-height: 20rem; overflow-y: auto; overscroll-behavior: contain; display: flex; flex-direction: column-reverse; gap: .15rem; background: #ffffff; border: 1px solid var(--hanwha-line); border-radius: .75rem; padding: .75rem; scrollbar-gutter: stable; }
    .chat-window::-webkit-scrollbar { width: .55rem; }
    .chat-window::-webkit-scrollbar-thumb { background: #d8cec7; border-radius: 999px; }
    .chat-window::-webkit-scrollbar-track { background: transparent; }
    .chat-user { background: #fff0e5; border-color: #f3d7c5; margin-left: 8%; }
    .chat-assistant { background: #f8fafc; border-color: #dce5ee; margin-right: 8%; }
    .chat-label { font-size: .78rem; font-weight: 800; color: #6e625a; margin-bottom: .3rem; }
    .chat-user .chat-label { color: #c65213; }
    .chat-assistant .chat-label { color: #35658d; }
    .chat-text { color: #29211c; line-height: 1.6; white-space: normal; }
    .chat-text strong { font-weight: 800; }
    [data-testid="stColumn"]:has(.product-card-marker) button p { white-space: normal; overflow-wrap: anywhere; text-align: left; line-height: 1.45; }
    [data-testid="stColumn"]:has(.product-card-marker) [data-testid="stVerticalBlock"]:has(.product-card-marker):not(:has([data-testid="stVerticalBlock"] .product-card-marker)) { height: 100%; overflow-y: visible; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data
def load_survey() -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / "survey_results.csv")


@st.cache_data
def load_products() -> list[dict]:
    with (DATA_DIR / "products.json").open(encoding="utf-8") as f:
        return json.load(f)


@st.cache_data
def load_analysis() -> dict | None:
    analysis_path = DATA_DIR / "survey_analysis.json"
    if analysis_path.exists():
        with analysis_path.open(encoding="utf-8") as f:
            cached = json.load(f)
        # 예전 4개 라벨 결과가 남아 있으면 새 taxonomy로 한 번만 갱신한다.
        clusters = cached.get("clusters", [])
        if cached.get("n_clusters") == 8 and clusters and "parent_label" in clusters[0]:
            return cached
    # 배포 환경에서 app.py만 실행해도 분석 결과를 자동 생성한다.
    try:
        from analyze_data import analyze_survey
        return analyze_survey(DATA_DIR / "survey_results.csv", analysis_path)
    except Exception:
        # 분석 패키지가 없거나 데이터가 잘못된 경우에도 앱은 기준 라벨로 실행한다.
        return None


def run_analysis() -> dict:
    """설문 파일을 다시 분석한다. 버튼 클릭 또는 CLI에서 명시적으로 호출한다."""
    from analyze_data import analyze_survey

    return analyze_survey(DATA_DIR / "survey_results.csv", DATA_DIR / "survey_analysis.json")


def get_gemini_client():
    """Gemini API 키가 있을 때만 Google GenAI 클라이언트를 만든다."""
    api_key = os.getenv("GEMINI_API_KEY")
    try:
        if not api_key and "GEMINI_API_KEY" in st.secrets:
            api_key = st.secrets["GEMINI_API_KEY"]
    except Exception:
        pass
    if not api_key:
        return None
    try:
        from google import genai
    except ImportError:
        return None
    return genai.Client(api_key=api_key)


def generate_with_gemini(
    client,
    instructions: str,
    prompt: str,
    preferred_model: str | None = None,
    fallback_models: list[str] | None = None,
) -> tuple[str, str]:
    """일시적인 서버 오류가 나면 재시도하고 호환 모델로 전환한다."""
    configured = preferred_model or os.getenv("GEMINI_MODEL")
    if configured and configured.startswith("models/"):
        configured = configured.split("/", 1)[1]
    # 기존 .env에 무거운 모델이 남아 있어도 무료 플랜에서는 경량 모델로 자동 전환한다.
    preferred = DEFAULT_LIGHT_GEMINI_MODEL if not configured or configured in HEAVY_GEMINI_MODELS else configured
    # 404 NOT_FOUND(신규 사용자에게 제공되지 않는 모델 포함)가 발생하면
    # 다음 모델로 넘어간다. .env에 예전 모델명이 남아 있어도 앱이 중단되지 않는다.
    candidates = list(dict.fromkeys([
        preferred,
        *(fallback_models or ["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"]),
    ]))
    last_error: Exception | None = None

    for model in candidates:
        for attempt in range(2):
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
                error_text = str(exc).lower()
                is_model_unavailable = (
                    "404" in error_text
                    or "not_found" in error_text
                    or "no longer available" in error_text
                )
                is_transient = type(exc).__name__ == "ServerError"
                # 인증·요청 형식 오류는 재시도해도 해결되지 않으므로 즉시 중단한다.
                if not (is_model_unavailable or is_transient):
                    raise
                if is_transient and attempt == 0:
                    time.sleep(1.0)

    if last_error:
        raise last_error
    raise RuntimeError("사용 가능한 Gemini 모델을 찾지 못했습니다.")


def classify_question(question: str) -> str:
    q = question.lower()
    if any(word in q for word in ["비교", "차이", "어떤 상품"]):
        return "상품 비교"
    if any(word in q for word in ["갱신", "보험료가 오", "보험료 변동"]):
        return "갱신 조건"
    if any(word in q for word in ["제외", "보장 안", "받을 수 없", "기존 질환"]):
        return "보장 제외·주의사항"
    if any(word in q for word in ["보장", "암", "입원", "간병"]):
        return "보장 설명"
    if any(word in q for word in ["상담", "물어", "질문"]):
        return "상담 준비"
    return "용어 설명"


def infer_customer_type(age_group: str, concern: str, budget: str, existing: str, family_status: str) -> str:
    if concern == "간병" or age_group == "50대 이상":
        return "중장년·건강/간병 집중형"
    if age_group in ["20대", "30대"] and existing == "없음":
        return "사회초년생·기본 보장 점검형"
    if family_status == "자녀 있음":
        return "가족 보장 강화형"
    if existing == "있음" and budget in ["5만~8만 원", "8만 원 이상", "5만~8만원", "8만~12만원", "12만원 이상"]:
        return "기존 보험 재점검·보완형"
    return "상품 비교·정보 탐색형"


def age_to_group(age: int) -> str:
    """숫자로 입력한 보험나이를 설문·상품 데이터의 연령대 라벨로 변환한다."""
    if age < 30:
        return "20대"
    if age < 40:
        return "30대"
    if age < 50:
        return "40대"
    return "50대 이상"


def parse_json_object(raw: str) -> dict:
    """Gemini가 코드펜스나 부가 설명을 붙여도 JSON 객체를 추출한다."""
    cleaned = raw.strip()
    cleaned = re.sub(r"^\s*```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```\s*$", "", cleaned)
    try:
        value = json.loads(cleaned)
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
        if not match:
            return {}
        try:
            value = json.loads(match.group(0))
            return value if isinstance(value, dict) else {}
        except json.JSONDecodeError:
            return {}


def analyze_customer_note(
    note: str,
    customer_profile: dict,
    products: list[dict],
    use_llm: bool = True,
) -> tuple[dict, str]:
    """추가 설명을 허용된 라벨로 해석한다. 가입 가능성이나 의학적 판단은 하지 않는다."""
    if not note.strip():
        return {}, "추가 설명 없음"
    client = get_gemini_client() if use_llm else None
    if not client:
        return {}, "Gemini 미사용 · 하드 라벨만 반영"

    allowed_concerns = ["암", "뇌혈관", "심혈관", "질병", "입원", "수술", "상해", "사망", "간병"]
    allowed_criteria = ["낮은 보험료", "넓은 보장", "비갱신형", "긴 보장기간", "해약환급금", "간편가입"]
    allowed_purposes = ["첫 보험", "기존 보험 보완", "보험료 절감", "갱신형 점검", "가족 보장", "노후·간병 준비"]
    instructions = (
        "당신은 보험상품 정보 탐색을 돕는 입력 정리 도우미입니다. "
        "사용자의 추가 설명을 정해진 라벨로만 구조화하세요. "
        "가입 가능 여부, 인수 심사, 질병 위험도, 보험료 확정 판단은 하지 마세요. "
        "반드시 JSON 객체만 반환하세요."
    )
    prompt = (
        f"고객의 구조화된 상황:\n{json.dumps(customer_profile, ensure_ascii=False, indent=2)}\n\n"
        f"추가 설명:\n{note}\n\n"
        f"허용 관심 보장 라벨: {allowed_concerns}\n"
        f"허용 중요 기준 라벨: {allowed_criteria}\n"
        f"허용 가입 목적 라벨: {allowed_purposes}\n\n"
        "다음 형식으로만 답하세요:\n"
        '{"concerns":[],"criteria":[],"purposes":[],"keywords":[],"risk_flags":[],"summary":""}\n'
        "concerns·criteria·purposes는 허용 목록에서만 선택하고, "
        "keywords는 짧은 일반 명사 3개 이내, risk_flags는 상담 확인이 필요한 표현만 넣으세요."
    )
    try:
        raw, model = generate_with_gemini(
            client,
            instructions,
            prompt,
            preferred_model=os.getenv("GEMINI_PROFILE_MODEL") or os.getenv("GEMINI_MODEL"),
            fallback_models=["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
        )
        parsed = parse_json_object(raw)
        def list_value(key: str) -> list:
            value = parsed.get(key, [])
            if isinstance(value, str):
                return [value]
            return value if isinstance(value, list) else []

        parsed["concerns"] = [x for x in list_value("concerns") if x in allowed_concerns]
        parsed["criteria"] = [x for x in list_value("criteria") if x in allowed_criteria]
        parsed["purposes"] = [x for x in list_value("purposes") if x in allowed_purposes]
        parsed["keywords"] = [str(x)[:30] for x in list_value("keywords")[:3]]
        parsed["risk_flags"] = [str(x)[:80] for x in list_value("risk_flags")[:3]]
        parsed["summary"] = str(parsed.get("summary", ""))[:180]
        return parsed, f"Gemini API · {model}"
    except Exception as exc:
        detail = str(exc).replace("\n", " ")[:120]
        return {}, f"Gemini 분석 실패 · 하드 라벨만 반영 ({type(exc).__name__}: {detail})"


# 상품별로 어떤 설문 불편을 해결하는지 연결한다. 실제 상품 도입 시에는
# 상품 설명서의 기능/보장 항목과 함께 내부 데이터로 관리하면 된다.
PRODUCT_PAIN_POINTS = {
    "P001": ["전문용어 이해", "보장 범위 이해", "보험료 비교"],
    "P002": ["보장 범위 이해", "상품 보장 비교", "보험료 비교", "보장 제외 조건"],
    "P003": ["보장 범위 이해", "보장 제외 조건", "갱신 조건", "상담 질문 준비"],
    "P004": ["보장 범위 이해", "상품 보장 비교", "보장 제외 조건"],
    "P005": ["상품 보장 비교", "보장 범위 이해", "상담 질문 준비"],
    "P006": ["보험료 비교", "보장 범위 이해", "보장 제외 조건"],
}


def rank_survey_priorities(
    analysis: dict | None,
    age_group: str,
    concern: str,
    budget: str,
    existing: str,
    family_status: str,
    customer_type: str,
) -> list[dict]:
    """빈도·심각도·고객 조건을 결합해 설문 페인포인트 우선순위를 계산한다."""
    if not analysis:
        return []
    concern_labels = {
        "암": ["보장 범위 이해", "상품 보장 비교", "보장 제외 조건"],
        "질병": ["보장 범위 이해", "보장 제외 조건", "상품 보장 비교"],
        "입원": ["보장 범위 이해", "상품 보장 비교", "보험료 비교"],
        "간병": ["보장 범위 이해", "보장 제외 조건", "상담 질문 준비"],
    }
    relevance_labels = set(concern_labels.get(concern, []))
    if existing == "없음":
        relevance_labels.update(["전문용어 이해", "보험료 비교", "상담 질문 준비"])
    if existing == "있음":
        relevance_labels.update(["상품 보장 비교", "보장 제외 조건", "갱신 조건"])
    if budget in ["5만 원 이하", "3만원 이하", "3만~5만원"]:
        relevance_labels.add("보험료 비교")
    elif budget in ["8만 원 이상", "8만~12만원", "12만원 이상"]:
        relevance_labels.update(["보장 범위 이해", "상품 보장 비교"])
    if family_status == "자녀 있음":
        relevance_labels.update(["보장 범위 이해", "상품 보장 비교"])
    if customer_type == "중장년·건강/간병 집중형":
        relevance_labels.update(["보장 제외 조건", "갱신 조건", "상담 질문 준비"])

    clusters = analysis.get("clusters", [])
    max_ratio = max((float(item.get("ratio", 0)) for item in clusters), default=1.0) or 1.0
    priorities = []
    for item in clusters:
        raw_ratio = float(item.get("ratio", 0))
        frequency_score = raw_ratio / max_ratio
        severity_score = float(item.get("avg_severity", 0)) / 5
        relevance_score = 1.0 if item.get("label") in relevance_labels else 0.0
        # 설문 근거를 가장 크게 반영하되, 고객 상황과 상품 탐색 목적도 가산한다.
        priority = 0.50 * frequency_score + 0.30 * severity_score + 0.20 * relevance_score
        priorities.append({
            **item,
            "priority_score": round(priority, 4),
            "priority_reason": (
                f"응답 비율 {raw_ratio:.1%}, 평균 심각도 {item.get('avg_severity', 0):.1f}/5"
                + (f", 고객 조건 관련성 높음({concern})" if relevance_score else "")
            ),
        })
    return sorted(priorities, key=lambda item: item["priority_score"], reverse=True)


def score_product(
    product: dict,
    age_group: str,
    concern: str,
    budget: str,
    existing: str,
    family_status: str,
    customer_type: str,
    survey_priorities: list[dict] | None = None,
    customer_profile: dict | None = None,
    llm_analysis: dict | None = None,
) -> tuple[int, list[str], dict]:
    profile = customer_profile or {}
    match_profile = product.get("match_profile", {})
    selected_concerns = [
        value for value in (profile.get("concerns") or ([concern] if concern else []))
        if value and value != "선택"
    ]
    score = 0
    reasons: list[str] = []
    breakdown = {
        "고객 기본정보": 0, "가입 목적·관심 보장": 0, "보험료·계약조건": 0,
        "기존 보험 현황": 0, "설문 대응": 0, "추가 입력 관련성": 0,
    }

    def add(category: str, points: int, reason: str) -> None:
        nonlocal score
        score += points
        breakdown[category] += points
        if reason:
            reasons.append(reason)

    def chosen(value: object) -> bool:
        return value not in (None, "", "선택", "잘 모르겠음")

    profile_age_group = profile.get("age_group", age_group)
    insurance_age = profile.get("insurance_age")
    age_range = match_profile.get("insurance_age_range", {})
    age_range_match = (
        isinstance(insurance_age, (int, float))
        and age_range
        and age_range.get("min", 0) <= insurance_age <= age_range.get("max", 100)
    )
    if age_range_match or (chosen(profile_age_group) and profile_age_group in product.get("age_groups", [])):
        add("고객 기본정보", 4, f"{profile_age_group} 대상 범위")
    if chosen(profile.get("gender")) and profile["gender"] in match_profile.get("genders", []):
        add("고객 기본정보", 2, f"{profile['gender']} 가입 조건")
    if chosen(family_status) and family_status in match_profile.get("family_types", []):
        add("고객 기본정보", 4, f"{family_status} 대상")
    if chosen(profile.get("dependents")) and profile["dependents"] in match_profile.get("dependents", []):
        add("고객 기본정보", 2, f"부양가족 {profile['dependents']} 조건")
    if chosen(profile.get("occupation_risk")) and profile["occupation_risk"] in match_profile.get("occupation_risks", []):
        add("고객 기본정보", 3, f"{profile['occupation_risk']} 직업군 고려")

    purposes = match_profile.get("purposes", [])
    if chosen(profile.get("purpose")) and profile["purpose"] in purposes:
        add("가입 목적·관심 보장", 8, f"{profile['purpose']} 목적에 적합")
    supported_concerns = product.get("concerns", product["coverage"])
    concern_matches = [item for item in selected_concerns if item in supported_concerns]
    if concern_matches:
        add("가입 목적·관심 보장", min(12, 4 * len(concern_matches)), "관심 보장(" + ", ".join(concern_matches) + ") 포함")
    if chosen(profile.get("criteria")) and profile["criteria"] in match_profile.get("criteria", []):
        add("가입 목적·관심 보장", 5, f"중요 기준({profile['criteria']}) 부합")

    if chosen(profile.get("coverage_amount")) and profile["coverage_amount"] in match_profile.get("coverage_amount_bands", []):
        add("보험료·계약조건", 2, f"희망 보장금액({profile['coverage_amount']}) 구간")
    budget_aliases = {
        "3만원 이하": ["5만 원 이하"],
        "3만~5만원": ["5만 원 이하", "5만~8만 원"],
        "5만~8만원": ["5만~8만 원"],
        "8만~12만원": ["8만 원 이상"],
        "12만원 이상": ["8만 원 이상"],
    }
    product_budget_bands = product.get("budget_bands", [])
    budget_match = chosen(budget) and (
        budget in product_budget_bands
        or any(band in product_budget_bands for band in budget_aliases.get(budget, []))
    )
    if budget_match:
        add("보험료·계약조건", 7, f"예산({budget}) 범위")
    for field, label, points in [
        ("payment_period", "납입기간", 4),
        ("insurance_period", "보험기간", 4),
        ("renewal_preference", "갱신 선호", 4),
        ("refund_preference", "해약환급금 선호", 2),
        ("premium_exemption", "납입면제 중요도", 2),
    ]:
        value = profile.get(field)
        if chosen(value) and value in match_profile.get(field + "s", match_profile.get(field, [])):
            add("보험료·계약조건", points, f"{label}({value}) 부합")

    if existing == "있음":
        if existing in match_profile.get("existing_statuses", []):
            add("기존 보험 현황", 1, "기존 보험 보유 상태 고려")
        if chosen(profile.get("existing_count")) and profile["existing_count"] in match_profile.get("existing_counts", []):
            add("기존 보험 현황", 2, f"가입 보험 수({profile['existing_count']}) 조건")
        existing_plan = profile.get("existing_plan")
        if chosen(existing_plan) and existing_plan in match_profile.get("existing_plans", []):
            add("기존 보험 현황", 4, f"기존 보험 {existing_plan} 목적에 적합")
        existing_concerns = set(profile.get("existing_concerns") or [])
        existing_concern_labels = set(match_profile.get("existing_concerns", supported_concerns))
        overlap = existing_concerns.intersection(existing_concern_labels)
        if overlap:
            add("기존 보험 현황", min(4, 2 * len(overlap)), "보유 보장과 상품 보장 보완 가능")
        if chosen(profile.get("existing_renewal")) and profile["existing_renewal"] in match_profile.get("existing_renewals", []):
            add("기존 보험 현황", 2, "기존 갱신형 보험 현황 고려")
        if chosen(profile.get("current_premium")) and profile["current_premium"] in match_profile.get("current_premium_bands", []):
            add("기존 보험 현황", 2, "현재 보험료 구간 고려")
    elif existing == "없음":
        if existing in match_profile.get("existing_statuses", []):
            add("기존 보험 현황", 1, "기존 보험이 없는 고객 조건 고려")
        if "첫 보험" in purposes:
            add("기존 보험 현황", 4, "첫 보험 가입자 대상")

    # 설문 라벨·우선순위 계산은 기존 taxonomy를 그대로 사용한다.
    priority_map = {item.get("label"): item for item in (survey_priorities or [])}
    related_pains = product.get("pain_points", PRODUCT_PAIN_POINTS.get(product["product_id"], []))
    related_score = sum(priority_map.get(label, {}).get("priority_score", 0) for label in related_pains)
    if related_score > 0:
        survey_points = min(10, round(related_score * 5))
        add("설문 대응", survey_points, "")
        top_related = [label for label in related_pains if label in priority_map][:2]
        reasons.append("설문 우선 불편 대응: " + ", ".join(top_related))

    # 자유 텍스트는 Gemini가 허용 라벨로 구조화한 결과만 사용하고, 최대 10점으로 제한한다.
    llm = llm_analysis or {}
    llm_concerns = [x for x in llm.get("concerns", []) if x in supported_concerns]
    llm_criteria = [x for x in llm.get("criteria", []) if x in match_profile.get("criteria", [])]
    llm_purposes = [x for x in llm.get("purposes", []) if x in purposes]
    llm_bonus = min(10, 3 * len(set(llm_concerns)) + 2 * len(set(llm_criteria)) + 2 * len(set(llm_purposes)))
    if llm_bonus:
        add("추가 입력 관련성", llm_bonus, "추가 설명과 상품 조건의 관련성 반영")
    if llm.get("risk_flags"):
        reasons.append("상담 확인 필요: " + ", ".join(llm["risk_flags"][:2]))
    if not reasons:
        reasons.append("상품 기본 정보 비교 대상")
    return score, reasons, breakdown


def recommend_products(
    age_group: str,
    concern: str,
    budget: str,
    existing: str,
    family_status: str,
    customer_type: str,
    products: list[dict],
    survey_priorities: list[dict] | None = None,
    customer_profile: dict | None = None,
    llm_analysis: dict | None = None,
) -> list[dict]:
    scored = []
    for product in products:
        score, reasons, breakdown = score_product(
            product, age_group, concern, budget, existing, family_status,
            customer_type, survey_priorities, customer_profile, llm_analysis,
        )
        enriched = {
            **product,
            "_match_score": score,
            "_match_reasons": reasons,
            "_score_breakdown": breakdown,
            "_hard_score": sum(
                value for key, value in breakdown.items()
                if key not in ("설문 대응", "추가 입력 관련성")
            ),
            "_llm_bonus": breakdown["추가 입력 관련성"],
            "_survey_points": breakdown["설문 대응"],
        }
        enriched["_survey_alignment"] = sum(
            item.get("priority_score", 0)
            for item in (survey_priorities or [])
            if item.get("label") in product.get(
                "pain_points", PRODUCT_PAIN_POINTS.get(product["product_id"], [])
            )
        )
        selected_concerns = (customer_profile or {}).get("concerns") or [concern]
        enriched["_concern_match"] = sum(
            int(item in product.get("concerns", product["coverage"]))
            for item in selected_concerns
        )
        enriched["_age_match"] = int(age_group in product.get("age_groups", []))
        enriched["_budget_match"] = int(
            budget in product.get("budget_bands", [])
            or any(
                band in product.get("budget_bands", [])
                for band in {
                    "3만원 이하": ["5만 원 이하"],
                    "3만~5만원": ["5만 원 이하", "5만~8만 원"],
                    "5만~8만원": ["5만~8만 원"],
                    "8만~12만원": ["8만 원 이상"],
                    "12만원 이상": ["8만 원 이상"],
                }.get(budget, [])
            )
        )
        enriched["_survey_pain_points"] = [
            item for item in (survey_priorities or [])
            if item.get("label") in product.get("pain_points", PRODUCT_PAIN_POINTS.get(product["product_id"], []))
        ][:3]
        scored.append((score, enriched))
    return [
        product for _, product in sorted(scored, key=lambda item: product_sort_key(item[1]))
    ]


def calculate_core_label_score(product: dict, customer_profile: dict) -> tuple[int, list[str]]:
    """간소화된 핵심 입력을 상품 라벨과 비교해 최대 70점을 계산한다."""
    score = 0
    reasons: list[str] = []
    age = customer_profile.get("insurance_age")
    age_range = product.get("match_profile", {}).get("insurance_age_range", {})
    if isinstance(age, (int, float)) and age_range and age_range.get("min", 0) <= age <= age_range.get("max", 100):
        score += 15
        reasons.append("보험나이 조건에 부합합니다.")
    concerns = [item for item in (customer_profile.get("concerns") or []) if item not in ("", "선택")]
    concern_matches = [item for item in concerns if item in product.get("concerns", product.get("coverage", []))]
    if concern_matches:
        score += min(20, 10 * len(concern_matches))
        reasons.append("관심 보장(" + ", ".join(concern_matches) + ")을 포함합니다.")
    budget = customer_profile.get("budget")
    aliases = {
        "3만원 이하": ["5만 원 이하"], "3만~5만원": ["5만 원 이하", "5만~8만 원"],
        "5만~8만원": ["5만~8만 원"], "8만~12만원": ["8만 원 이상"], "12만원 이상": ["8만 원 이상"],
    }
    if budget not in (None, "", "선택") and (budget in product.get("budget_bands", []) or any(
        band in product.get("budget_bands", []) for band in aliases.get(budget, [])
    )):
        score += 15
        reasons.append("희망 예산 범위에서 비교할 수 있습니다.")
    family = customer_profile.get("family_status")
    if family not in (None, "", "선택") and family in product.get("match_profile", {}).get("family_types", []):
        score += 10
        reasons.append("가족 구성과 관련된 대상 조건을 포함합니다.")
    existing = customer_profile.get("existing")
    if existing in product.get("match_profile", {}).get("existing_statuses", []):
        score += 10
        reasons.append("기존 보험 보유 여부와 상품 대상 조건이 맞습니다.")
    return min(70, score), reasons


def calculate_survey_score(product: dict, survey_priorities: list[dict]) -> int:
    pain_points = product.get("pain_points", PRODUCT_PAIN_POINTS.get(product.get("product_id"), []))
    alignment = sum(float(item.get("priority_score", 0)) for item in (survey_priorities or []) if item.get("label") in pain_points)
    return min(10, max(0, round(alignment * 5)))


def build_base_recommendations(products: list[dict], customer_profile: dict, survey_priorities: list[dict]) -> list[dict]:
    """Gemini 호출 전 화면에 전달할 핵심 조건·설문 기반 점수를 만든다."""
    result = []
    for product in products:
        hard_score, reasons = calculate_core_label_score(product, customer_profile)
        survey_score = calculate_survey_score(product, survey_priorities)
        result.append({
            **product,
            "_hard_score": hard_score,
            "_survey_points": survey_score,
            "_llm_bonus": 0,
            "_match_score": hard_score + survey_score,
            "_match_reasons": reasons or ["선택한 핵심 조건과 상품 정보를 비교합니다."],
            "_survey_alignment": survey_score,
            "_concern_match": len([item for item in (customer_profile.get("concerns") or []) if item in product.get("concerns", [])]),
            "_age_match": int("보험나이 조건에 부합합니다." in reasons),
            "_budget_match": int("희망 예산 범위에서 비교할 수 있습니다." in reasons),
            "_survey_pain_points": [item for item in (survey_priorities or []) if item.get("label") in product.get("pain_points", [])][:3],
        })
    return sorted(result, key=product_sort_key)


def recommend_products_with_gemini(
    products: list[dict],
    customer_profile: dict,
    survey_priorities: list[dict],
    fallback: list[dict],
    use_llm: bool = True,
) -> tuple[list[dict], str]:
    """고객의 전체 입력을 Gemini가 종합해 상품을 정렬한다.

    LLM은 제공된 상품 데이터 안에서만 판단하고, 가입 가능성이나 보험금 지급 여부는
    판단하지 않는다. 응답 형식이 잘못되거나 API가 실패하면 기존 규칙 추천을 사용한다.
    """
    client = get_gemini_client() if use_llm else None
    if not client:
        return fallback, "기본 규칙 추천 · Gemini 미사용"

    safe_profile = {key: value for key, value in customer_profile.items() if key != "precheck"}
    base_by_id = {
        str(product.get("product_id")): {
            "hard_score": int(product.get("_hard_score", 0)),
            "survey_score": int(product.get("_survey_points", 0)),
            "base_reasons": product.get("_match_reasons", []),
            "survey_alignment": product.get("_survey_alignment", 0),
            "concern_match": product.get("_concern_match", 0),
            "age_match": product.get("_age_match", 0),
            "budget_match": product.get("_budget_match", 0),
            "survey_pain_points": product.get("_survey_pain_points", []),
        }
        for product in fallback
    }
    product_context = [
        {
            "base_scores": base_by_id.get(str(product.get("product_id")), {}),
            **{key: product.get(key) for key in [
                "product_id", "name", "type", "target", "concerns", "coverage", "strengths",
                "exclusions", "renewal", "premium_example", "caution", "pain_points",
                "match_profile", "source", "source_date",
            ] if key in product},
        }
        for product in products
    ]
    survey_context = [
        {key: item.get(key) for key in [
            "label", "ratio", "avg_severity", "priority_score", "priority_reason"
        ]}
        for item in (survey_priorities or [])[:8]
    ]
    instructions = (
        "당신은 한화생명 보험상품 정보 탐색을 돕는 추천 도우미입니다. "
        "고객 입력, 추가 자유문장, 설문 우선순위, 제공된 상품 데이터만 근거로 상품을 정렬하세요. "
        "상품 데이터에 없는 보장·보험료·조건을 만들지 말고, 가입 가능성·인수 심사·최종 가입 결정을 판단하지 마세요. "
        "핵심 조건 점수와 설문 점수는 이미 계산되어 있으므로 이를 존중하고, 추가 상황 해석 점수만 0~20점으로 산정하세요. "
        "반드시 JSON 객체 하나만 반환하세요."
    )
    prompt = (
        f"고객 입력:\n{json.dumps(safe_profile, ensure_ascii=False, indent=2)}\n\n"
        f"설문 우선순위(무엇을 먼저 설명할지 결정하는 참고자료):\n{json.dumps(survey_context, ensure_ascii=False, indent=2)}\n\n"
        f"비교 가능한 상품 목록:\n{json.dumps(product_context, ensure_ascii=False, indent=2)}\n\n"
        "다음 형식으로만 답하세요. recommendations에는 상품 목록의 product_id만 사용하고, "
        "모든 상품을 포함하세요. additional_score는 추가 상황 해석 점수(0~20)입니다. "
        "총점은 핵심 조건 점수(최대 70)+설문 대응(최대 10)+additional_score(최대 20)으로 계산합니다. "
        "reasons는 고객 입력과 상품 데이터의 연결을 2~3개, cautions는 상품 데이터에 있는 확인사항을 1~2개 작성하세요.\n"
        '{"recommendations":[{"product_id":"P001","additional_score":17,'
        '"reasons":["..."],"cautions":["..."]}]}'
    )
    try:
        recommendation_model = os.getenv("GEMINI_RECOMMEND_MODEL") or os.getenv("GEMINI_MODEL")
        raw, used_model = generate_with_gemini(
            client, instructions, prompt,
            preferred_model=recommendation_model,
            fallback_models=["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
        )
        parsed = parse_json_object(raw)
        rows = parsed.get("recommendations", [])
        if not isinstance(rows, list):
            raise ValueError("recommendations 배열이 없습니다.")
        by_id = {str(product.get("product_id")): product for product in products}
        enriched: list[dict] = []
        seen: set[str] = set()
        for row in rows:
            if not isinstance(row, dict):
                continue
            product_id = str(row.get("product_id", ""))
            if product_id not in by_id or product_id in seen:
                continue
            seen.add(product_id)
            try:
                llm_bonus = max(0, min(20, int(float(row.get("additional_score", 0)))))
            except (TypeError, ValueError):
                continue
            base = base_by_id.get(product_id, {"hard_score": 0, "survey_score": 0})
            ai_score = min(100, int(base.get("hard_score", 0)) + int(base.get("survey_score", 0)) + llm_bonus)
            level = "높음" if ai_score >= 80 else "보통" if ai_score >= 55 else "낮음"
            reasons = row.get("reasons", [])
            cautions = row.get("cautions", [])
            if isinstance(reasons, str): reasons = [reasons]
            if isinstance(cautions, str): cautions = [cautions]
            reasons = [str(value)[:180] for value in reasons if str(value).strip()][:3]
            cautions = [str(value)[:180] for value in cautions if str(value).strip()][:2]
            if not reasons:
                reasons = ["고객 입력과 제공된 상품 정보를 함께 검토한 결과입니다."]
            enriched.append({
                **by_id[product_id],
                "_match_score": ai_score,
                "_hard_score": int(base.get("hard_score", 0)),
                "_survey_points": int(base.get("survey_score", 0)),
                "_llm_bonus": llm_bonus,
                "_match_reasons": list(base.get("base_reasons", [])) + reasons,
                "_survey_alignment": base.get("survey_alignment", 0),
                "_concern_match": base.get("concern_match", 0),
                "_age_match": base.get("age_match", 0),
                "_budget_match": base.get("budget_match", 0),
                "_survey_pain_points": base.get("survey_pain_points", []),
                "_ai_score": ai_score,
                "_recommendation_level": level,
                "_ai_reasons": reasons,
                "_ai_cautions": cautions,
                "_recommendation_mode": f"Gemini AI 종합 추천 · {used_model}",
            })
        if len(enriched) != len(products):
            missing = [product for product in products if product["product_id"] not in seen]
            enriched.extend({
                **product,
                "_match_score": int(base_by_id.get(product["product_id"], {}).get("hard_score", 0)) + int(base_by_id.get(product["product_id"], {}).get("survey_score", 0)),
                "_hard_score": int(base_by_id.get(product["product_id"], {}).get("hard_score", 0)),
                "_survey_points": int(base_by_id.get(product["product_id"], {}).get("survey_score", 0)),
                "_llm_bonus": 0,
                "_ai_score": int(base_by_id.get(product["product_id"], {}).get("hard_score", 0)) + int(base_by_id.get(product["product_id"], {}).get("survey_score", 0)),
                "_recommendation_level": "AI 추가 분석 없음",
                "_ai_reasons": ["AI 응답에서 별도 추천 근거가 제시되지 않은 상품입니다."],
                "_ai_cautions": [product.get("caution", "상품 설명서의 세부 조건을 확인하세요.")],
                "_recommendation_mode": f"Gemini AI 종합 추천 · {used_model}",
            } for product in missing)
        return sorted(enriched, key=lambda item: (-item.get("_ai_score", 0), item.get("name", ""))), f"Gemini AI 종합 추천 · {used_model}"
    except Exception as exc:
        detail = str(exc).replace("\n", " ")[:160]
        return fallback, f"Gemini 추천 실패 · 기본 규칙 추천 ({type(exc).__name__}: {detail})"


def product_sort_key(product: dict) -> tuple:
    """추천·비교 화면에서 공통으로 사용하는 상품 정렬 기준."""
    return (
        -int(product.get("_match_score", 0)),
        -float(product.get("_survey_alignment", 0)),
        -int(product.get("_concern_match", 0)),
        -int(product.get("_age_match", 0)),
        -int(product.get("_budget_match", 0)),
        product.get("name", ""),
    )


def answer_question(question: str, selected: list[dict], use_llm: bool = True) -> tuple[str, str, str]:
    intent = classify_question(question)
    client = get_gemini_client() if use_llm else None

    if client:
        product_context = json.dumps(selected, ensure_ascii=False, indent=2)
        instructions = (
            "당신은 한화생명 보험상품 정보를 쉽게 설명하는 안내 도우미입니다. "
            "제공된 상품 데이터에 있는 내용만 사용하고, 데이터에 없는 보험료·보장·가입 가능 여부는 추측하지 마세요. "
            "고객에게 보험 가입을 최종 권유하거나 가입 판단을 대신하지 말고, 필요한 경우 전문 상담을 안내하세요. "
            "답변은 한국어로 짧고 명확하게 작성하며, 핵심 답변·주의사항·근거를 포함하세요."
        )
        prompt = f"고객 질문:\n{question}\n\n참고할 상품 데이터:\n{product_context}"
        try:
            response_text, used_model = generate_with_gemini(client, instructions, prompt)
            return intent, response_text, f"Gemini API · {used_model}"
        except Exception as exc:
            detail = str(exc).replace("\n", " ")[:240]
            fallback_notice = (
                f"Gemini 호출에 실패해 기본 답변으로 전환했습니다: "
                f"{type(exc).__name__} · {detail}"
            )
        
    if intent == "상품 비교":
        lines = ["선택한 상품을 같은 기준으로 비교하면 다음과 같습니다.", ""]
        for product in selected:
            lines.append(
                f"- **{product['name']}**: {product['renewal']}, "
                f"{', '.join(product['coverage'])}, {product['premium_example']}"
            )
        lines.append("\n상품의 장단점은 고객의 건강 상태와 계약 조건에 따라 달라질 수 있으므로 상담 시 세부 조건을 확인하세요.")
        return intent, "\n".join(lines), fallback_notice if client else "기본 템플릿"

    product = selected[0] if selected else None
    if intent == "갱신 조건":
        text = "갱신형은 일정 기간마다 계약을 갱신하는 방식으로, 갱신 시점에 보험료가 변동될 수 있습니다."
    elif intent == "보장 제외·주의사항":
        text = "보장 제외 조건은 상품별 약관에 따라 다릅니다. 기존 질환, 면책기간, 고지 의무를 반드시 확인해야 합니다."
    elif intent == "보장 설명":
        text = "보장 내용은 상품에 따라 다르며, 진단 기준과 지급 조건을 함께 확인해야 합니다."
    elif intent == "상담 준비":
        text = "상담 시 갱신 여부, 보장 제외 조건, 보험료 변동 가능성, 중도 해지 조건을 확인해 보세요."
    else:
        text = "보험 용어는 상품 설명서의 정의와 보장 조건을 함께 확인하는 것이 좋습니다."

    if product:
        text += f"\n\n현재 선택 상품: **{product['name']}**\n근거: {product['source']} ({product['source_date']})"
    return intent, text, fallback_notice if client else "기본 템플릿"


def refine_answer_with_feedback(
    question: str,
    previous_answer: str,
    feedback: str,
    selected: list[dict],
    customer_context: dict,
    use_llm: bool = True,
) -> tuple[str, str]:
    """사용자 피드백과 기존 답변을 바탕으로 답변을 다시 작성한다."""
    client = get_gemini_client() if use_llm else None
    if client:
        instructions = (
            "당신은 한화생명 보험상품 안내 답변을 개선하는 도우미입니다. "
            "사용자의 피드백을 가장 우선해 기존 답변을 새로 작성하세요. "
            "제공된 보험상품 데이터에 있는 내용만 사용하고, 가입 가능 여부나 보장 금액을 추측하지 마세요. "
            "답변에는 핵심 설명, 주의사항, 근거를 포함하고 실제 가입 판단은 전문 상담으로 안내하세요."
        )
        prompt = (
            f"고객 질문:\n{question}\n\n"
            f"기존 답변:\n{previous_answer}\n\n"
            f"사용자 피드백:\n{feedback}\n\n"
            f"고객 상황:\n{json.dumps(customer_context, ensure_ascii=False, indent=2)}\n\n"
            f"참고 보험상품 데이터:\n{json.dumps(selected, ensure_ascii=False, indent=2)}"
        )
        try:
            revised, used_model = generate_with_gemini(client, instructions, prompt)
            return revised, f"피드백 반영 Gemini API · {used_model}"
        except Exception as exc:
            detail = str(exc).replace("\n", " ")[:160]
            mode = f"Gemini 피드백 반영 실패 · {type(exc).__name__}: {detail}"
    else:
        mode = "LLM 미사용 · 기본 피드백 반영"

    fallback = (
        f"{previous_answer}\n\n"
        f"---\n**사용자 피드백 반영 요청:** {feedback}\n\n"
        "현재는 AI 재생성을 사용할 수 없어 기존 답변과 피드백을 함께 표시합니다. "
        "Gemini 연결 후 다시 시도해 주세요."
    )
    return fallback, mode


def recommend_questions(
    age_group: str,
    concern: str,
    budget: str,
    existing: str,
    selected: list[dict],
    family_status: str = "",
    customer_type: str = "",
    survey_priorities: list[dict] | None = None,
    use_llm: bool = True,
    customer_profile: dict | None = None,
    llm_analysis: dict | None = None,
) -> tuple[list[str], str]:
    """고객 상황과 상품 정보를 바탕으로 상담 전 질문을 생성한다."""
    question_templates = {
        "전문용어 이해": "이 상품 설명서의 핵심 용어를 제 상황에 맞게 쉽게 설명해 주실 수 있나요?",
        "보장 범위 이해": "제가 관심 있는 {concern} 보장은 어떤 조건에서 얼마까지 받을 수 있나요?",
        "상품 보장 비교": "비교한 상품들의 보장 범위와 지급 조건 중 제 상황에서 가장 큰 차이는 무엇인가요?",
        "보험료 비교": "월 보험료 차이가 보장 범위와 어떤 관계가 있는지 설명해 주실 수 있나요?",
        "보장 제외 조건": "기존 질환, 면책기간, 고지 의무 때문에 보장에서 제외될 수 있는 조건은 무엇인가요?",
        "갱신 조건": "갱신 주기와 갱신 시 보험료가 변동되는 조건을 확인할 수 있을까요?",
        "상담 질문 준비": "가입 전에 제가 반드시 확인해야 하는 질문은 무엇인가요?",
        "상담 정보 전달": "제 상황과 기존 보험을 상담사에게 어떻게 정리해서 전달하면 좋을까요?",
    }
    ranked_labels = [item.get("label") for item in (survey_priorities or [])]
    fallback = [
        question_templates[label].format(concern=concern)
        for label in ranked_labels
        if label in question_templates
    ][:4]
    if len(fallback) < 3:
        fallback.extend([
            "갱신 시 보험료가 얼마나 변동될 수 있나요?",
            "상품의 보장 제외 조건은 무엇인가요?",
            "중도 해지 시 환급금은 어떻게 계산되나요?",
        ])
        fallback = list(dict.fromkeys(fallback))[:4]
    client = get_gemini_client() if use_llm else None
    if not client:
        return fallback, "기본 질문 목록"

    safe_profile = {
        key: value for key, value in (customer_profile or {}).items()
        if key != "precheck"
    }
    product_context = json.dumps(selected, ensure_ascii=False, indent=2)
    instructions = (
        "당신은 보험상품 상담 준비를 돕는 도우미입니다. "
        "고객이 상담사에게 물어볼 질문 4개를 한국어로 생성하세요. "
        "고객 상황과 제공된 상품 데이터에 근거하고, 가입을 권유하거나 답을 단정하지 마세요. "
        "반드시 질문만 4줄로 출력하고, 각 줄은 물음표(?)로 끝내세요. 번호·불릿·설명은 붙이지 마세요."
    )
    prompt = (
        f"고객 상황: 연령대={age_group}, 관심 보장={concern}, "
        f"월 예산={budget}, 기존 보험={existing}, 가족 구성={family_status}, "
        f"고객 유형={customer_type}\n\n"
        f"확장 고객 입력:\n{json.dumps(safe_profile, ensure_ascii=False, indent=2)}\n\n"
        f"추가 설명 분석 결과:\n{json.dumps(llm_analysis or {}, ensure_ascii=False, indent=2)}\n\n"
        f"참고 상품 데이터:\n{product_context}\n\n"
        "이전 고객 설문에서 계산한 우선순위 페인포인트(응답 비율·심각도·현재 고객과의 관련성을 반영):\n"
        f"{json.dumps((survey_priorities or [])[:5], ensure_ascii=False, indent=2)}\n\n"
        "질문은 우선순위가 높은 페인포인트를 먼저 다루되, 상품 데이터에 없는 내용을 전제로 하지 마세요."
    )
    failure_detail = ""
    try:
        question_model = os.getenv("GEMINI_QUESTION_MODEL", "gemini-3.5-flash-lite")
        raw, used_model = generate_with_gemini(
            client,
            instructions,
            prompt,
            preferred_model=question_model,
            fallback_models=["gemini-3.1-flash-lite", "gemini-2.5-flash-lite"],
        )
        questions = []
        # 모델이 줄바꿈 대신 한 문단으로 답하는 경우도 안전하게 나눈다.
        for line in re.split(r"[\r\n]+|(?<=[?？])\s+", raw):
            cleaned = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
            is_question = any(mark in cleaned for mark in ["?", "？"]) or bool(
                re.search(r"(까요|나요|습니까|할까|무엇인가요|어떻게 해야)\s*$", cleaned)
            )
            if is_question and len(cleaned) >= 8:
                questions.append(cleaned)
        questions = list(dict.fromkeys(questions))[:4]
        if len(questions) >= 3:
            return questions, f"Gemini API · {used_model}"
        failure_detail = "응답에서 질문 3개 이상을 인식하지 못했습니다."
    except Exception as exc:
        failure_detail = f"{type(exc).__name__}: {str(exc).replace(chr(10), ' ')[:160]}"
    return fallback, f"Gemini 실패 · 기본 질문 목록 ({failure_detail})"


def render_product_card(product: dict) -> None:
    st.markdown(f"### {product['name']}")
    st.caption(f"{product['type']} · {product['target']}")
    st.write(f"**주요 보장:** {', '.join(product['coverage'])}")
    if product.get("strengths"):
        st.write("**특징:** " + ", ".join(product["strengths"]))
    st.write(f"**갱신 여부:** {product['renewal']}  ·  **보험료 예시:** {product['premium_example']}")
    match_score = int(product.get("_match_score", 0))
    st.write(f"**AI 추천도:** {match_score}점")
    st.progress(
        min(100, max(0, match_score)) / 100,
        text=f"{match_score} / 100",
    )
    st.caption(
        f"핵심 조건 {product.get('_hard_score', 0)}/70 · "
        f"설문 대응 {product.get('_survey_points', 0)}/10 · "
        f"AI 상황 해석 {product.get('_llm_bonus', 0)}/20 · "
        f"{product.get('_recommendation_mode', '분석 대기')}"
    )
    from html import escape

    st.markdown("**이런 점에서 고객님과 잘 맞아요**")
    # Each section is one Streamlit element, avoiding inter-element gaps per bullet.
    guidance_points = product.get("_ai_reasons") or build_guidance_points(product)
    guidance_items = "".join(
        f'<div class="product-guidance-item">{escape(str(point))}</div>'
        for point in guidance_points
    )
    st.markdown(
        '<div class="product-guidance"><div class="product-guidance-list">' + guidance_items + '</div></div>',
        unsafe_allow_html=True,
    )
    st.caption("예산 일치는 등록된 안내 구간 기준이며, 예시 보험료는 실제 견적이 아닙니다.")
    st.markdown("**가입 전에 이것은 꼭 확인하세요**")
    caution_points = product.get("_ai_cautions") or build_caution_points(product)
    if caution_points:
        caution_items = "".join(
            f'<div class="product-caution-item">{escape(point)}</div>'
            for point in caution_points
        )
        st.markdown(
            '<div class="product-caution"><div class="product-caution-list">' + caution_items + '</div></div>',
            unsafe_allow_html=True,
        )
    # questions = build_survey_questions(product)
    # if questions:
    #     st.markdown("**설문에서 자주 나타난 불편과 고객 조건을 함께 고려한 확인 질문입니다.**")
    #     for item in questions:
    #         if st.button(
    #             item["text"],
    #             key=f"product_question_{product['product_id']}_{item['label']}",
    #             use_container_width=True,
    #             help="이 상품의 정보를 기준으로 아래 AI 답변 영역에서 설명합니다.",
    #         ):
    #             st.session_state.pending_product_question = {
    #                 "question": item["question"],
    #                 "product_id": product["product_id"],
    #             }
    #             st.success("아래 '4. 상담 전 질문 추천 및 AI 설명'에서 답변을 확인하세요.")

    st.caption(f"근거: {product['source']} / 기준일 {product['source_date']}")


def render_responsive_dataframe(
    data: pd.DataFrame,
    column_config: dict | None = None,
    row_height: int | None = None,
) -> None:
    """스크롤바 없이 화면 폭에 맞춰 긴 셀을 줄바꿈하는 표를 렌더링한다."""
    del column_config, row_height  # HTML 표에서는 CSS가 폭·행 높이를 자동 처리한다.
    display_data = data.copy()
    for column in display_data.columns:
        display_data[column] = display_data[column].map(
            lambda value: ", ".join(map(str, value)) if isinstance(value, (list, tuple)) else value
        )
    table_html = display_data.to_html(
        index=False,
        escape=True,
        classes="hanwha-table",
        border=0,
    )
    st.markdown(f'<div class="hanwha-table-wrap">{table_html}</div>', unsafe_allow_html=True)


# FastAPI와 Streamlit이 동일한 추천·질문·답변 도메인 로직을 사용하도록
# 공통 모듈을 화면 실행 직전에 연결한다. 기존 함수 정의는 Streamlit
# 호환성을 위해 남겨 두되 실제 실행은 core.logic을 사용한다.
from core import logic as shared_logic


def _shared_rank_survey_priorities(analysis, age_group, concern, budget, existing, family_status, customer_type):
    profile = {
        "age_group": age_group,
        "concerns": [concern] if concern else [],
        "budget": budget,
        "existing": existing,
        "family_status": family_status,
        "customer_type": customer_type,
    }
    return shared_logic.rank_survey_priorities(analysis, profile)


def _shared_recommend_products_with_gemini(products, customer_profile, survey_priorities, fallback=None, use_llm=True):
    return shared_logic.recommend_products_with_gemini(products, customer_profile, survey_priorities, use_llm=use_llm)


def _shared_recommend_questions(age_group, concern, budget, existing, selected, family_status="", customer_type="", survey_priorities=None, use_llm=True, customer_profile=None, llm_analysis=None):
    profile = dict(customer_profile or {})
    profile.update({"age_group": age_group, "concerns": profile.get("concerns") or ([concern] if concern else []), "budget": budget, "existing": existing, "family_status": family_status, "customer_type": customer_type})
    return shared_logic.recommend_questions(profile, selected, survey_priorities or [], use_llm=use_llm)


rank_survey_priorities = _shared_rank_survey_priorities
recommend_products_with_gemini = _shared_recommend_products_with_gemini
recommend_questions = _shared_recommend_questions
answer_question = shared_logic.answer_question

survey = load_survey()
products = load_products()
analysis = load_analysis()

st.markdown(
    """
    <div class="hanwha-kicker">고객 경험 혁신</div>
    <div class="hanwha-hero">
        <div class="brand">HANWHA · LIFE</div>
        <div class="title">한화생명 Easy Guide AI</div>
        <div class="subtitle">설문 데이터에서 발견한 보험상품 이해·비교 불편을 해결하는 고객 안내 프로토타입</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("프로토타입용 가상 설문 및 상품 데이터 사용 · 실제 가입 판단을 대신하지 않습니다.")

with st.sidebar:
    st.header("고객 상황 입력")
    st.markdown("#### 1. 고객 기본정보")
    insurance_age_input = st.number_input(
        "보험나이", min_value=0, max_value=100, value=20, step=1
    )
    insurance_age = int(insurance_age_input) if insurance_age_input is not None else None
    age_group = age_to_group(insurance_age) if insurance_age is not None else ""
    family_status = st.selectbox("가족 구성", ["선택", "1인 가구", "부부", "자녀 있음", "부모 부양", "기타"])
    concerns = st.multiselect(
        "관심 보장(복수 선택)",
        ["암", "뇌혈관", "심혈관", "질병", "입원", "수술", "상해", "사망", "간병"],
        default=[],
    )
    concern = concerns[0] if concerns else ""
    budget = st.selectbox(
        "월 납입 예산", ["선택", "3만원 이하", "3만~5만원", "5만~8만원", "8만~12만원", "12만원 이상"]
    )
    existing = st.selectbox("기존 보험 가입 여부", ["선택", "있음", "없음", "잘 모르겠음"])
    gender = dependents = occupation_risk = purpose = criteria = coverage_amount = "선택"
    payment_period = insurance_period = renewal_preference = refund_preference = premium_exemption = "선택"
    existing_count = current_premium = existing_renewal = existing_plan = "선택"
    existing_concerns = []
    precheck = {}
    additional_note = st.text_area(
        "추가 상황·희망 조건 (선택)",
        placeholder="예: 야외 작업이 많고 가족력 때문에 암 보장을 꼼꼼히 확인하고 싶어요. 비갱신형과 90세 보장을 우선하고 싶습니다.",
        help="가입 목적, 직업 위험도, 성별, 희망 보장금액·기간, 갱신·환급금 선호 등 원하는 내용을 자유롭게 적으면 AI가 추천에 반영합니다.",
    )
    if st.button("AI 분석하기", use_container_width=True):
        if not concerns or budget == "선택" or existing == "선택" or family_status == "선택":
            st.warning("보험나이 외의 핵심 항목도 선택한 뒤 분석해 주세요.")
        else:
            submitted_profile = {
                "insurance_age": insurance_age,
                "age_group": age_group,
                "family_status": family_status,
                "concerns": concerns,
                "budget": budget,
                "existing": existing,
                "additional_note": additional_note,
            }
            submitted_type = infer_customer_type(age_group, concerns[0], budget, existing, family_status)
            submitted_priorities = rank_survey_priorities(
                analysis, age_group, concerns[0], budget, existing, family_status, submitted_type,
            )
            base_recommendations = build_base_recommendations(products, submitted_profile, submitted_priorities)
            with st.spinner("입력한 고객 상황과 설문 결과를 Gemini가 분석하는 중입니다..."):
                analyzed_products, analysis_mode = recommend_products_with_gemini(
                    products, submitted_profile, submitted_priorities, base_recommendations, use_llm=True,
                )
            st.session_state.analysis_ready = True
            st.session_state.submitted_profile = submitted_profile
            st.session_state.recommended_products = analyzed_products
            st.session_state.recommendation_mode = analysis_mode
            st.session_state.submitted_customer_type = submitted_type
            st.session_state.submitted_survey_priorities = submitted_priorities
            st.success("AI 분석 결과를 갱신했습니다.")

analysis_ready = bool(st.session_state.get("analysis_ready"))
customer_profile = st.session_state.get("submitted_profile", {}) if analysis_ready else {}
age_group = customer_profile.get("age_group", "")
concerns = customer_profile.get("concerns", [])
concern = concerns[0] if concerns else ""
budget = customer_profile.get("budget", "")
existing = customer_profile.get("existing", "")
family_status = customer_profile.get("family_status", "")
insurance_age = customer_profile.get("insurance_age", 20)
additional_note = customer_profile.get("additional_note", "")
customer_type = st.session_state.get("submitted_customer_type", "")
survey_priorities = st.session_state.get("submitted_survey_priorities", [])
recommended = st.session_state.get("recommended_products", []) if analysis_ready else []
llm_note_analysis = {}

st.subheader("1. 설문 기반 고객 불편 분석")
analysis_button_col, analysis_help_col = st.columns([1, 3])
with analysis_button_col:
    if st.button("설문 분석 다시 실행"):
        try:
            with st.spinner("세부 라벨 기준으로 설문을 다시 분석하는 중..."):
                run_analysis()
            load_analysis.clear()
            st.success("분석 결과를 갱신했습니다.")
            st.rerun()
        except Exception as exc:
            st.error(f"분석에 실패했습니다: {type(exc).__name__} · {exc}")
with analysis_help_col:
    st.caption("앱 시작 시에는 저장된 JSON을 재사용하고, 데이터가 바뀐 경우에만 이 버튼으로 재분석합니다.")
metric_cols = st.columns(4)
metric_cols[0].metric("분석 응답 수", f"{len(survey):,}건")
metric_cols[1].metric("평균 불편 심각도", f"{survey['severity'].mean():.1f}/5")
if analysis:
    cluster_df = pd.DataFrame(analysis["clusters"])
    count_top = cluster_df.loc[cluster_df["count"].idxmax()]
    severity_top = cluster_df.loc[cluster_df["avg_severity"].idxmax()]
    metric_cols[2].metric("응답 수 최다 불편", str(count_top["label"]))
    metric_cols[3].metric(
        "가장 높은 평균 심각도", f"{severity_top['label']} ({severity_top['avg_severity']:.1f}/5)"
    )
    taxonomy_count = sum(len(labels) for labels in analysis.get("label_taxonomy", {}).values())
    labeled_count = analysis.get("n_labeled_clusters", len(cluster_df))
    st.caption(f"분석 방법: {analysis['method']} · 세부 라벨 {taxonomy_count}개 · K={analysis['n_clusters']} → 표시 {labeled_count}개(동일 라벨 통합)")
    chart_df = cluster_df[["label", "count"]].rename(columns={"count": "응답 수"}).copy()
    chart_df["차트 라벨"] = chart_df["label"].astype(str).str.replace(" ", "\n", regex=False)
    st.vega_lite_chart(
        chart_df,
        {
            "mark": {"type": "bar", "tooltip": True},
            "encoding": {
                "x": {
                    "field": "차트 라벨",
                    "type": "nominal",
                    "sort": "-y",
                    "axis": {"title": None, "labelAngle": 0, "labelLimit": 160, "labelOverlap": False},
                },
                "y": {
                    "field": "응답 수",
                    "type": "quantitative",
                    "scale": {"domainMin": 0},
                    "axis": {"title": "응답 수", "format": "d"},
                },
                "color": {"value": "#F36F21"},
            },
            "height": 360,
        },
        use_container_width=True,
    )
    with st.expander("세부 라벨·주요 표현 표와 지표 계산식 보기", expanded=False):
        cluster_table = cluster_df[["parent_label", "label", "count", "ratio", "label_confidence", "avg_severity", "top_terms"]].rename(
                columns={"parent_label": "상위 유형", "label": "세부 불편 유형", "count": "응답 수", "ratio": "비율", "label_confidence": "라벨 신뢰도", "avg_severity": "평균 심각도", "top_terms": "주요 표현"}
            )
        render_responsive_dataframe(
            cluster_table,
            column_config={
                "상위 유형": st.column_config.TextColumn(width="medium"),
                "세부 불편 유형": st.column_config.TextColumn(width="medium"),
                "응답 수": st.column_config.NumberColumn(width="small", format="%d"),
                "비율": st.column_config.NumberColumn(width="small", format="%.1f%%"),
                "라벨 신뢰도": st.column_config.NumberColumn(width="small", format="%.2f"),
                "평균 심각도": st.column_config.NumberColumn(width="small", format="%.2f"),
                "주요 표현": st.column_config.TextColumn(width="large"),
            },
        )
        st.markdown("#### 지표 계산식")
        st.markdown(
            """
- **응답 비율** = 해당 세부 라벨 응답 수 ÷ 전체 응답 수
- **평균 심각도** = 해당 라벨 응답의 심각도 합계 ÷ 해당 라벨 응답 수
- **라벨 신뢰도** = 군집 내 대표 라벨 응답 수 ÷ 해당 군집 전체 응답 수
- **설문 우선순위** = 0.50 × 상대 응답 빈도 + 0.30 × (평균 심각도 ÷ 5) + 0.20 × 고객 조건 관련성
            """
        )
        st.markdown(
            """
#### 설문 우선순위를 쉽게 설명하면

- **설문 우선순위:** 여러 고객 불편 중 현재 고객에게 무엇을 먼저 안내할지 정하는 점수입니다.
- **상대 응답 빈도:** 설문에서 가장 많이 나온 불편을 1로 두고, 다른 불편이 그에 비해 얼마나 자주 나왔는지를 나타냅니다. 예를 들어 최대 응답 비율이 20%이고 어떤 불편이 15%라면 상대 응답 빈도는 `15% ÷ 20% = 0.75`입니다.
- **평균 심각도 ÷ 5:** 1-5점으로 조사한 심각도를 0-1 범위로 바꾼 값입니다.
- **고객 조건 관련성:** 현재 고객의 관심 보장, 예산, 기존 보험, 가족 구성 및 고객 유형과 관련 있는 불편이면 1, 아니면 0으로 반영합니다.

따라서 **많이 발생하고, 심각하며, 현재 고객과 관련 있는 불편일수록 우선순위가 높아집니다.**
            """
        )
else:
    fallback_group = survey.groupby("cluster").agg(
        count=("cluster", "size"), avg_severity=("severity", "mean")
    ).reset_index().rename(columns={"cluster": "label"})
    count_top = fallback_group.loc[fallback_group["count"].idxmax()]
    severity_top = fallback_group.loc[fallback_group["avg_severity"].idxmax()]
    metric_cols[2].metric("응답 수 최다 불편", str(count_top["label"]))
    metric_cols[3].metric(
        "가장 높은 평균 심각도", f"{severity_top['label']} ({severity_top['avg_severity']:.1f}/5)"
    )
    st.caption("아직 분석 결과가 없어 생성 데이터의 기준 라벨을 표시합니다. 앱이 분석 패키지를 사용할 수 있는 환경에서 재실행 버튼을 눌러 주세요.")
    fallback_group["차트 라벨"] = fallback_group["label"].astype(str).str.replace(" ", "\n", regex=False)
    st.vega_lite_chart(
        fallback_group,
        {
            "mark": {"type": "bar", "tooltip": True, "color": "#F36F21"},
            "encoding": {
                "x": {"field": "차트 라벨", "type": "nominal", "sort": "-y", "axis": {"title": None, "labelAngle": 0, "labelLimit": 160, "labelOverlap": False}},
                "y": {"field": "count", "type": "quantitative", "scale": {"domainMin": 0}, "axis": {"title": "응답 수", "format": "d"}},
            },
            "height": 360,
        },
        use_container_width=True,
    )

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
st.subheader("2. 고객 유형 및 상품 안내")
if not analysis_ready:
    st.info("왼쪽 패널에서 고객 상황을 입력한 뒤 **AI 분석하기**를 눌러 주세요. 입력 전에는 Gemini를 호출하지 않습니다.")
else:
    st.success(f"자동 분석 결과: **{customer_type}**")
if analysis_ready and survey_priorities:
    top_pains = survey_priorities[:3]
    st.write("고객 조건과 설문 우선순위를 함께 반영해 다음 항목부터 확인하도록 안내합니다.")
    pain_table = pd.DataFrame(
        {
            "우선순위": [str(rank) for rank in range(1, len(top_pains) + 1)],
            "설문 기반 불편": [item["label"] for item in top_pains],
            "응답 비율": [f"{item.get('ratio', 0):.1%}" for item in top_pains],
            "평균 심각도": [f"{item.get('avg_severity', 0):.1f}/5" for item in top_pains],
            "선정 근거": [item["priority_reason"] for item in top_pains],
        }
    )
    render_responsive_dataframe(
        pain_table,
        column_config={
            "우선순위": st.column_config.TextColumn(width="small"),
            "설문 기반 불편": st.column_config.TextColumn(width="medium"),
            "응답 비율": st.column_config.TextColumn(width="small"),
            "평균 심각도": st.column_config.TextColumn(width="small"),
            "선정 근거": st.column_config.TextColumn(width="large"),
        },
    )

if analysis_ready:
    st.caption(f"전체 {len(recommended)}개 예시 상품 중 AI 분석 결과 상위 {min(3, len(recommended))}개를 먼저 표시합니다.")
    display_products = recommended[:3]
    cols = st.columns(len(display_products))
    for col, product in zip(cols, display_products):
        with col:
            with st.container(border=True):
                st.markdown('<span class="product-card-marker"></span>', unsafe_allow_html=True)
                render_product_card(product)

if analysis_ready:
  with st.expander("AI 추천도 계산식과 추천 근거 보기", expanded=False):
    st.markdown(
        """
**AI 추천도** = 핵심 조건 일치(최대 70점) + 설문 대응(최대 10점) + AI 상황 해석(최대 20점)

- **핵심 조건 일치:** 보험나이, 관심 보장, 월 예산, 가족 구성, 기존 보험을 상품 데이터와 비교합니다.
- **설문 대응:** 설문 우선순위 페인포인트와 상품의 `pain_points`가 겹치는 정도를 반영합니다.
- **AI 상황 해석:** 버튼을 눌렀을 때 Gemini가 핵심 입력·추가 상황·상품 정보·설문 결과를 함께 읽고 최대 20점을 추가합니다.

이 점수는 실제 가입 적합성 판정이 아니라, 고객이 먼저 살펴볼 보험을 정하는 정보 탐색용 지표입니다.
        """
    )
    st.markdown("""
#### 분석 실행 방식

- 입력값을 바꾸는 동안에는 기존 결과가 유지됩니다.
- **AI 분석하기**를 누르면 모든 입력값을 Gemini에 전달해 새 점수와 추천 이유를 생성합니다.
- 왼쪽 패널을 다시 바꾸고 버튼을 누르면 이전 결과를 새 분석 결과로 교체합니다.
    """)
    score_rows = []
    for product in recommended:
        score_rows.append(
            {
                "보험": product["name"],
                "핵심 조건": product.get("_hard_score", 0),
                "AI 상황 해석": product.get("_llm_bonus", 0),
                "설문 대응": product.get("_survey_points", 0),
                "AI 추천도": product.get("_match_score", 0),
            }
        )
    render_responsive_dataframe(
        pd.DataFrame(score_rows),
        column_config={
            "보험": st.column_config.TextColumn(width="large"),
            "핵심 조건": st.column_config.NumberColumn(width="small", format="%d"),
            "AI 상황 해석": st.column_config.NumberColumn(width="small", format="%d"),
            "설문 대응": st.column_config.NumberColumn(width="small", format="%d"),
            "AI 추천도": st.column_config.NumberColumn(width="small", format="%d"),
        },
    )

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
st.subheader("3. 상품 비교")
if not analysis_ready:
    st.info("AI 분석을 완료하면 상위 추천 상품과 추가 비교 상품을 확인할 수 있습니다.")
auto_compare_products = recommended[:3]
auto_compare_names = [p["name"] for p in auto_compare_products]
profile_signature = "|".join(
    [
        json.dumps(customer_profile, ensure_ascii=False, sort_keys=True),
        json.dumps(llm_note_analysis, ensure_ascii=False, sort_keys=True),
        customer_type,
        *auto_compare_names,
    ]
)

# 고객 상황이 바뀌면 추가 선택값만 초기화하고, 자동 비교 상위 3개는 항상 새 추천으로 교체한다.
if st.session_state.get("compare_profile_signature") != profile_signature:
    st.session_state.compare_profile_signature = profile_signature
    st.session_state.extra_compare_names = []

if analysis_ready:
    st.info("자동 비교 상품: " + ", ".join(auto_compare_names))
additional_options = [p["name"] for p in products if p["name"] not in auto_compare_names] if analysis_ready else []
extra_compare_names = st.multiselect(
    "추가로 비교할 보험을 선택하세요",
    additional_options,
    key="extra_compare_names",
    help="자동 비교 상품은 현재 고객 조건 기준 상위 3개이며, 여기에 다른 보험을 추가할 수 있습니다.",
)
compare_names = auto_compare_names + extra_compare_names
recommended_by_id = {p["product_id"]: p for p in recommended}
compare_products = [
    recommended_by_id.get(p["product_id"], p)
    for p in products
    if p["name"] in compare_names
]
# 비교표도 상품 파일 순서가 아니라 현재 고객 기준 매칭 점수가 높은 순서로 표시한다.
compare_products = sorted(
    compare_products,
    key=product_sort_key,
)
if compare_products:
    st.caption("비교표 정렬 기준: AI 추천도 내림차순 · 동점이면 상품명 가나다순")
    comparison = pd.DataFrame(
        {
            p["name"]: {
                "상품 유형": p["type"],
                "주요 보장": ", ".join(p["coverage"]),
                "갱신 여부": p["renewal"],
                "보험료 예시": p["premium_example"],
                "주의사항": p["caution"],
                "AI 추천도": f"{p.get('_match_score', 0)}점",
                "설문 우선 확인 항목": ", ".join(
                    item["label"] for item in p.get("_survey_pain_points", [])
                ) or "-",
            }
            for p in compare_products
        }
    )
    render_responsive_dataframe(
        comparison,
        column_config={
            product_name: st.column_config.TextColumn(width="large")
            for product_name in comparison.columns
        },
    )

st.markdown("<div class='section-divider'></div>", unsafe_allow_html=True)
st.subheader("4. 상담 전 질문 추천 및 AI 설명")
st.write("AI가 추천한 질문을 선택하거나 직접 질문을 입력하세요.")
use_llm = st.checkbox("Gemini LLM 사용 (API 키 필요)", value=True, disabled=not analysis_ready)
if "suggested_questions" not in st.session_state:
    st.session_state.suggested_questions = ["먼저 ‘AI 질문 추천 생성’을 눌러보세요."]
if st.button("AI 질문 추천 생성", disabled=not analysis_ready):
    question_products = compare_products or recommended[:1]
    with st.spinner("고객 상황과 설문 결과를 바탕으로 추천 질문을 생성하는 중입니다..."):
        generated_questions, question_mode = recommend_questions(
            age_group,
            concern,
            budget,
            existing,
            question_products,
            family_status=family_status,
            customer_type=customer_type,
            survey_priorities=survey_priorities,
            use_llm=use_llm,
            customer_profile=customer_profile,
            llm_analysis=llm_note_analysis,
        )
    st.session_state.suggested_questions = generated_questions
    st.session_state.question_mode = question_mode
st.caption(f"질문 추천 모드: {st.session_state.get('question_mode', '대기 중')}")
suggested_questions = st.session_state.suggested_questions
question = st.selectbox("추천 질문", ["직접 입력"] + suggested_questions)
if question == "직접 입력":
    question = st.text_input("질문을 입력하세요", placeholder="예: 상품 A의 갱신 조건이 궁금해요.")

ask_clicked = st.button("AI에게 물어보기", disabled=not analysis_ready)
if not analysis_ready:
    st.info("먼저 왼쪽 패널에서 AI 분석을 실행하면 질문 추천과 상품 설명을 사용할 수 있습니다.")
card_request = st.session_state.pop("pending_product_question", None)
if card_request or (ask_clicked and question):
    if card_request:
        question = card_request["question"]
        answer_products = [
            p for p in recommended if p["product_id"] == card_request["product_id"]
        ]
    else:
        answer_products = compare_products or recommended[:1]
    with st.spinner("선택한 보험 정보와 고객 질문을 바탕으로 답변을 생성하는 중입니다..."):
        intent, response, mode = answer_question(question, answer_products, use_llm=use_llm)
    st.session_state.answer_result = {
        "question": question,
        "intent": intent,
        "response": response,
        "mode": mode,
        "products": answer_products,
        "customer_context": {
            **{
                key: value for key, value in customer_profile.items()
                if key != "precheck"
            },
            "연령대": age_group,
            "관심 보장": concern,
            "월 예산": budget,
            "기존 보험": existing,
            "가족 구성": family_status,
            "고객 유형": customer_type,
            "추가 입력 LLM 해석": llm_note_analysis,
        },
        "revision_count": 0,
    }
    st.session_state.answer_history = [
        {"role": "user", "text": question},
        {"role": "assistant", "text": response, "intent": intent, "mode": mode},
    ]
    st.session_state.answer_feedback = ""

def format_chat_text(value: object) -> str:
    """AI 응답의 기본 Markdown 강조만 안전한 HTML로 변환한다."""
    raw_text = str(value).replace("\r\n", "\n")
    # 모델 응답에 포함된 연속 빈 줄은 두 줄(문단 구분)까지만 유지한다.
    raw_text = re.sub(r"\n(?:[ \t]*\n){2,}", "\n\n", raw_text)
    text = escape(raw_text).replace("\n", "<br>")
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    return text


answer_result = st.session_state.get("answer_result")
if answer_result:
    st.markdown("#### 상담 대화")
    answer_history = st.session_state.get(
        "answer_history",
        [
            {"role": "user", "text": answer_result["question"]},
            {
                "role": "assistant",
                "text": answer_result["response"],
                "intent": answer_result["intent"],
                "mode": answer_result["mode"],
            },
        ],
    )
    chat_messages = []
    # column-reverse를 사용해 새 답변이 추가되어도 채팅창의 최신 메시지가 먼저 보이게 한다.
    for message in reversed(answer_history):
        if message.get("role") == "user":
            chat_messages.append(
                '<div class="chat-message chat-user">'
                '<div class="chat-label">고객님</div>'
                f'<div class="chat-text">{escape(str(message.get("text", "")))}</div>'
                "</div>"
            )
        else:
            meta = []
            if message.get("intent"):
                meta.append(f"분류: {message['intent']}")
            if message.get("mode"):
                meta.append(f"답변 모드: {message['mode']}")
            if message.get("revision_count"):
                meta.append(f"수정 {message['revision_count']}회")
            meta_text = " · ".join(meta)
            chat_messages.append(
                '<div class="chat-message chat-assistant">'
                '<div class="chat-label">Easy Guide AI'
                + (f" · {escape(meta_text)}" if meta_text else "")
                + "</div>"
                f'<div class="chat-text">{format_chat_text(message.get("text", ""))}</div>'
                "</div>"
            )
    st.markdown(
        '<div class="chat-window">' + "".join(chat_messages) + "</div>",
        unsafe_allow_html=True,
    )

    st.markdown("#### 답변을 더 맞춤형으로 바꿔볼까요?")
    st.caption("빠른 피드백을 선택하거나, 원하는 설명 방식을 직접 입력해 주세요.")
    quick_feedbacks = [
        "너무 어려워요",
        "핵심만 요약해 주세요",
        "상품 차이만 비교해 주세요",
        "주의사항을 더 알려주세요",
        "상담 질문 형태로 바꿔주세요",
        "직접 입력",
    ]
    quick_cols = st.columns(3)
    for index, label in enumerate(quick_feedbacks):
        with quick_cols[index % 3]:
            if st.button(label, key=f"quick_feedback_{index}", use_container_width=True):
                st.session_state.answer_feedback = "" if label == "직접 입력" else label

    if st.session_state.pop("clear_answer_feedback", False):
        st.session_state.answer_feedback = ""
    feedback = st.text_area(
        "피드백 메시지",
        key="answer_feedback",
        placeholder="예: 갱신형과 비갱신형의 차이만 짧게 설명해 주세요.",
    )
    if st.button("피드백 전송", type="primary", key="submit_answer_feedback"):
        if not feedback.strip():
            st.warning("반영할 피드백을 먼저 입력해 주세요.")
        else:
            with st.spinner("피드백을 반영해 답변을 다시 작성하는 중..."):
                revised, revised_mode = refine_answer_with_feedback(
                    answer_result["question"],
                    answer_result["response"],
                    feedback.strip(),
                    answer_result["products"],
                    answer_result["customer_context"],
                    use_llm=use_llm,
                )
            st.session_state.answer_history = [
                *st.session_state.get("answer_history", []),
                {"role": "user", "text": feedback.strip()},
                {
                    "role": "assistant",
                    "text": revised,
                    "mode": revised_mode,
                    "revision_count": answer_result.get("revision_count", 0) + 1,
                },
            ]
            st.session_state.answer_result = {
                **answer_result,
                "response": revised,
                "mode": revised_mode,
                "revision_count": answer_result.get("revision_count", 0) + 1,
            }
            st.session_state.clear_answer_feedback = True
            st.rerun()

st.divider()
st.caption("본 화면은 설문 분석 결과를 서비스 기능으로 연결하는 교육·기획용 MVP입니다. 실제 적용 시 공식 상품 문서와 내부 상담 시스템 검증이 필요합니다.")
