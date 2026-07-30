from contextvars import ContextVar
from pathlib import Path

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
    "tutorial_events": set(),
    "expected_tutorial_action": None,
    "cabin_observations": set(),
    "tutorial_reminders": set(),
    "chapter_one_closed": False,
    "chapter_one_reflection": None,
    "chapter_two_closed": False,
    "chapter_two_reflection": None,
    "active_interview": None,
    "interview_topics": {},
    "interview_observations": {},
    "interview_last_topics": {},
    "interview_topic_counts": {},
    "pending_interview_exit": False,
    "pending_echo_action": None,
}


def create_game_state():
    """새 플레이어가 사용할 빈 게임 상태를 만든다."""
    return {
        "investigated": set(),
        "investigation_log": [],
        "unlocked_documents": set(),
        "hint_count": 0,
        "hint_history": [],
        "tutorial_events": set(),
        "expected_tutorial_action": None,
        "cabin_observations": set(),
        "tutorial_reminders": set(),
        "chapter_one_closed": False,
        "chapter_one_reflection": None,
        "chapter_two_closed": False,
        "chapter_two_reflection": None,
        "active_interview": None,
        "interview_topics": {},
        "interview_observations": {},
        "interview_last_topics": {},
        "interview_topic_counts": {},
        "pending_interview_exit": False,
        "pending_echo_action": None,
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
    session_state.game_state_data.setdefault(
        "tutorial_events",
        set()
    )
    session_state.game_state_data.setdefault(
        "expected_tutorial_action",
        None
    )
    session_state.game_state_data.setdefault(
        "cabin_observations",
        set()
    )
    session_state.game_state_data.setdefault(
        "tutorial_reminders",
        set()
    )
    session_state.game_state_data.setdefault(
        "chapter_one_closed",
        False
    )
    session_state.game_state_data.setdefault(
        "chapter_one_reflection",
        None
    )
    session_state.game_state_data.setdefault(
        "chapter_two_closed",
        False
    )
    session_state.game_state_data.setdefault(
        "chapter_two_reflection",
        None
    )
    session_state.game_state_data.setdefault(
        "active_interview",
        None
    )
    session_state.game_state_data.setdefault(
        "interview_topics",
        {}
    )
    session_state.game_state_data.setdefault(
        "interview_observations",
        {}
    )
    session_state.game_state_data.setdefault(
        "interview_last_topics",
        {}
    )
    session_state.game_state_data.setdefault(
        "interview_topic_counts",
        {}
    )
    session_state.game_state_data.setdefault(
        "pending_interview_exit",
        False
    )
    session_state.game_state_data.setdefault(
        "pending_echo_action",
        None
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


def apply_debug_checkpoint(session_state, checkpoint):
    """개발 중 반복 플레이를 줄이는 일관된 테스트 상태를 만든다."""
    reset_game_state(session_state)
    state = _get_game_state()

    if checkpoint == "chapter_1_start":
        return

    if checkpoint not in {
        "chapter_2_start",
        "chapter_2_last_interview",
        "chapter_2_compare",
    }:
        raise ValueError(
            f"등록되지 않은 디버그 체크포인트: {checkpoint}"
        )

    state["cabin_observations"].update({
        "door",
        "table",
        "floor",
    })
    for investigation_id in CHAPTER_REQUIREMENTS[2]:
        add_investigation(investigation_id)

    state["chapter_one_reflection"] = "insufficient"
    state["chapter_one_closed"] = True
    state["tutorial_events"].update({
        "coach_cabin",
        "cabin_record_followup",
    })

    if checkpoint in {
        "chapter_2_last_interview",
        "chapter_2_compare",
    }:
        completed_interviews = {
            "김동율": {
                "id": "INTERVIEW_KIMDONGYUL_BASIC",
                "topics": {
                    "relationship",
                    "alibi",
                    "haesung_overview",
                    "haesung_role",
                },
            },
            "김현준": {
                "id": "INTERVIEW_KIMHYUNJUN_BASIC",
                "topics": {
                    "contract",
                    "argument",
                    "consequence",
                },
            },
            "강원모": {
                "id": "INTERVIEW_KANGWONMO_BASIC",
                "topics": {
                    "alibi",
                    "haesung",
                    "victim_recent",
                },
            },
        }
        for person, interview_data in completed_interviews.items():
            add_investigation(interview_data["id"])
            state["interview_topics"][person] = (
                interview_data["topics"].copy()
            )

    if checkpoint == "chapter_2_compare":
        add_investigation("INTERVIEW_PARKSOYOUNG")
        state["interview_topics"]["박소영"] = {
            "message",
            "absence",
            "discovery",
        }


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
    # 1장 현장 조사
    "SCENE_CABIN_INSPECTION": "피해자 객실 현장 조사",
    "SCENE_DISCOVERY_RECONSTRUCTION": "시신 발견 경위 재구성",

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
    # SCENE
    "SCENE_CABIN_INSPECTION":
        "SCENE_001_CABIN_INSPECTION.md",

    "SCENE_DISCOVERY_RECONSTRUCTION":
        "SCENE_002_DISCOVERY_RECONSTRUCTION.md",

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


def _read_notebook_document(investigation_id):
    """해금된 RAG 원문을 사건 수첩 표시용으로 읽는다."""
    file_name = UNLOCK_RULES.get(investigation_id)

    if not file_name:
        return None

    file_path = (
        Path(__file__).resolve().parent
        / "data"
        / "locked"
        / file_name
    )

    if not file_path.exists():
        return None

    lines = file_path.read_text(
        encoding="utf-8"
    ).splitlines()

    # 제목은 사건 수첩의 펼침 제목으로 이미 표시한다.
    if lines and lines[0].startswith("# "):
        lines = lines[1:]

    return "\n".join(lines).strip()


def read_investigation_section(investigation_id, section_title):
    """조사 원문의 특정 Markdown H2 구역을 반환한다."""
    document = _read_notebook_document(investigation_id)

    if not document:
        return None

    target_heading = f"## {section_title}"
    section_lines = []
    collecting = False

    for line in document.splitlines():
        if line == target_heading:
            collecting = True
            continue

        if collecting and line.startswith("## "):
            break

        if collecting:
            section_lines.append(line)

    content = "\n".join(section_lines).strip()
    return content or None


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


def get_active_interview():
    """현재 대화 중인 인터뷰 대상자를 반환한다."""
    return _get_game_state()["active_interview"]


def start_interview_session(person):
    """인물별 인터뷰 세션을 시작하거나 이어서 연다."""
    state = _get_game_state()
    state["active_interview"] = person
    state["pending_interview_exit"] = False
    state["interview_topics"].setdefault(person, set())


def pause_interview_session():
    """확인한 주제는 보존하고 현재 인터뷰 화면만 종료한다."""
    state = _get_game_state()
    state["active_interview"] = None
    state["pending_interview_exit"] = False


def set_pending_interview_exit(pending=True):
    """인터뷰 종료 확인을 기다리는 상태를 저장한다."""
    _get_game_state()["pending_interview_exit"] = pending


def is_pending_interview_exit():
    """직전 문맥이 인터뷰 종료 확인이었는지 반환한다."""
    return _get_game_state()["pending_interview_exit"]


def set_pending_echo_action(action_name):
    """에코가 방금 제안하거나 되물은 행동을 저장한다."""
    _get_game_state()["pending_echo_action"] = action_name


def get_pending_echo_action():
    """짧은 후속 입력이 이어갈 에코의 직전 행동."""
    return _get_game_state()["pending_echo_action"]


def clear_pending_echo_action():
    """직전 에코 행동 문맥을 비운다."""
    _get_game_state()["pending_echo_action"] = None


def record_interview_topic(person, topic):
    """인물에게 확인한 주제를 기록하고 복사본을 반환한다."""
    state = _get_game_state()
    topics = state["interview_topics"].setdefault(
        person,
        set(),
    )
    was_new = topic not in topics
    topics.add(topic)
    state["interview_last_topics"][person] = topic
    counts = state["interview_topic_counts"].setdefault(
        person,
        {},
    )
    counts[topic] = counts.get(topic, 0) + 1
    return was_new, topics.copy()


def get_interview_topics(person):
    """특정 인물에게 확인한 대화 주제를 반환한다."""
    return _get_game_state()["interview_topics"].get(
        person,
        set(),
    ).copy()


def get_last_interview_topic(person):
    """짧은 후속 질문을 이해하기 위한 직전 대화 주제."""
    return _get_game_state()["interview_last_topics"].get(person)


def get_interview_topic_count(person, topic):
    """같은 인물에게 같은 주제를 질문한 누적 횟수."""
    return _get_game_state()["interview_topic_counts"].get(
        person,
        {},
    ).get(topic, 0)


def record_interview_observation(person, observation):
    """날카로운 질문으로 발견한 선택적 관찰을 기록한다."""
    observations = _get_game_state()[
        "interview_observations"
    ].setdefault(person, set())
    was_new = observation not in observations
    observations.add(observation)
    return was_new


def get_interview_observations(person):
    """특정 인물에게서 발견한 선택적 관찰을 반환한다."""
    return _get_game_state()["interview_observations"].get(
        person,
        set(),
    ).copy()


def mark_tutorial_event(event_name):
    """튜토리얼 안내가 같은 세션에서 한 번만 나오도록 기록한다."""
    events = _get_game_state()["tutorial_events"]

    if event_name in events:
        return False

    events.add(event_name)
    return True


def has_tutorial_event(event_name):
    """현재 세션에서 특정 튜토리얼 행동을 완료했는지 반환한다."""
    return event_name in _get_game_state()["tutorial_events"]


def set_tutorial_expected_action(action_name):
    """에코가 방금 제안한 1장 행동을 기억한다."""
    _get_game_state()["expected_tutorial_action"] = action_name


def get_tutorial_expected_action():
    """현재 에코가 플레이어의 동의를 기다리는 행동을 반환한다."""
    return _get_game_state()["expected_tutorial_action"]


def clear_tutorial_expected_action():
    """기대하던 행동이 실행됐거나 더 이상 유효하지 않을 때 지운다."""
    _get_game_state()["expected_tutorial_action"] = None


def get_cabin_observations():
    """현재까지 확인한 객실 세부 구역을 반환한다."""
    return _get_game_state()["cabin_observations"].copy()


def add_cabin_observation(observation_name):
    """객실 세부 관찰을 기록하고 모든 구역 확인 여부를 반환한다."""
    observations = _get_game_state()["cabin_observations"]
    observations.add(observation_name)

    return {
        "door",
        "table",
        "floor",
    }.issubset(observations)


def is_cabin_clue_followup(user_input):
    """
    사용자가 객실 기록의 실제 단서를 질문했는지 판정한다.

    사건 수첩 열람법 같은 UI 질문은 제외하고, 표현이 달라도
    같은 현장 개념을 가리키면 후속 질문으로 인정한다.
    """
    normalized = "".join(
        character
        for character in user_input.lower()
        if not character.isspace()
    )

    ui_intents = [
        "수첩",
        "기록볼",
        "기록보",
        "기록열",
        "열람",
        "어디서봐",
        "어떻게봐",
    ]
    if any(intent in normalized for intent in ui_intents):
        return False

    clue_concept_groups = [
        [
            "강제침입",
            "강제침임",
            "강제파손",
            "침입흔적",
            "침임흔적",
            "파손흔적",
            "문이안부서",
        ],
        [
            "출입문",
            "잠금장치",
            "문을열",
            "문열어",
            "열쇠",
            "카드키",
            "정상출입",
            "출입권한",
            "들어왔",
            "들여보",
            "들였",
            "아는사람",
            "그냥들어",
            "초대",
        ],
        [
            "물잔",
            "물컵",
            "약보관함",
            "약통",
            "복용",
            "테이블위",
            "탁자위",
        ],
        [
            "의자",
            "바닥매트",
            "매트주름",
            "가구배치",
            "어긋",
            "난투",
            "수색흔적",
            "정돈",
            "흐트러",
        ],
    ]

    return any(
        any(
            concept in normalized
            for concept in concept_group
        )
        for concept_group in clue_concept_groups
    )


def get_pending_tutorial_reminder():
    """중간 질문 뒤 아직 남아 있는 1장 행동을 한 번 상기시킨다."""
    if get_story_chapter()["number"] != 1:
        return None

    action_name = get_tutorial_expected_action()

    if not action_name:
        return None

    reminders = _get_game_state()["tutorial_reminders"]
    reminder_key = f"reminder:{action_name}"

    if reminder_key in reminders:
        return None

    reminder_messages = {
        "cabin": (
            "질문에 대한 확인은 마쳤습니다. 준비되셨다면 아까 "
            "말씀드린 **객실 출입문과 잠금장치 조사**를 이어가죠. "
            "`계속하자`라고 답하셔도 됩니다."
        ),
        "cabin_table": (
            "그럼 다시 객실 조사로 돌아가 볼까요? 다음은 "
            "**테이블과 그 위 물건**을 확인할 차례입니다. "
            "`계속 살펴보자`라고 말씀하셔도 됩니다."
        ),
        "cabin_floor": (
            "확인이 끝났다면 남은 **바닥과 가구 주변** 조사를 "
            "이어갈 수 있어요. `계속 조사하자`라고 말씀해 주세요."
        ),
        "cabin_followup": (
            "사건 수첩을 확인한 뒤, 객실 기록에서 마음에 걸리는 "
            "흔적 하나를 제게 질문해 주세요. 그 의미를 함께 "
            "정리해 보겠습니다."
        ),
        "forensic": (
            "준비되셨다면 다음으로 피해자의 **시신 상태와 사망 "
            "원인**을 조사해 보겠습니다. `계속하자`라고 하셔도 "
            "알아들을 수 있어요."
        ),
        "discovery": (
            "이제 남은 것은 신고부터 객실 개방까지의 **시신 발견 "
            "과정**입니다. 준비되셨다면 `계속하자`라고 말씀해 "
            "주세요."
        ),
    }
    message = reminder_messages.get(action_name)

    if not message:
        return None

    reminders.add(reminder_key)
    return message


def get_chapter_one_coach_message():
    """
    1장에서 완료된 행동 다음에 에코가 먼저 제안할 안내를 반환한다.

    같은 안내는 세션당 한 번만 반환하며, 플레이어가 조사 순서를
    바꾸면 아직 확보하지 않은 핵심 기록을 기준으로 안내한다.
    """
    if get_story_chapter()["number"] != 1:
        return None

    investigated = _get_investigated_set()
    events = _get_game_state()["tutorial_events"]
    cabin_observations = get_cabin_observations()

    if "SCENE_CABIN_INSPECTION" not in investigated:
        if "door" not in cabin_observations:
            set_tutorial_expected_action("cabin")

            if "coach_cabin" not in events:
                events.add("coach_cabin")
                return (
                    "객실의 **출입문과 잠금장치**부터 살펴보는 게 "
                    "좋겠어요.\n\n"
                    "저에게 **객실을 조사해 달라**고 말씀해 "
                    "주시겠어요? `피해자가 발견된 객실을 살펴봐`처럼 "
                    "편하게 말하셔도 됩니다."
                )

            return None

        if "table" not in cabin_observations:
            set_tutorial_expected_action("cabin_table")

            if "coach_cabin_table" not in events:
                events.add("coach_cabin_table")
                return (
                    "출입문 주변 확인을 마쳤어요. 이번에는 객실 "
                    "안쪽의 **테이블과 그 위 물건**을 살펴볼까요?\n\n"
                    "예를 들면 `테이블을 조사해 봐`처럼 말하거나, "
                    "간단히 `계속 살펴보자`라고 해도 됩니다."
                )

            return None

        if "floor" not in cabin_observations:
            set_tutorial_expected_action("cabin_floor")

            if "coach_cabin_floor" not in events:
                events.add("coach_cabin_floor")
                return (
                    "테이블 확인도 끝났어요. 아직 객실의 배치 "
                    "자체는 살펴보지 않았습니다.\n\n"
                    "마지막으로 **바닥과 가구 주변**을 확인해 "
                    "보시겠어요? 간단히 `계속 조사하자`라고 "
                    "말씀하셔도 됩니다."
                )

            return None

        return None

    if (
        "FORENSIC_POSTMORTEM" not in investigated
        and "cabin_record_followup" not in events
    ):
        set_tutorial_expected_action("cabin_followup")

        if "coach_cabin_followup" not in events:
            events.add("coach_cabin_followup")
            return (
                "객실 조사 기록을 사건 수첩에 추가했어요.\n\n"
                "원한다면 강제 침입 흔적이나 테이블 위 물건처럼 "
                "마음에 걸리는 부분을 골라 질문해 보세요. 바로 "
                "진행하려면 **피해자의 상태나 사망 원인을 확인해 "
                "달라**고 말씀하셔도 됩니다."
            )

        return None

    if "FORENSIC_POSTMORTEM" not in investigated:
        if "coach_forensic" not in events:
            events.add("coach_forensic")
            set_tutorial_expected_action("forensic")
            return (
                "좋은 질문이에요. 이렇게 확보한 기록의 의미를 "
                "다시 묻는 것이 이 조사의 핵심입니다.\n\n"
                "하지만 객실 흔적만으로는 피해자가 어떻게 "
                "사망했는지 알 수 없어요. 이번에는 저에게 "
                "**피해자의 사망 원인을 조사해 달라**고 "
                "말씀해 주시겠어요?"
            )
        return None

    if "SCENE_DISCOVERY_RECONSTRUCTION" not in investigated:
        if "coach_discovery" not in events:
            events.add("coach_discovery")
            set_tutorial_expected_action("discovery")
            return (
                "법의학 기록도 사건 수첩에 추가했어요. 여기서 "
                "한 가지를 구분해야 합니다. **23시 20분은 사망 "
                "시각이 아니라 발견 시각**이에요.\n\n"
                "이제 누가 신고했고 어떤 절차로 객실이 열렸는지 "
                "확인해 볼까요? 저에게 **시신 발견 과정을 조사해 "
                "달라**고 말씀해 주세요."
            )
        return None

    return None


MAX_HINTS = 3


STORY_CHAPTERS = {
    1: {
        "title": "객실에 남은 흔적",
        "transition": (
            "최종인의 죽음은 단순 사고가 아니었습니다. "
            "사건 당일의 진술을 확인할 차례입니다."
        ),
    },
    2: {
        "title": "네 사람의 진술",
        "transition": (
            "문은 부서지지 않았고 객실 전체를 뒤엎은 싸움도 "
            "없었습니다. 그러나 최종인은 누군가의 물리적 개입으로 "
            "사망했습니다.\n\n"
            "**사전에 확인된 공식 기록**\n\n"
            "8년 전 화물선 해성호는 악천후 속에서 좌초해 인명피해가 "
            "발생했습니다. 공식 조사에서는 조타계통 이상 가능성, "
            "현장 대응, 운항·안전관리 판단이 함께 지적됐고 당시 현장 "
            "책임자 김동율에게 상당한 책임이 부과됐습니다. 최종인은 "
            "사고 이후 자료와 보고를 정리하는 과정에 참여했습니다. "
            "다만 위험정보가 실제로 누구에게 어느 수준까지 전달됐는지는 "
            "이 공식 기록만으로 판단할 수 없습니다.\n\n"
            "한 사람은 8년 전의 원한을 품고 있었고, 한 사람은 "
            "그날 저녁 피해자와 충돌했습니다. 또 다른 사람은 "
            "과거 사고의 관계자였으며, 마지막 한 사람은 그가 "
            "나타나지 않자 객실 확인을 요청했습니다.\n\n"
            "**최종인은 마지막으로 누구를 믿었고, 누구의 말이 "
            "기록과 어긋나고 있을까요?**"
        ),
    },
    3: {
        "title": "존재하지 않는 21시 15분",
        "transition": (
            "메시지가 도착한 시간과 사람이 살아 있던 시간은 "
            "같지 않았습니다. 실제 범행 가능시간을 다시 구성해야 합니다."
        ),
    },
    4: {
        "title": "객실 밖의 76분",
        "transition": (
            "객실에 있었다는 진술은 출입기록으로 증명되지 "
            "않았습니다. 이제 8년 전 기록과의 연결을 확인해야 합니다."
        ),
    },
    5: {
        "title": "8년 전의 침묵",
        "transition": (
            "과거의 책임과 현재의 사건이 연결되었습니다. "
            "확보한 기록을 하나의 증거망으로 정리할 차례입니다."
        ),
    },
    6: {
        "title": "마지막 기록",
        "transition": (
            "핵심 조사기록이 모두 연결되었습니다. "
            "마지막 추리를 준비하십시오."
        ),
    },
}

CHAPTER_OBJECTIVES = {
    1: "객실 현장, 피해자의 상태와 시신 발견 과정을 확인하십시오.",
    2: "주요 관계자들의 기본 진술을 확보하고 서로 비교하십시오.",
    3: "피해자의 마지막 생존시각과 21시 15분 메시지를 검증하십시오.",
    4: "객실 출입기록과 알리바이를 대조해 범행 가능시간을 재구성하십시오.",
    5: "해성호 기록, 피해자의 재조사와 사라진 자료의 의미를 연결하십시오.",
    6: "확보한 기록을 바탕으로 범인·시간·동기·핵심 증거를 정리하십시오.",
}


CHAPTER_REQUIREMENTS = {
    2: {
        "SCENE_CABIN_INSPECTION",
        "FORENSIC_POSTMORTEM",
        "SCENE_DISCOVERY_RECONSTRUCTION",
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


def is_chapter_one_ready():
    """1장의 필수 기록이 모두 확보됐는지 반환한다."""
    return CHAPTER_REQUIREMENTS[2].issubset(
        _get_investigated_set()
    )


def get_chapter_one_reflection():
    """플레이어가 1장 끝에 기록한 첫 판단을 반환한다."""
    return _get_game_state()["chapter_one_reflection"]


def set_chapter_one_reflection(reflection_key):
    """1장의 첫 판단을 한 번 기록한다."""
    state = _get_game_state()

    if state["chapter_one_reflection"] is not None:
        return False

    state["chapter_one_reflection"] = reflection_key
    return True


def complete_chapter_one():
    """필수 기록 확보 후 플레이어가 1장을 직접 정리해 종료한다."""
    state = _get_game_state()

    if (
        not is_chapter_one_ready()
        or state["chapter_one_reflection"] is None
    ):
        return False

    state["chapter_one_closed"] = True
    clear_tutorial_expected_action()
    return True


def is_chapter_two_ready():
    """2장의 네 가지 기본 진술을 모두 확보했는지 반환한다."""
    return CHAPTER_REQUIREMENTS[3].issubset(
        _get_investigated_set()
    )


def get_chapter_two_reflection():
    """플레이어가 2장 끝에 선택한 검증 대상을 반환한다."""
    return _get_game_state()["chapter_two_reflection"]


def set_chapter_two_reflection(reflection_key):
    """2장의 진술 비교 판단을 한 번 기록한다."""
    state = _get_game_state()

    if state["chapter_two_reflection"] is not None:
        return False

    state["chapter_two_reflection"] = reflection_key
    return True


def complete_chapter_two():
    """진술 비교 판단 후 플레이어가 2장을 직접 종료한다."""
    state = _get_game_state()

    if (
        not is_chapter_two_ready()
        or state["chapter_two_reflection"] is None
    ):
        return False

    state["chapter_two_closed"] = True
    state["active_interview"] = None
    return True


def get_story_chapter():
    """완료한 핵심 조사로 현재 스토리 장을 계산한다."""
    investigated = _get_investigated_set()
    chapter_number = 1

    for next_chapter in range(2, 7):
        requirements = CHAPTER_REQUIREMENTS[
            next_chapter
        ]

        if requirements.issubset(investigated):
            if (
                next_chapter == 2
                and not _get_game_state()[
                    "chapter_one_closed"
                ]
            ):
                break
            if (
                next_chapter == 3
                and not _get_game_state()[
                    "chapter_two_closed"
                ]
            ):
                break
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
        "**현재 목표**\n\n"
        f"{CHAPTER_OBJECTIVES[chapter_number]}\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━"
    )


CHAPTER_ACTION_RULES = {
    "interview": {
        "minimum_chapter": 2,
        "direction": (
            "먼저 객실 현장, 사망원인과 시신 발견 과정을 "
            "확인해야 합니다."
        ),
    },
    "witness_general": {
        "minimum_chapter": 2,
        "direction": (
            "먼저 객실 현장, 사망원인과 시신 발견 과정을 "
            "확인해야 합니다."
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
        "SCENE_CABIN_INSPECTION",
        "FORENSIC_POSTMORTEM",
        "SCENE_DISCOVERY_RECONSTRUCTION",
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
    cabin_observations = state["cabin_observations"]

    categories = {
        category: _category_status(
            required_ids,
            investigated
        )
        for category, required_ids
        in INVESTIGATION_CATEGORIES.items()
    }
    title_to_id = {
        title: investigation_id
        for investigation_id, title
        in INVESTIGATION_TITLES.items()
    }
    notebook_entries = []

    for title in investigation_log:
        investigation_id = title_to_id.get(title)
        notebook_entries.append({
            "title": title,
            "content": _read_notebook_document(
                investigation_id
            ),
        })

    return {
        "current_stage": story_chapter["label"],
        "chapter_number": story_chapter["number"],
        "chapter_title": story_chapter["title"],
        "cabin_observations": cabin_observations.copy(),
        "cabin_observation_count": len(
            cabin_observations
        ),
        "completed_count": len(investigation_log),
        "all_records": investigation_log.copy(),
        "notebook_entries": notebook_entries,
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
                "SCENE_CABIN_INSPECTION",
                (
                    "사건이 시작된 장소에는 말보다 먼저 남은 흔적이 있습니다.",
                    "피해자가 발견된 객실의 출입문과 실내 상태를 살펴보십시오.",
                    "피해자 객실 현장을 조사해 강제 침입과 실내 흔적을 확인해 보십시오.",
                ),
            ),
            (
                "FORENSIC_POSTMORTEM",
                (
                    "사건의 출발점은 피해자의 상태와 현장입니다.",
                    "정확한 사망 시각을 판단하려면 먼저 사망 원인과 현장 상태를 확인해 보십시오.",
                    "피해자의 사망 원인과 현장 감식을 새롭게 조사해 보십시오.",
                ),
            ),
            (
                "SCENE_DISCOVERY_RECONSTRUCTION",
                (
                    "발견된 시간과 실제 사망한 시간은 같지 않을 수 있습니다.",
                    "누가 신고했고 어떤 절차로 객실을 열었는지 확인해 보십시오.",
                    "신고부터 시신 확인까지의 발견 경위를 재구성해 보십시오.",
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
