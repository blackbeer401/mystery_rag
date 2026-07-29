from contextvars import ContextVar

from unlock_manager import unlock_document


# Streamlit 세션마다 서로 다른 게임 상태를 사용한다.
# 터미널에서 game.py를 직접 실행할 때는 fallback 상태를 사용한다.
_current_game_state = ContextVar(
    "current_game_state",
    default=None
)

_fallback_game_state = {
    "investigated": set(),
    "investigation_log": [],
    "unlocked_documents": set(),
    "hint_count": 0,
    "hint_history": [],
}


def create_game_state():
    """새 플레이어가 사용할 빈 게임 상태를 만든다."""
    return {
        "investigated": set(),
        "investigation_log": [],
        "unlocked_documents": set(),
        "hint_count": 0,
        "hint_history": [],
    }


def bind_session_state(session_state):
    """현재 Streamlit 세션과 game_state 모듈을 연결한다."""
    if "game_state_data" not in session_state:
        session_state.game_state_data = create_game_state()

    # 이전 버전에서 이미 시작한 세션에도 새 상태값을 안전하게 추가한다.
    session_state.game_state_data.setdefault(
        "investigated",
        set()
    )
    session_state.game_state_data.setdefault(
        "investigation_log",
        []
    )
    session_state.game_state_data.setdefault(
        "unlocked_documents",
        set()
    )
    session_state.game_state_data.setdefault(
        "hint_count",
        0
    )
    session_state.game_state_data.setdefault(
        "hint_history",
        []
    )

    _current_game_state.set(
        session_state.game_state_data
    )


def reset_game_state(session_state=None):
    """현재 플레이어의 조사·해금 상태를 처음으로 되돌린다."""
    new_state = create_game_state()

    if session_state is not None:
        session_state.game_state_data = new_state

    _current_game_state.set(new_state)


def _get_game_state():
    state = _current_game_state.get()

    if state is None:
        return _fallback_game_state

    return state


def _get_investigated_set():
    return _get_game_state()["investigated"]


def _get_investigation_log_list():
    return _get_game_state()["investigation_log"]


def _get_unlocked_document_set():
    return _get_game_state()["unlocked_documents"]


def _unlock_for_current_player(file_name):
    """문서를 DB에 준비하고 현재 플레이어에게만 검색 권한을 준다."""
    unlock_document(file_name)
    _get_unlocked_document_set().add(file_name)
INVESTIGATION_TITLES = {
    # 인터뷰
    "INTERVIEW_KIMDONGYUL_BASIC": "김동율 기본 인터뷰",
    "INTERVIEW_KIMDONGYUL_DEEP": "김동율 심층 재인터뷰",
    "INTERVIEW_KIMHYUNJUN_BASIC": "김현준 기본 인터뷰",
    "INTERVIEW_KIMHYUNJUN_DEEP": "김현준 심층 재인터뷰",
    "INTERVIEW_KANGWONMO_BASIC": "강원모 기본 인터뷰",
    "INTERVIEW_KANGWONMO_FOLLOWUP": "강원모 추가 인터뷰",
    "INTERVIEW_PARKSOYOUNG": "박소영 인터뷰",

    # 목격자 조사
    "WITNESS_KIMDONGYUL_CORRIDOR": "김동율 객실구역 목격 조사",
    "WITNESS_KIMHYUNJUN_ARGUMENT": "김현준 언쟁 목격 조사",
    "WITNESS_LAST_CONFIRMED_ALIVE": "최종인 마지막 생존 목격 조사",
    "WITNESS_KIMHYUNJUN_MOVEMENT": "김현준 이동 동선 조사",

    # 법의학
    "FORENSIC_POSTMORTEM": "사망 원인 및 현장 감식",

    # 디지털 포렌식
    "DIGITAL_MESSAGE_FORENSICS": "21시 15분 메시지 포렌식",
    "DIGITAL_USB_TRACE": "USB 사용 흔적 분석",
    "DIGITAL_VICTIM_DEVICE_ACTIVITY": "최종인 최근 기기 활동 분석",

    # 출입 기록
    "ACCESS_KANGWONMO_RAW": "강원모 객실 출입 기록 분석",
    "ACCESS_CABIN_SYSTEM": "객실 출입 시스템 구조 분석",

    # 타임라인
    "TIMELINE_ALIBI_ANALYSIS": "사건 타임라인 및 알리바이 종합 분석",

    # 과거 사건
    "ARCHIVE_HAESUNG_BASIC": "해성호 사고 기본 기록 조사",
    "ARCHIVE_TECHNICAL_RISK": "해성호 기술적 위험 심층 조사",
    "ARCHIVE_INFORMATION_FLOW": "위험 정보 전달 과정 조사",
    "ARCHIVE_RESPONSIBILITY": "사고 책임 평가 자료 조사",
    "ARCHIVE_VICTIM_ANALYSIS": "최종인의 과거 사고 재분석 기록 조사",
}

