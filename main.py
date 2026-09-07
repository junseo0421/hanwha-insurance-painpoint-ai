"""FastAPI entry point for the React insurance guide.

The existing app.py remains the Streamlit validation app. This service exposes
the same product, survey and explanation concepts without importing Streamlit.
"""
from __future__ import annotations

import os
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from core.logic import (
    age_to_group,
    answer_question,
    build_base_recommendations,
    infer_customer_type,
    load_products,
    rank_survey_priorities,
    recommend_products_with_gemini,
    recommend_questions,
    refine_answer_with_feedback,
    survey_summary,
)


class CustomerProfile(BaseModel):
    insurance_age: int = Field(default=20, ge=0, le=100)
    family_status: str = "선택"
    concerns: list[str] = Field(default_factory=list)
    budget: str = "선택"
    existing: str = "선택"
    additional_note: str = ""

    def normalized(self) -> dict[str, Any]:
        profile = self.model_dump()
        profile["age_group"] = age_to_group(self.insurance_age)
        profile["customer_type"] = infer_customer_type(
            profile["age_group"],
            (self.concerns or [""])[0],
            self.budget,
            self.existing,
            self.family_status,
        )
        return profile


class RecommendationRequest(BaseModel):
    customer: CustomerProfile
    use_llm: bool = True


class ComparisonRequest(BaseModel):
    product_ids: list[str] = Field(min_length=1)
    customer: CustomerProfile | None = None


class QuestionRequest(BaseModel):
    customer: CustomerProfile
    product_ids: list[str] = Field(default_factory=list)
    use_llm: bool = True


class AnswerRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    product_ids: list[str] = Field(default_factory=list)
    use_llm: bool = True


class FeedbackRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    previous_answer: str = Field(min_length=1, max_length=10000)
    feedback: str = Field(min_length=1, max_length=2000)
    product_ids: list[str] = Field(default_factory=list)
    use_llm: bool = True


app = FastAPI(title="Hanwha Life Easy Guide API", version="1.0.0")
origins = [item.strip() for item in os.getenv("FRONTEND_ORIGIN", "http://localhost:5173").split(",") if item.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _products_by_id() -> dict[str, dict]:
    return {str(product["product_id"]): product for product in load_products()}


def _recommend(customer: CustomerProfile, use_llm: bool):
    profile = customer.normalized()
    analysis = survey_summary().get("analysis")
    priorities = rank_survey_priorities(analysis, profile)
    products = load_products()
    recommended, mode = recommend_products_with_gemini(products, profile, priorities, use_llm=use_llm)
    return profile, priorities, recommended, mode


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "hanwha-easy-guide-api"}


@app.get("/api/products")
def products() -> dict[str, Any]:
    return {"products": load_products()}


@app.post("/api/recommendations")
def recommendations(payload: RecommendationRequest) -> dict[str, Any]:
    if not payload.customer.concerns or payload.customer.budget == "선택" or payload.customer.existing == "선택" or payload.customer.family_status == "선택":
        raise HTTPException(status_code=422, detail="관심 보장, 예산, 기존 보험, 가족 구성을 선택해 주세요.")
    profile, priorities, result, mode = _recommend(payload.customer, payload.use_llm)
    return {"customer": profile, "customer_type": profile["customer_type"], "survey_priorities": priorities, "recommendation_mode": mode, "products": result}


@app.post("/api/comparisons")
def comparisons(payload: ComparisonRequest) -> dict[str, Any]:
    by_id = _products_by_id()
    missing = [pid for pid in payload.product_ids if pid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {', '.join(missing)}")
    if payload.customer:
        _, _, recommended, _ = _recommend(payload.customer, use_llm=False)
        ranked = {str(product["product_id"]): product for product in recommended}
        selected = [ranked.get(pid, by_id[pid]) for pid in payload.product_ids]
        selected.sort(key=lambda product: (-int(product.get("_match_score", 0)), str(product.get("name", ""))))
    else:
        selected = [by_id[pid] for pid in payload.product_ids]
    return {"products": selected}


@app.post("/api/questions/recommend")
def questions(payload: QuestionRequest) -> dict[str, Any]:
    profile, priorities, recommended, _ = _recommend(payload.customer, use_llm=False)
    by_id = {str(product["product_id"]): product for product in recommended}
    selected = [by_id[pid] for pid in payload.product_ids if pid in by_id] or recommended[:3]
    items, mode = recommend_questions(profile, selected, priorities, use_llm=payload.use_llm)
    return {"questions": items, "mode": mode, "survey_priorities": priorities[:5]}


@app.post("/api/questions/answer")
def answer(payload: AnswerRequest) -> dict[str, Any]:
    by_id = _products_by_id()
    missing = [pid for pid in payload.product_ids if pid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {', '.join(missing)}")
    intent, response, mode = answer_question(payload.question, [by_id[pid] for pid in payload.product_ids], payload.use_llm)
    return {"intent": intent, "response": response, "mode": mode}


@app.post("/api/questions/feedback")
def feedback(payload: FeedbackRequest) -> dict[str, Any]:
    by_id = _products_by_id()
    missing = [pid for pid in payload.product_ids if pid not in by_id]
    if missing:
        raise HTTPException(status_code=404, detail=f"상품을 찾을 수 없습니다: {', '.join(missing)}")
    response, mode = refine_answer_with_feedback(payload.question, payload.previous_answer, payload.feedback, [by_id[pid] for pid in payload.product_ids], payload.use_llm)
    return {"response": response, "mode": mode}


@app.get("/api/survey-analysis")
def survey_analysis() -> dict[str, Any]:
    return survey_summary()
