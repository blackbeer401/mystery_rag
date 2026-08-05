"""현재 공개된 기억 자료만 다루는 제한된 에코 분석 계층."""

from __future__ import annotations

import json
import os
from typing import Any

from memory_reconstruction import CLAIMS, EVIDENCE, MemoryState


SAFE_RESPONSE = {
    "summary": "현재 공개된 자료만으로는 이 가설을 안전하게 분석할 수 없습니다.",
    "supported_claim_ids": [],
    "conflicting_claim_ids": [],
    "unknown_claim_ids": [],
    "source_ids": [],
    "next_action_id": None,
}


def analyze_hypothesis(state: MemoryState, text: str, client: Any = None) -> dict[str, Any]:
    """분석만 수행하며 전달받은 ``state``를 변경하지 않는다."""
    hypothesis = text.strip()
    if not hypothesis:
        return SAFE_RESPONSE.copy()
    if _asks_for_culprit(hypothesis):
        return {
            **SAFE_RESPONSE,
            "summary": "현재 자료는 21시 15분 생존 전제를 검토할 뿐 범인을 판단할 수 없습니다.",
            "source_ids": list(state.workspace_ids),
        }
    if client is None and not os.getenv("OPENAI_API_KEY"):
        return _offline_analysis(state, hypothesis)
    try:
        api_client = client or _openai_client()
        allowed_sources = list(state.workspace_ids)
        records = [EVIDENCE[item] for item in allowed_sources]
        prompt = {
            "hypothesis": hypothesis,
            "allowed_sources": [record.__dict__ for record in records],
            "allowed_claim_ids": list(CLAIMS),
            "required_schema": SAFE_RESPONSE,
        }
        response = api_client.responses.create(
            model=os.getenv("MEMORY_ECHO_MODEL", "gpt-4.1-mini"),
            instructions=(
                "현재 공개 자료로 가설만 분석하라. 새 사실, 범인, 진행 판정을 만들지 말라. "
                "반드시 JSON 객체만 출력하고 source_ids에는 allowed_sources의 ID만 사용하라."
            ),
            input=json.dumps(prompt, ensure_ascii=False),
        )
        return validate_echo_response(state, json.loads(response.output_text))
    except Exception:
        return SAFE_RESPONSE.copy()


def validate_echo_response(state: MemoryState, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != set(SAFE_RESPONSE):
        return SAFE_RESPONSE.copy()
    allowed_sources = set(state.workspace_ids)
    allowed_claims = set(CLAIMS)
    id_fields = {
        "supported_claim_ids": allowed_claims,
        "conflicting_claim_ids": allowed_claims,
        "unknown_claim_ids": allowed_claims,
        "source_ids": allowed_sources,
    }
    for field, allowed in id_fields.items():
        ids = value.get(field)
        if not isinstance(ids, list) or not set(ids).issubset(allowed):
            return SAFE_RESPONSE.copy()
    if not isinstance(value.get("summary"), str) or value.get("next_action_id") is not None:
        return SAFE_RESPONSE.copy()
    return value


def _offline_analysis(state: MemoryState, hypothesis: str) -> dict[str, Any]:
    sources = list(state.workspace_ids)
    inferred = _infer_claim_ids(hypothesis)
    return {
        "summary": (
            "판단 가능: 선택한 자료가 명시하는 시각과 사건은 비교할 수 있습니다. "
            "판단 불가능: 정확한 사망시각과 범인은 현재 자료만으로 확정할 수 없습니다."
        ),
        "supported_claim_ids": inferred,
        "conflicting_claim_ids": [],
        "unknown_claim_ids": [item for item in CLAIMS if item not in inferred],
        "source_ids": sources,
        "next_action_id": None,
    }


def _asks_for_culprit(text: str) -> bool:
    normalized = text.replace(" ", "")
    return any(word in normalized for word in ("범인", "누가죽", "살인자", "진범"))


def _infer_claim_ids(text: str) -> list[str]:
    """API가 없어도 시제품의 두 핵심 주장 표현만 보수적으로 구조화한다."""
    normalized = text.lower().replace(" ", "")
    claims = []
    message_terms = ("메시지", "21:15", "21시15분")
    not_survival_terms = ("생존증거가아니", "뜻이아니", "예약", "자동전송")
    if any(term in normalized for term in message_terms) and any(
        term in normalized for term in not_survival_terms
    ):
        claims.append("CLAIM_MESSAGE_NOT_SURVIVAL")
    if (
        ("19:55" in normalized or "19시55분" in normalized)
        and ("23:20" in normalized or "23시20분" in normalized)
        and any(term in normalized for term in ("확정할수없", "추가", "구분"))
    ):
        claims.append("CLAIM_CONFIRMED_WINDOW")
    return claims


def _openai_client():
    from openai import OpenAI
    return OpenAI()