def add_investigation_log(investigation_id):
    investigation_log = _get_investigation_log_list()

    title = INVESTIGATION_TITLES.get(
        investigation_id,
        investigation_id
    )

    if title not in investigation_log:
        investigation_log.append(title)

# 조사 완료 처리
def add_investigation(investigation_id):
    investigated = _get_investigated_set()

    # 이미 완료한 조사는 다시 기록하지 않음
    if investigation_id in investigated:
        return

    investigated.add(investigation_id)
    add_investigation_log(investigation_id)

    check_unlocks(investigation_id)


# 조사 ID와 해금할 문서를 연결
UNLOCK_RULES = {
    # INTERVIEW
    "INTERVIEW_KIMDONGYUL_BASIC":
        "INT_001_KIMDONGYUL_BASIC.md",

    "INTERVIEW_KIMDONGYUL_DEEP":
        "INT_002_KIMDONGYUL_DEEP.md",

    "INTERVIEW_KIMHYUNJUN_BASIC":
        "INT_003_KIMHYUNJUN_BASIC.md",

    "INTERVIEW_KIMHYUNJUN_DEEP":
        "INT_004_KIMHYUNJUN_DEEP.md",

    "INTERVIEW_KANGWONMO_BASIC":
        "INT_005_KANGWONMO_BASIC.md",

    "INTERVIEW_KANGWONMO_FOLLOWUP":
        "INT_006_KANGWONMO_FOLLOWUP.md",

    "INTERVIEW_PARKSOYOUNG":
        "INT_007_PARKSOYOUNG.md",

    # WITNESS
    "WITNESS_KIMDONGYUL_CORRIDOR":
        "WIT_001_KIMDONGYUL_CORRIDOR.md",

    "WITNESS_KIMHYUNJUN_ARGUMENT":
        "WIT_002_KIMHYUNJUN_ARGUMENT.md",

    "WITNESS_LAST_CONFIRMED_ALIVE":
        "WIT_003_LAST_CONFIRMED_ALIVE.md",

    "WITNESS_KIMHYUNJUN_MOVEMENT":
        "WIT_004_KIMHYUNJUN_MOVEMENT.md",

    # FORENSIC
    "FORENSIC_POSTMORTEM":
        "FORENSIC_001_POSTMORTEM.md",

    # DIGITAL
    "DIGITAL_MESSAGE_FORENSICS":
        "DIGITAL_001_MESSAGE_FORENSICS.md",

    "DIGITAL_USB_TRACE":
        "DIGITAL_002_USB_TRACE.md",

    "DIGITAL_VICTIM_DEVICE_ACTIVITY":
        "DIGITAL_003_VICTIM_DEVICE_ACTIVITY.md",

    # ACCESS
    "ACCESS_KANGWONMO_RAW":
        "ACCESS_001_KANGWONMO_RAW.md",

    "ACCESS_CABIN_SYSTEM":
        "ACCESS_002_CABIN_SYSTEM.md",

    # TIMELINE
    "TIMELINE_ALIBI_ANALYSIS":
        "TIMELINE_001_ALIBI_ANALYSIS.md",

    # ARCHIVE
    "ARCHIVE_HAESUNG_BASIC":
        "ARC_001_HAESUNG_TECHNICAL_RECORD.md",

    "ARCHIVE_TECHNICAL_RISK":
        "DEEP_001_TECHNICAL_RISK.md",

    "ARCHIVE_INFORMATION_FLOW":
        "DEEP_002_INFORMATION_FLOW.md",

    "ARCHIVE_RESPONSIBILITY":
        "DEEP_003_RESPONSIBILITY_RECONSTRUCTION.md",

    "ARCHIVE_VICTIM_ANALYSIS":
        "DEEP_004_VICTIM_ANALYSIS.md",


}


