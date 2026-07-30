"""플레이어의 자유 입력을 게임이 이해할 수 있는 의도로 번역한다."""

import json


ROUTE_TOOL = {
    "type": "function",
    "name": "route_game_input",
    "description": (
        "플레이어의 문장을 사건 정보에 답하지 않고 게임 의도로만 분류한다."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "intent": {
                "type": "string",
                "enum": [
                    "continue_investigation",
                    "investigate",
                    "ask_evidence",
                    "progress_help",
                    "ui_help",
                    "social_chat",
                    "out_of_scope",
                    "unclear",
                ],
            },
            "target": {
                "type": ["string", "null"],
                "enum": [
                    None,
                    "cabin",
                    "cabin_door",
                    "cabin_table",
                    "cabin_floor",
                    "discovery",
                    "forensic",
                    "kim_dongyul",
                    "kim_hyunjun",
                    "kang_wonmo",
                    "park_soyoung",
                    "witness_dongyul_corridor",
                    "witness_hyunjun_argument",
                    "witness_last_alive",
                    "witness_hyunjun_movement",
                    "digital",
                    "access",
                    "timeline",
                    "archive",
                    "notebook",
                    "hint",
                    "game_rules",
                    "greeting",
                    "thanks",
                    "identity",
                ],
            },
            "confidence": {
                "type": "number",
                "minimum": 0,
                "maximum": 1,
            },
        },
        "required": ["intent", "target", "confidence"],
        "additionalProperties": False,
    },
}


def _fallback_decision():
    return {
        "intent": "unclear",
        "target": None,
        "confidence": 0,
    }


def decide_game_action(client, user_input, context):
    """
    짧은 상태 정보와 플레이어 입력만 사용해 의도를 구조화한다.

    이 함수는 사건의 정답을 만들거나 조사를 직접 실행하지 않는다.
    실제 행동 허용 여부는 game.py와 game_state.py가 검증한다.
    """
    prompt = f"""
너는 추리게임의 입력 분류기다.
답변하거나 사건 사실을 추측하지 말고 route_game_input 함수만 호출한다.

[현재 게임 상태]
- 현재 장: {context["chapter_number"]}
- 현재 목표: {context["chapter_goal"]}
- 반드시 이어갈 다음 행동: {context["required_next_action"]}
- 선택적으로 권장한 행동: {context["optional_suggestion"]}
- 현재 실제 실행 가능한 행동: {context["available_actions"]}
- 완료한 조사: {context["completed_actions"]}
- 객실에서 확인한 구역: {context["cabin_observations"]}

[분류 규칙]
1. "계속하자", "남은 걸 보자", "다음으로 가자"처럼 현재 흐름을
   이어가려는 말은 continue_investigation이다.
2. 구체적인 대상을 새로 조사하거나 인터뷰하라는 요청은 investigate다.
3. 이미 확보한 단서, 기록, 진술의 내용이나 의미를 묻는 것은
   ask_evidence다. 질문 안에 '조사'라는 단어가 있어도 새 행동 요청이
   아니라 결과를 묻는 것이라면 ask_evidence다.
4. 다음에 무엇을 해야 하는지, 장을 넘기는 법, 진행 상황을 묻는 것은
   progress_help다.
5. 사건 수첩, 힌트, 화면, 사용법 질문은 ui_help다.
6. 짧은 인사, 감사, 에코의 정체 질문만 social_chat이다.
7. 날씨, 음식, 코딩 등 사건 및 게임과 무관한 요청은 out_of_scope다.
8. 무엇을 가리키는지 알 수 없는 말은 추측하지 말고 unclear다.
9. target은 문장에서 명확히 요청한 대상만 선택한다.
10. 선택적으로 권장한 행동과 반드시 이어갈 행동이 다를 때,
    단순한 "계속하자"는 반드시 이어갈 다음 행동을 뜻한다.
11. 아직 수행하지 않은 '반드시 이어갈 다음 행동'의 대상을
    플레이어가 직접 언급했다면, 문장이 질문형이어도 investigate로
    분류한다. 예: 다음 행동이 discovery인 상태의 "시신 발견 과정은?"
    또는 다음 행동이 forensic인 상태의 "사망 원인은?"
12. 현재 실제 실행 가능한 행동 목록에 없는 새로운 조사를 임의로
    만들어 investigate로 분류하지 않는다. 구현되지 않은 CCTV,
    시설관리기록, 설계도 등의 요청은 ask_evidence로 분류한다.

[플레이어 입력]
{user_input}
"""

    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            tools=[ROUTE_TOOL],
            tool_choice={
                "type": "function",
                "name": "route_game_input",
            },
        )
    except Exception:
        return _fallback_decision()

    for item in response.output:
        if (
            item.type == "function_call"
            and item.name == "route_game_input"
        ):
            try:
                decision = json.loads(item.arguments)
            except (TypeError, json.JSONDecodeError):
                return _fallback_decision()

            if decision.get("confidence", 0) < 0.55:
                return _fallback_decision()

            return decision

    return _fallback_decision()
