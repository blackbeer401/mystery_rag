"""애매한 인터뷰 입력의 주제만 저비용 LLM으로 분류한다."""

import json


INTERVIEW_TOPIC_DESCRIPTIONS = {
    "김현준": {
        "relationship": "피해자 최종인과의 관계와 감정",
        "contract": "협력업체 선정과 계약 문제의 존재",
        "contract_detail": "계약 문제의 구체적인 쟁점과 원인",
        "argument": "사건 당일 최종인과 나눈 대화와 만남",
        "argument_detail": "언쟁의 강도, 목소리, 충돌 여부",
        "consequence": "갈등 공개로 받을 불이익과 숨길 이유",
        "alibi": "대화 이후 사건 당일 행적과 이동",
    },
    "강원모": {
        "relationship": "피해자 최종인과의 관계",
        "alibi": "사건 당일 행적과 객실 체류 주장",
        "haesung": "8년 전 해성호 사고와 당시 업무",
        "victim_recent": "최종인의 최근 재조사와 행동",
    },
    "박소영": {
        "relationship": "피해자 최종인과의 관계",
        "message": "21시 15분에 받은 메시지",
        "absence": "22시 30분 약속 불참과 연락 시도",
        "discovery": "객실 확인 요청과 시신 발견 과정",
    },
}


def _fallback_result():
    return {
        "topic": "unclear",
        "is_followup": False,
        "confidence": 0,
    }


def classify_interview_topic_semantically(
    client,
    person,
    user_input,
    last_topic=None,
):
    """
    사건 답변을 생성하지 않고 질문의 주제만 구조화한다.

    명확한 표현은 호출 전에 코드 규칙으로 처리하므로 이 함수는
    규칙과 직전 맥락으로도 결정하지 못한 입력에만 사용한다.
    """
    topic_descriptions = INTERVIEW_TOPIC_DESCRIPTIONS.get(person)
    if not topic_descriptions:
        return _fallback_result()

    allowed_topics = list(topic_descriptions)
    route_tool = {
        "type": "function",
        "name": "classify_interview_question",
        "description": (
            "사건에 답하거나 사실을 만들지 않고 인터뷰 질문의 "
            "주제만 분류한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "enum": allowed_topics + ["unclear"],
                },
                "is_followup": {
                    "type": "boolean",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "required": [
                "topic",
                "is_followup",
                "confidence",
            ],
            "additionalProperties": False,
        },
    }
    prompt = f"""
너는 추리게임 인터뷰의 질문 분류기다.
사건 내용에 답하거나 새로운 사실을 만들지 말고 함수만 호출한다.

[현재 인터뷰 인물]
{person}

[허용 주제]
{json.dumps(topic_descriptions, ensure_ascii=False)}

[직전 주제]
{last_topic or "없음"}

[분류 규칙]
1. 질문 자체에 주제가 있으면 해당 주제를 고른다.
2. "그게 뭐였는데?", "최종인이랑?", "그래서?"처럼 짧은
   후속 질문은 직전 주제가 명확할 때만 그 맥락을 사용한다.
3. 대화 상대나 만남을 확인하면 argument로 분류한다.
4. 계약의 정확한 내용이나 문제 원인을 재질문하면
   contract_detail로 분류한다.
5. 언쟁의 강도, 목소리, 위협 여부를 물으면
   argument_detail로 분류한다.
6. 대화 이후 위치와 행적을 물으면 alibi로 분류한다.
7. 인물의 허용 주제와 관계없는 과거, 범인 추측, 의미 없는 말은
   unclear로 분류한다.
8. 직전 주제만으로 의미를 정할 수 없으면 추측하지 말고
   unclear로 분류한다.

[플레이어 질문]
{user_input[:200]}
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            tools=[route_tool],
            tool_choice={
                "type": "function",
                "name": "classify_interview_question",
            },
        )
    except Exception:
        return _fallback_result()

    for item in response.output:
        if (
            item.type == "function_call"
            and item.name == "classify_interview_question"
        ):
            try:
                result = json.loads(item.arguments)
            except (TypeError, json.JSONDecodeError):
                return _fallback_result()

            topic = result.get("topic")
            confidence = result.get("confidence", 0)
            if (
                topic not in allowed_topics + ["unclear"]
                or not isinstance(confidence, (int, float))
                or confidence < 0.72
            ):
                return _fallback_result()
            return {
                "topic": topic,
                "is_followup": bool(
                    result.get("is_followup", False)
                ),
                "confidence": float(confidence),
            }

    return _fallback_result()