# 완료된 조사에 대응하는 문서 해금
def check_unlocks(investigation_id):
    investigated = _get_investigated_set()

    if investigation_id in UNLOCK_RULES:
        _unlock_for_current_player(
            UNLOCK_RULES[investigation_id]
        )
            
    # 최종인이 왜 8년 뒤 다시 조사했는지 해금
    if (
        "DIGITAL_VICTIM_DEVICE_ACTIVITY" in investigated
        and "ARCHIVE_HAESUNG_BASIC" in investigated
        and "EVIDENCE_RESEARCH_TRIGGER" not in investigated
    ):
        investigated.add("EVIDENCE_RESEARCH_TRIGGER")
        _unlock_for_current_player(
            "EVID_002_VICTIM_RESEARCH_TRIGGER.md"
        )

    # 사라진 USB의 진짜 의미 해금
    if (
        "DIGITAL_USB_TRACE" in investigated
        and "ARCHIVE_RESPONSIBILITY" in investigated
        and "EVIDENCE_USB_CONTEXT" not in investigated
    ):
        investigated.add("EVIDENCE_USB_CONTEXT")
        _unlock_for_current_player(
            "EVID_001_MISSING_USB_CONTEXT.md"
        )

# 현재 조사 상태 복사본 반환
def get_investigated():
    return _get_investigated_set().copy()


def get_unlocked_documents():
    """현재 플레이어가 RAG로 검색할 수 있는 해금 문서를 반환한다."""
    return _get_unlocked_document_set().copy()


MAX_HINTS = 3


STORY_CHAPTERS = {
    1: {
        "title": "객실에 남은 흔적",
        "transition": (
            "최종인의 죽음은 단순 사고가 아니었습니다.\n\n"
            "이제 사건 당일 그와 접촉한 사람들의 말을 "
            "확인해야 합니다."
        ),
    },
    2: {
        "title": "네 사람의 진술",
        "transition": (
            "네 사람은 모두 사실의 일부만을 말하고 있습니다.\n\n"
            "진술보다 객관적인 시간 기록을 다시 살펴볼 때입니다."
        ),
    },
    3: {
        "title": "존재하지 않는 21시 15분",
        "transition": (
            "메시지가 도착한 시간과 사람이 살아 있던 시간은 "
            "같지 않았습니다.\n\n"
            "무너진 시간축 안에서 실제 범행 가능시간을 "
            "다시 구성해야 합니다."
        ),
    },
    4: {
        "title": "객실 밖의 76분",
        "transition": (
            "객실에 있었다는 진술은 출입기록으로 증명되지 "
            "않았습니다.\n\n"
            "이제 현재의 살인과 8년 전 사고가 어떻게 "
            "연결되는지 확인해야 합니다."
        ),
    },
    5: {
        "title": "8년 전의 침묵",
        "transition": (
            "현재의 살인은 8년 전 진실을 다시 묻기 위한 "
            "두 번째 은폐였습니다.\n\n"
            "확보한 시간·동기·자료를 하나의 증거망으로 "
            "연결할 차례입니다."
        ),
    },
    6: {
        "title": "마지막 기록",
        "transition": (
            "핵심 조사기록이 모두 연결되었습니다.\n\n"
            "이제 범인, 범행 가능시간, 동기와 핵심 증거를 "
            "바탕으로 마지막 추리를 준비할 수 있습니다."
        ),
    },
}


