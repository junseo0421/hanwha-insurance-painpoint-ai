"""고객 자유응답을 TF-IDF + K-means로 분석하고 세부 라벨을 부여한다.

``cluster``/``cluster_group`` 컬럼은 생성 데이터의 참고용 정답이며 모델 입력에는
사용하지 않는다. K-means가 만든 군집을 사람이 이해할 수 있는 이름으로 바꾸기 위해
키워드 라벨은 군집 사후 명명(post-labeling)에만 사용한다.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd
from scipy.sparse import hstack
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer


BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
INPUT = DATA_DIR / "survey_results.csv"
OUTPUT = DATA_DIR / "survey_analysis.json"

# 한 가지 큰 라벨(예: '상품 비교') 안에서도 해결책이 달라지는 지점을 나눈다.
LABEL_KEYWORDS = {
    "전문용어 이해": ["보험 용어", "전문용어", "약관", "용어", "전문 표현"],
    "보장 범위 이해": ["어떤 상황", "보장 내용", "보장하는지", "얼마를 받", "사례 중심"],
    "상품 보장 비교": ["보장 차이", "보장 항목", "지급 조건", "보장 범위", "나란히"],
    "보험료 비교": ["보험료", "납입액", "예산", "가격 차이", "비용"],
    "보장 제외 조건": ["보장되지", "제외", "기존 질환", "면책", "제외 항목"],
    "갱신 조건": ["갱신 시", "갱신형", "갱신 주기", "보험료 변동", "장기 비용"],
    "상담 질문 준비": ["무엇을 물어", "상담 질문", "확인할 질문", "질문 목록"],
    "상담 정보 전달": ["상황을", "처음부터 설명", "전달하기", "상담 시간을", "기본 정보를 정리"],
}

LABEL_GROUPS = {
    "전문용어 이해": "정보 이해",
    "보장 범위 이해": "정보 이해",
    "상품 보장 비교": "상품 비교",
    "보험료 비교": "상품 비교",
    "보장 제외 조건": "주의사항",
    "갱신 조건": "주의사항",
    "상담 질문 준비": "상담",
    "상담 정보 전달": "상담",
}


def keyword_label(text: str) -> str:
    """응답 하나의 세부 라벨을 키워드로 추정한다(모델 학습 입력에는 미사용)."""
    text = str(text)
    scored = []
    for label, keywords in LABEL_KEYWORDS.items():
        score = sum(text.count(keyword) * (2 if " " in keyword else 1) for keyword in keywords)
        scored.append((score, label))
    best_score, best_label = max(scored, key=lambda item: item[0])
    return best_label if best_score else "기타"


def _top_terms(model: KMeans, cluster_id: int, feature_names: list[str], n: int = 8) -> list[str]:
    centroid = model.cluster_centers_[cluster_id]
    top_indices = centroid.argsort()[::-1][:n]
    return [str(feature_names[i]) for i in top_indices]


def merge_same_labels(summaries: list[dict]) -> list[dict]:
    """K-means가 같은 의미를 여러 군집으로 나눈 경우 라벨 기준으로 통합한다."""
    grouped: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for summary in summaries:
        grouped[(summary.get("parent_label", "기타"), summary.get("label", "기타"))].append(summary)

    merged = []
    for (parent_label, label), items in grouped.items():
        total_count = sum(int(item["count"]) for item in items)
        top_terms = []
        representatives = []
        references = []
        distribution: Counter[str] = Counter()
        weighted_severity = 0.0
        weighted_confidence = 0.0
        for item in items:
            count = int(item["count"])
            weighted_severity += float(item.get("avg_severity", 0)) * count
            weighted_confidence += float(item.get("label_confidence", 0)) * count
            top_terms.extend(item.get("top_terms", []))
            representatives.extend(item.get("representative_complaints", []))
            if item.get("synthetic_reference_label"):
                references.append(item["synthetic_reference_label"])
            distribution.update(item.get("keyword_label_distribution", {}))
        merged.append(
            {
                "cluster_id": min(int(item["cluster_id"]) for item in items),
                "label": label,
                "parent_label": parent_label,
                "merged_cluster_count": len(items),
                "label_confidence": round(weighted_confidence / total_count, 4) if total_count else 0.0,
                "count": total_count,
                "ratio": round(total_count / sum(int(item["count"]) for item in summaries), 4),
                "avg_severity": round(weighted_severity / total_count, 2) if total_count else 0.0,
                "top_terms": list(dict.fromkeys(top_terms))[:8],
                "representative_complaints": list(dict.fromkeys(representatives))[:3],
                "keyword_label_distribution": dict(distribution.most_common(4)),
                "synthetic_reference_label": Counter(references).most_common(1)[0][0] if references else None,
            }
        )
    return sorted(merged, key=lambda item: item["count"], reverse=True)


def analyze_survey(
    input_path: Path = INPUT,
    output_path: Path = OUTPUT,
    n_clusters: int = 8,
) -> dict:
    """설문 자유응답을 클러스터링하고 분석 결과를 반환·저장한다."""
    input_path = Path(input_path)
    output_path = Path(output_path)
    df = pd.read_csv(input_path)
    texts = df["complaint"].fillna("").astype(str).tolist()
    if len(texts) < n_clusters:
        n_clusters = max(2, len(texts))

    # 한국어 짧은 문장에서 단어와 어절 일부가 모두 반영되도록 두 표현을 결합한다.
    word_vectorizer = TfidfVectorizer(
        analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True,
    )
    char_vectorizer = TfidfVectorizer(
        analyzer="char", ngram_range=(2, 5), min_df=2, max_features=4000,
        sublinear_tf=True,
    )
    word_matrix = word_vectorizer.fit_transform(texts)
    char_matrix = char_vectorizer.fit_transform(texts)
    matrix = hstack([word_matrix, char_matrix]).tocsr()
    feature_names = list(word_vectorizer.get_feature_names_out()) + [
        f"char:{term}" for term in char_vectorizer.get_feature_names_out()
    ]

    model = KMeans(n_clusters=n_clusters, random_state=42, n_init=30)
    df["model_cluster_id"] = model.fit_predict(matrix)
    # 라벨은 모델 입력에 넣지 않고, 결과를 사람이 읽을 수 있게 붙이는 데만 사용한다.
    df["_keyword_label"] = df["complaint"].map(keyword_label)

    summaries = []
    for cluster_id in sorted(df["model_cluster_id"].unique()):
        mask = df["model_cluster_id"] == cluster_id
        cluster_df = df.loc[mask]
        label_counts = cluster_df["_keyword_label"].value_counts()
        label = str(label_counts.index[0]) if len(label_counts) else "기타"
        confidence = float(label_counts.iloc[0] / len(cluster_df)) if len(cluster_df) else 0.0
        original_majority = None
        if "cluster" in cluster_df.columns:
            original_majority = str(cluster_df["cluster"].value_counts().index[0])
        summaries.append(
            {
                "cluster_id": int(cluster_id),
                "label": label,
                "parent_label": LABEL_GROUPS.get(label, "기타"),
                "label_confidence": round(confidence, 4),
                "count": int(mask.sum()),
                "ratio": round(float(mask.mean()), 4),
                "avg_severity": round(float(cluster_df["severity"].mean()), 2),
                "top_terms": _top_terms(model, cluster_id, feature_names),
                "representative_complaints": cluster_df["complaint"].head(3).tolist(),
                "keyword_label_distribution": {
                    str(k): int(v) for k, v in label_counts.head(4).items()
                },
                "synthetic_reference_label": original_majority,
            }
        )

    merged_summaries = merge_same_labels(summaries)
    result = {
        "method": "TF-IDF(word+char n-grams) + KMeans + 세부 키워드 라벨링",
        "n_rows": int(len(df)),
        "n_clusters": int(n_clusters),
        "n_labeled_clusters": len(merged_summaries),
        "random_state": 42,
        "label_taxonomy": {
            "정보 이해": ["전문용어 이해", "보장 범위 이해"],
            "상품 비교": ["상품 보장 비교", "보험료 비교"],
            "주의사항": ["보장 제외 조건", "갱신 조건"],
            "상담": ["상담 질문 준비", "상담 정보 전달"],
        },
        "clusters": merged_summaries,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def main() -> None:
    result = analyze_survey()
    print(f"analyzed {result['n_rows']} rows / K={result['n_clusters']} -> {OUTPUT}")


if __name__ == "__main__":
    main()
