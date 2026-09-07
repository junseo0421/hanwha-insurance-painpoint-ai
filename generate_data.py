"""프로토타입용 고객 불편 설문 1,000건을 재현 가능하게 생성한다."""

from __future__ import annotations

import csv
import random
from pathlib import Path

SEED = 42
N = 1000
OUT = Path(__file__).parent / "data" / "survey_results.csv"

# 큰 유형 하나로 묶이면 서로 다른 해결책이 섞이므로, 실제 기능과 바로 연결되는
# 8개의 세부 불편 라벨을 사용한다. ``cluster``는 세부 라벨이고,
# ``cluster_group``은 발표용 상위 유형이다.
CLUSTERS = {
    "전문용어 이해": {
        "group": "정보 이해",
        "weight": 0.14,
        "severity": (3, 5),
        "complaints": [
            "보험 용어가 너무 어려워서 무슨 뜻인지 모르겠다.",
            "갱신형과 비갱신형 같은 전문용어를 쉽게 설명해 줬으면 좋겠다.",
            "약관의 전문 표현을 일상적인 말로 바꿔서 보고 싶다.",
        ],
    },
    "보장 범위 이해": {
        "group": "정보 이해",
        "weight": 0.14,
        "severity": (3, 5),
        "complaints": [
            "이 상품이 어떤 상황을 보장하는지 한눈에 이해하기 어렵다.",
            "암 진단을 받으면 실제로 얼마를 받는지 모르겠다.",
            "보장 내용을 사례 중심의 쉬운 설명으로 보고 싶다.",
        ],
    },
    "상품 보장 비교": {
        "group": "상품 비교",
        "weight": 0.13,
        "severity": (3, 5),
        "complaints": [
            "상품 A와 상품 B의 보장 차이를 같은 기준으로 비교하기 어렵다.",
            "상품별 보장 항목과 지급 조건을 나란히 보고 싶다.",
            "어떤 상품의 보장 범위가 더 넓은지 모르겠다.",
        ],
    },
    "보험료 비교": {
        "group": "상품 비교",
        "weight": 0.12,
        "severity": (3, 5),
        "complaints": [
            "보험료만 봐서는 가격 차이가 왜 나는지 모르겠다.",
            "월 납입액과 보장 수준을 함께 비교할 수 있으면 좋겠다.",
            "내 예산에 맞는 상품인지 보험료를 비교하기 어렵다.",
        ],
    },
    "보장 제외 조건": {
        "group": "주의사항",
        "weight": 0.12,
        "severity": (3, 5),
        "complaints": [
            "보장되지 않는 조건이 설명서 뒤쪽에 있어 찾기 어렵다.",
            "기존 질환이 있으면 어떤 보장이 제외되는지 불안하다.",
            "면책기간과 보장 제외 항목을 먼저 확인하고 싶다.",
        ],
    },
    "갱신 조건": {
        "group": "주의사항",
        "weight": 0.11,
        "severity": (3, 5),
        "complaints": [
            "갱신 시 보험료가 얼마나 오를 수 있는지 명확히 알고 싶다.",
            "갱신형 상품의 장기 비용을 예측하기 어렵다.",
            "갱신 주기와 보험료 변동 조건을 찾기 어렵다.",
        ],
    },
    "상담 질문 준비": {
        "group": "상담",
        "weight": 0.12,
        "severity": (2, 4),
        "complaints": [
            "상담 전에 무엇을 물어봐야 할지 모르겠다.",
            "내 상황에 맞는 상담 질문을 미리 준비하고 싶다.",
            "상품을 고르기 전에 확인할 질문 목록이 필요하다.",
        ],
    },
    "상담 정보 전달": {
        "group": "상담",
        "weight": 0.12,
        "severity": (2, 4),
        "complaints": [
            "상담사에게 내 보험 상황을 매번 처음부터 설명해야 한다.",
            "상담할 때 내가 궁금한 내용을 정리해서 전달하기 어렵다.",
            "상담 전에 기본 정보를 정리해 상담 시간을 줄이고 싶다.",
        ],
    },
}


def main() -> None:
    random.seed(SEED)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    clusters = list(CLUSTERS)
    weights = [CLUSTERS[c]["weight"] for c in clusters]
    age_groups = ["20대", "30대", "40대", "50대 이상"]
    stages = ["정보 탐색", "상품 비교", "가입 검토", "상담"]
    channels = ["모바일", "웹", "전화", "오프라인"]
    fields = [
        "response_id", "age_group", "customer_stage", "channel", "cluster", "cluster_group",
        "complaint", "severity", "existing_insurance", "consultation_needed",
    ]

    with OUT.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for idx in range(1, N + 1):
            cluster = random.choices(clusters, weights=weights, k=1)[0]
            writer.writerow({
                "response_id": idx,
                "age_group": random.choices(age_groups, weights=[0.32, 0.31, 0.23, 0.14])[0],
                "customer_stage": random.choice(stages),
                "channel": random.choices(channels, weights=[0.48, 0.28, 0.16, 0.08])[0],
                "cluster": cluster,
                "cluster_group": CLUSTERS[cluster]["group"],
                "complaint": random.choice(CLUSTERS[cluster]["complaints"]),
                "severity": random.randint(*CLUSTERS[cluster]["severity"]),
                "existing_insurance": random.choice(["없음", "있음"]),
                "consultation_needed": random.choice(["예", "아니오"]),
            })
    print(f"generated {N} rows -> {OUT}")


if __name__ == "__main__":
    main()