CHAPTER_REQUIREMENTS = {
    2: {
        "FORENSIC_POSTMORTEM",
    },
    3: {
        "INTERVIEW_KIMDONGYUL_BASIC",
        "INTERVIEW_KIMHYUNJUN_BASIC",
        "INTERVIEW_KANGWONMO_BASIC",
        "INTERVIEW_PARKSOYOUNG",
    },
    4: {
        "WITNESS_LAST_CONFIRMED_ALIVE",
        "DIGITAL_MESSAGE_FORENSICS",
    },
    5: {
        "ACCESS_KANGWONMO_RAW",
        "ACCESS_CABIN_SYSTEM",
        "TIMELINE_ALIBI_ANALYSIS",
    },
    6: {
        "ARCHIVE_HAESUNG_BASIC",
        "ARCHIVE_INFORMATION_FLOW",
        "ARCHIVE_RESPONSIBILITY",
        "ARCHIVE_VICTIM_ANALYSIS",
        "EVIDENCE_USB_CONTEXT",
    },
}


def get_story_chapter():
    """완료한 핵심 조사로 현재 스토리 장을 계산한다."""
    investigated = _get_investigated_set()
    chapter_number = 1

    for next_chapter in range(2, 7):
        requirements = CHAPTER_REQUIREMENTS[
            next_chapter
        ]

        if requirements.issubset(investigated):
            chapter_number = next_chapter
        else:
            break

    chapter = STORY_CHAPTERS[chapter_number]

    return {
        "number": chapter_number,
        "title": chapter["title"],
        "label": (
            f"제{chapter_number}장 · "
            f"{chapter['title']}"
        ),
    }


def get_chapter_transition_message(chapter_number):
    """새 장에 진입했을 때 보여줄 연출 문구를 반환한다."""
    chapter = STORY_CHAPTERS[chapter_number]

    return (
        "\n\n━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"## 제{chapter_number}장 — {chapter['title']}\n\n"
        f"{chapter['transition']}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


CHAPTER_ACTION_RULES = {
    "interview": {
        "minimum_chapter": 2,
        "direction": (
            "먼저 객실의 사망원인과 현장 흔적을 확인해야 합니다."
        ),
    },
    "witness_general": {
        "minimum_chapter": 2,
        "direction": (
            "먼저 객실의 사망원인과 현장 흔적을 확인해야 합니다."
        ),
    },
    "witness_last_alive": {
        "minimum_chapter": 3,
        "direction": (
            "먼저 주요 관계자 네 사람의 기본 진술을 확보해야 합니다."
        ),
    },
    "digital_message": {
        "minimum_chapter": 3,
        "direction": (
            "먼저 주요 관계자 네 사람의 기본 진술을 확보해야 합니다."
        ),
    },
    "access": {
        "minimum_chapter": 4,
        "direction": (
            "마지막 생존 목격과 21시 15분 메시지의 성격을 "
            "먼저 확인해야 합니다."
        ),
    },
    "timeline": {
        "minimum_chapter": 4,
        "direction": (
            "마지막 생존 목격과 21시 15분 메시지의 성격을 "
            "먼저 확인해야 합니다."
        ),
    },
    "digital_deep": {
        "minimum_chapter": 5,
        "direction": (
            "먼저 객실 출입기록과 알리바이를 대조해 "
            "범행 가능시간을 재구성해야 합니다."
        ),
    },
    "archive": {
        "minimum_chapter": 5,
        "direction": (
            "먼저 객실 출입기록과 알리바이를 대조해 "
            "범행 가능시간을 재구성해야 합니다."
        ),
    },
    "accusation": {
        "minimum_chapter": 6,
        "direction": (
            "현재까지의 기록만으로는 최종 지목을 뒷받침할 "
            "증거망이 완성되지 않았습니다. 현재 장의 핵심 조사를 "
            "더 진행해야 합니다."
        ),
    },
}


def get_chapter_action_block(action_name):
    """현재 장에서 아직 허용되지 않은 행동의 안내문을 반환한다."""
    rule = CHAPTER_ACTION_RULES[action_name]
    current_chapter = get_story_chapter()["number"]

    if current_chapter >= rule["minimum_chapter"]:
        return None

    return (
        "🔒 아직 이 조사를 진행할 단계가 아닙니다.\n\n"
        f"{rule['direction']}"
    )


INVESTIGATION_CATEGORIES = {
    "현장과 피해자": {
        "FORENSIC_POSTMORTEM",
    },
    "관계자 진술": {
        "INTERVIEW_KIMDONGYUL_BASIC",
        "INTERVIEW_KIMHYUNJUN_BASIC",
        "INTERVIEW_KANGWONMO_BASIC",
        "INTERVIEW_PARKSOYOUNG",
    },
    "시간과 동선": {
        "DIGITAL_MESSAGE_FORENSICS",
        "WITNESS_LAST_CONFIRMED_ALIVE",
        "ACCESS_KANGWONMO_RAW",
        "TIMELINE_ALIBI_ANALYSIS",
    },
    "과거 기록": {
        "ARCHIVE_HAESUNG_BASIC",
        "ARCHIVE_RESPONSIBILITY",
        "ARCHIVE_VICTIM_ANALYSIS",
    },
}


def _category_status(required_ids, investigated):
    completed = len(required_ids & investigated)

    if completed == 0:
        return "not_started"

    if completed == len(required_ids):
        return "completed"

    return "in_progress"


def get_sidebar_summary():
    """사이드바에 표시할 스포일러 없는 진행 정보."""
    state = _get_game_state()
    investigated = state["investigated"]
    investigation_log = state["investigation_log"]
    story_chapter = get_story_chapter()

    categories = {
        category: _category_status(
            required_ids,
            investigated
        )
        for category, required_ids
        in INVESTIGATION_CATEGORIES.items()
    }

    return {
        "current_stage": story_chapter["label"],
        "chapter_number": story_chapter["number"],
        "chapter_title": story_chapter["title"],
        "completed_count": len(investigation_log),
        "all_records": investigation_log.copy(),
        "recent_records": investigation_log[-3:],
        "categories": categories,
        "remaining_hints": (
            MAX_HINTS - state["hint_count"]
        ),
        "max_hints": MAX_HINTS,
        "last_hint": (
            state["hint_history"][-1]
            if state["hint_history"]
            else None
        ),
    }


def use_hint():
    """
    현재 조사 상태에 맞는 힌트를 한 번 사용한다.
    힌트는 조사 상태나 문서 해금 상태를 변경하지 않는다.
    """
    state = _get_game_state()

    if state["hint_count"] >= MAX_HINTS:
        return None

    investigated = state["investigated"]
    hint_level = state["hint_count"]
    chapter_number = get_story_chapter()["number"]

    chapter_hint_candidates = {
        1: [
            (
                "FORENSIC_POSTMORTEM",
                (
                    "사건의 출발점은 피해자의 상태와 현장입니다.",
                    "정확한 사망 시각을 판단하려면 먼저 사망 원인과 현장 상태를 확인해 보십시오.",
                    "피해자의 사망 원인과 현장 감식을 새롭게 조사해 보십시오.",
                ),
            ),
        ],
        2: [
            (
                investigation_id,
                (
                    "서로 다른 이해관계를 가진 관계자들의 진술을 비교해 보십시오.",
                    "아직 기본 진술을 확보하지 않은 주요 관계자가 있습니다.",
                    f"{person}을 인터뷰해 기본 진술을 확보해 보십시오.",
                ),
            )
            for investigation_id, person in (
                ("INTERVIEW_KIMDONGYUL_BASIC", "김동율"),
                ("INTERVIEW_KIMHYUNJUN_BASIC", "김현준"),
                ("INTERVIEW_KANGWONMO_BASIC", "강원모"),
                ("INTERVIEW_PARKSOYOUNG", "박소영"),
            )
        ],
        3: [
            (
                "WITNESS_LAST_CONFIRMED_ALIVE",
                (
                    "기록보다 사람이 직접 확인한 시간이 중요할 수 있습니다.",
                    "피해자가 마지막으로 살아 있었던 시점을 입증할 목격정보를 찾아보십시오.",
                    "최종인의 마지막 생존 목격자를 조사해 보십시오.",
                ),
            ),
            (
                "DIGITAL_MESSAGE_FORENSICS",
                (
                    "메시지가 도착한 시간과 작성된 시간은 다를 수 있습니다.",
                    "21시 15분 메시지가 실제 생존을 입증하는지 검증해 보십시오.",
                    "21시 15분 메시지의 생성·전송 방식을 포렌식해 보십시오.",
                ),
            ),
        ],
        4: [
            (
                "ACCESS_CABIN_SYSTEM",
                (
                    "진술과 객관적인 이동 기록을 서로 비교해 보십시오.",
                    "객실 출입기록에서 입실과 퇴실이 같은 방식으로 기록되는지 확인해 보십시오.",
                    "강원모 객실의 출입기록과 도어 시스템을 분석해 보십시오.",
                ),
            ),
            (
                "TIMELINE_ALIBI_ANALYSIS",
                (
                    "확보한 시간 기록들을 하나의 순서로 배열해 보십시오.",
                    "메시지·목격·출입 기록이 가리키는 시간을 함께 비교해 보십시오.",
                    "사건 시간대와 주요 인물들의 알리바이를 종합 분석해 보십시오.",
                ),
            ),
        ],
        5: [
            (
                "DIGITAL_VICTIM_DEVICE_ACTIVITY",
                (
                    "피해자가 최근 남긴 디지털 작업 흔적을 더 살펴보십시오.",
                    "사라진 저장장치와 오래된 사고자료 사이의 관계를 확인해 보십시오.",
                    "피해자의 USB 흔적과 최근 기기 활동을 추가 분석해 보십시오.",
                ),
            ),
            (
                "ARCHIVE_VICTIM_ANALYSIS",
                (
                    "현재 사건의 동기는 과거 기록과 연결되어 있을 수 있습니다.",
                    "해성호 사고의 초기자료와 책임평가 자료를 비교해 보십시오.",
                    "8년 전 해성호 사고의 보존기록을 단계적으로 조사해 보십시오.",
                ),
            ),
        ],
        6: [],
    }
    hint_candidates = chapter_hint_candidates[
        chapter_number
    ]

    for investigation_id, messages in hint_candidates:
        if investigation_id not in investigated:
            hint = messages[hint_level]
            break
    else:
        hint = (
            "핵심 조사는 충분히 진행되었습니다. "
            "확보한 기록 사이의 모순을 정리해 최종 추리를 준비해 보십시오."
        )

    state["hint_count"] += 1
    state["hint_history"].append(hint)

    return hint

# 현재까지 완료한 조사 기록 출력
# 현재까지 완료한 조사 기록 출력
def show_investigation_log():
    investigation_log = _get_investigation_log_list()

    if not investigation_log:
        return (
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "사건 수첩\n\n"
            "아직 확보한 조사 기록이 없습니다.\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        )

    lines = [
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        "사건 수첩",
        "",
        "현재까지 확보한 조사",
        ""
    ]

    for index, title in enumerate(
        investigation_log,
        start=1
    ):
        lines.append(
            f"{index}. {title}"
        )

    lines.append("")
    lines.append(f"총 {len(investigation_log)}건")
    lines.append("")
    lines.append("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    return "\n".join(lines)


# 현재 조사 진행 상황 출력
def show_investigation_status():
    investigated = _get_investigated_set()
    investigation_log = _get_investigation_log_list()

    lines = [
        "[조사 현황]",
        "",
        f"완료한 조사: {len(investigation_log)}개"
    ]

    # -------------------------
    # 완료한 조사 표시
    # -------------------------
    if investigation_log:

        lines.append("")
        lines.append("[확인 완료]")

        for title in investigation_log:
            lines.append(
                f"✓ {title}"
            )

    else:
        lines.append("")
        lines.append(
            "아직 완료한 조사가 없습니다."
        )

    # -------------------------
    # 현재 확인 가능한 조사 방향
    # -------------------------
    available_directions = []

    # 법의학 조사
    if "FORENSIC_POSTMORTEM" not in investigated:
        available_directions.append(
            "사망 원인과 현장 감식"
        )

    # 디지털 포렌식은 단계에 따라 다르게 표시
    if "DIGITAL_MESSAGE_FORENSICS" not in investigated:
        available_directions.append(
            "피해자의 디지털 자료"
        )

    elif "DIGITAL_USB_TRACE" not in investigated:
        available_directions.append(
            "피해자의 외부 저장장치 사용 흔적"
        )

    elif "DIGITAL_VICTIM_DEVICE_ACTIVITY" not in investigated:
        available_directions.append(
            "피해자의 최근 기기 활동"
        )

    # 인터뷰
    interview_ids = {
        "INTERVIEW_KIMDONGYUL_BASIC",
        "INTERVIEW_KIMHYUNJUN_BASIC",
        "INTERVIEW_KANGWONMO_BASIC",
        "INTERVIEW_PARKSOYOUNG"
    }

    if not interview_ids.issubset(investigated):
        available_directions.append(
            "사건 관계자 인터뷰"
        )

    # 목격자 조사
    witness_ids = {
        "WITNESS_KIMDONGYUL_CORRIDOR",
        "WITNESS_KIMHYUNJUN_ARGUMENT",
        "WITNESS_LAST_CONFIRMED_ALIVE",
        "WITNESS_KIMHYUNJUN_MOVEMENT"
    }

    if not witness_ids.issubset(investigated):
        available_directions.append(
            "사건 당시 목격자 진술"
        )

    # 객실 출입기록
    if "ACCESS_KANGWONMO_RAW" not in investigated:
        available_directions.append(
            "객실 출입기록"
        )

    elif "ACCESS_CABIN_SYSTEM" not in investigated:
        available_directions.append(
            "객실 출입 시스템 구조"
        )

    # 과거 사고 기록은 단계명을 직접 노출하지 않음
    archive_ids = {
        "ARCHIVE_HAESUNG_BASIC",
        "ARCHIVE_TECHNICAL_RISK",
        "ARCHIVE_INFORMATION_FLOW",
        "ARCHIVE_RESPONSIBILITY",
        "ARCHIVE_VICTIM_ANALYSIS"
    }

    if not archive_ids.issubset(investigated):
        available_directions.append(
            "해성호 과거 사고 기록"
        )

    # 선행 조사 완료 후에만 종합 분석 표시
    if (
        "DIGITAL_MESSAGE_FORENSICS" in investigated
        and "WITNESS_LAST_CONFIRMED_ALIVE" in investigated
        and "TIMELINE_ALIBI_ANALYSIS" not in investigated
    ):
        available_directions.append(
            "시간기록과 알리바이 종합 분석"
        )

    lines.append("")
    lines.append("[현재 조사 가능한 방향]")

    if available_directions:

        for direction in available_directions:
            lines.append(
                f"□ {direction}"
            )

    else:
        lines.append(
            "현재 확인 가능한 주요 조사를 모두 완료했습니다."
        )

    return "\n".join(lines)
