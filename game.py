from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from openai import OpenAI
import json
import time
from pathlib import Path

from game_director import decide_game_action
from interview_router import classify_interview_topic_semantically
from character_dialogue import (
    INTERVIEW_OPENINGS,
    INTERVIEW_DIALOGUE,
    INTERVIEW_REQUIREMENTS,
    INTERVIEW_RECORDS,
    INTERVIEW_SUMMARIES,
    get_repeat_response,
    OUT_OF_KNOWLEDGE_RESPONSES,
    WAITING_RESPONSES,
    classify_character_topic,
)
from game_state import (
    CHAPTER_OBJECTIVES,
    add_investigation,
    get_investigated,
    get_unlocked_documents,
    show_investigation_log,
    show_investigation_status,
    get_chapter_action_block,
    get_story_chapter,
    mark_tutorial_event,
    has_tutorial_event,
    get_tutorial_expected_action,
    clear_tutorial_expected_action,
    get_cabin_observations,
    add_cabin_observation,
    read_investigation_section,
    is_cabin_clue_followup,
    is_chapter_one_ready,
    get_active_interview,
    start_interview_session,
    pause_interview_session,
    record_interview_topic,
    get_interview_topics,
    record_interview_observation,
    get_interview_observations,
    get_last_interview_topic,
    get_interview_topic_count,
    set_pending_interview_exit,
    is_pending_interview_exit,
    set_pending_echo_action,
    get_pending_echo_action,
    clear_pending_echo_action,
    get_cached_interview_route,
    cache_interview_route,
    can_call_interview_router,
    record_interview_router_call,
)

load_dotenv()

client=OpenAI()


def get_start_message():
    """
    게임을 처음 실행했을 때 보여줄 사건 안내 메시지를 반환한다.

    화면 출력은 app.py가 담당하고, 사건 설정과 플레이 방법은
    game.py에서 관리하도록 역할을 분리한다.
    """

    return """
## 제1장 — 객실에 남은 흔적

**23시 20분. 비상 개방된 객실 안에서 최종인이 발견됐습니다.**

문은 부서지지 않았고 객실 전체가 크게 흐트러지지도 않았습니다.
그러나 그가 언제, 왜 죽었는지는 아직 설명되지 않습니다.

**현재 목표**

객실이 열리기 전까지 그 안에서 무슨 일이 있었는지 확인하십시오.

기록관 에코가 현장 기록을 동기화했습니다.
"""

# -------------------------
# 1. 저장된 Vector DB 불러오기
# -------------------------

embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)

candidate_retriever = vectorstore.as_retriever(
    search_kwargs={"k": 50}
)

# 권한 필터를 통과한 뒤 재정렬 모델에 보낼 후보 수를 제한한다.
# k=50은 아직 잠긴 문서가 섞인 공용 DB에서도 허용 문서를 찾기 위한
# 검색 폭이고, 실제 프롬프트에는 아래 개수만 전달한다.
MAX_RAG_CANDIDATES = 12


INITIAL_DOCUMENTS = {
    path.name
    for path in Path("./data/available").glob("*.md")
}


def retrieve_authorized_documents(search_query):
    """
    공용 Chroma DB에서 후보를 찾되, 현재 플레이어가 볼 수 있는
    초기 문서와 직접 해금한 문서만 RAG 후보로 통과시킨다.
    """
    allowed_documents = (
        INITIAL_DOCUMENTS
        | get_unlocked_documents()
    )

    candidates = candidate_retriever.invoke(
        search_query
    )

    authorized_documents = [
        document
        for document in candidates
        if document.metadata.get("source_file")
        in allowed_documents
    ]

    return authorized_documents[:MAX_RAG_CANDIDATES]

# -------------------------
# 2. Tool 정의
# -------------------------

def archive_investigation():
    """
    사용자가 해성호 과거 사고의 기록, 기술자료,
    위험정보 전달과정, 책임평가 등을 추가 조사해달라고
    명시적으로 요청했을 때 사용하는 조사 도구다.

    조사를 반복할수록 확보된 자료를 바탕으로
    더 깊은 단계의 과거자료를 조사한다.

    이미 확보된 자료의 내용을 단순히 묻는 질문에는 사용하지 않는다.
    """

    chapter_block = get_chapter_action_block("archive")
    if chapter_block:
        return chapter_block

    current_state = get_investigated()


    # 1단계
    # 해성호 기본 보존기록 조사
    if "ARCHIVE_HAESUNG_BASIC" not in current_state:

        add_investigation(
            "ARCHIVE_HAESUNG_BASIC"
        )

        return (
            "8년 전 해성호 사고의 보존 기술기록을 조사했습니다."
        )


    # 2단계
    # 사고 전 기술적 위험 심층조사
    if "ARCHIVE_TECHNICAL_RISK" not in current_state:

        add_investigation(
            "ARCHIVE_TECHNICAL_RISK"
        )

        return (
            "해성호 사고 전 조타계통의 기술적 위험과 "
            "초기 점검기록을 추가 조사했습니다."
        )


    # 3단계
    # 위험정보 전달과정
    if "ARCHIVE_INFORMATION_FLOW" not in current_state:

        add_investigation(
            "ARCHIVE_INFORMATION_FLOW"
        )

        return (
            "사고 전 위험정보가 어떤 과정으로 검토되고 "
            "현장에 전달되었는지 추가 조사했습니다."
        )


    # 4단계
    # 사고 후 책임평가
    if "ARCHIVE_RESPONSIBILITY" not in current_state:

        add_investigation(
            "ARCHIVE_RESPONSIBILITY"
        )

        return (
            "해성호 사고 후 책임평가 자료와 "
            "사고 전 실제 전달자료를 비교 조사했습니다."
        )


    # 5단계
    # 피해자 최종인의 개인 재분석
    if "DIGITAL_VICTIM_DEVICE_ACTIVITY" not in current_state:

        return (
            "과거 사고자료는 상당 부분 확보했지만, "
            "최종인이 이 자료들을 어떻게 재분석했는지는 "
            "피해자의 디지털 자료를 먼저 조사해야 확인할 수 있습니다."
        )


    if "ARCHIVE_VICTIM_ANALYSIS" not in current_state:

        add_investigation(
            "ARCHIVE_VICTIM_ANALYSIS"
        )

        return (
            "과거 사고자료와 피해자의 최근 디지털 활동을 대조해 "
            "최종인의 개인 재분석 기록을 확인했습니다."
        )


    return "현재 조사 가능한 해성호 과거자료는 모두 확인했습니다."

def digital_forensics():
    """
    사용자가 피해자의 디지털 자료를 새롭게 분석해달라고
    명시적으로 요청했을 때 사용하는 조사 도구다.

    조사를 반복할수록 다음 순서로 더 깊은 디지털 자료를 확인한다.

    1. 21:15 메시지 포렌식
    2. USB 사용 흔적
    3. 피해자의 최근 기기 활동

    이미 확보된 디지털 정보의 내용을 단순히 묻는 질문에는
    이 도구를 사용하지 않는다.
    """

    current_state = get_investigated()

    if "DIGITAL_MESSAGE_FORENSICS" not in current_state:
        chapter_block = get_chapter_action_block(
            "digital_message"
        )
    else:
        chapter_block = get_chapter_action_block(
            "digital_deep"
        )

    if chapter_block:
        return chapter_block


    # 1단계
    # 21:15 메시지 포렌식
    if "DIGITAL_MESSAGE_FORENSICS" not in current_state:

        add_investigation(
            "DIGITAL_MESSAGE_FORENSICS"
        )

        return (
            "21:15에 전송된 최종인 명의 메시지의 "
            "작성 및 전송기록을 디지털 포렌식했습니다."
        )


    # 2단계
    # USB 사용 흔적
    if "DIGITAL_USB_TRACE" not in current_state:

        add_investigation(
            "DIGITAL_USB_TRACE"
        )

        return (
            "최종인의 노트북에서 외부 저장장치 연결기록과 "
            "USB 사용 흔적을 추가 분석했습니다."
        )


    # 3단계
    # 최근 기기 활동 분석
    if "DIGITAL_VICTIM_DEVICE_ACTIVITY" not in current_state:

        add_investigation(
            "DIGITAL_VICTIM_DEVICE_ACTIVITY"
        )

        return (
            "최종인의 최근 노트북 사용기록과 "
            "해성호 관련 문서 활동을 추가 분석했습니다."
        )


    return "현재 조사 가능한 피해자의 디지털 자료는 모두 확인했습니다."


def access_log_analysis():
    """
    사용자가 강원모의 객실 출입기록이나
    객실 도어 시스템을 새롭게 분석해달라고 요청했을 때 사용하는 조사 도구다.

    조사를 반복할수록 다음 순서로 확인한다.

    1. 강원모 객실 출입 원시기록
    2. 객실 도어 시스템의 ENTRY / 퇴실 기록 구조

    이미 확보된 출입기록의 내용을 단순히 묻는 질문에는
    이 도구를 사용하지 않는다.
    """

    chapter_block = get_chapter_action_block("access")
    if chapter_block:
        return chapter_block

    current_state = get_investigated()


    # 1단계
    # 강원모 객실 출입 원시기록
    if "ACCESS_KANGWONMO_RAW" not in current_state:

        add_investigation(
            "ACCESS_KANGWONMO_RAW"
        )

        return (
            "강원모 객실의 카드키 출입 원시기록을 분석했습니다."
        )


    # 2단계
    # 객실 출입 시스템 구조 분석
    if "ACCESS_CABIN_SYSTEM" not in current_state:

        add_investigation(
            "ACCESS_CABIN_SYSTEM"
        )

        return (
            "객실 도어 시스템의 입실·퇴실 기록 생성방식을 "
            "추가 분석했습니다."
        )


    return "현재 조사 가능한 객실 출입기록과 시스템 정보는 모두 확인했습니다."


def timeline_alibi_check():
    """
    사용자가 지금까지 확보한 사건의 시간기록, 알리바이,
    출입기록 등을 서로 대조하거나 종합 분석해달라고
    명시적으로 요청했을 때 사용하는 조사 도구다.

    이미 확보된 특정 시각이나 사실 하나를 단순히 묻는 질문에는
    이 도구를 사용하지 않는다.
    """

    chapter_block = get_chapter_action_block("timeline")
    if chapter_block:
        return chapter_block

    current_state = get_investigated()

    # 타임라인 분석에 필요한 최소 정보 확인
    if "DIGITAL_MESSAGE_FORENSICS" not in current_state:
        return (
            "21:15 메시지의 정확한 성격이 아직 확인되지 않았습니다. "
            "먼저 디지털 포렌식을 진행할 필요가 있습니다."
        )

    if "WITNESS_LAST_CONFIRMED_ALIVE" not in current_state:
        return (
            "피해자의 마지막 확실한 생존시각이 아직 확인되지 않았습니다. "
            "마지막 생존 목격자를 먼저 조사할 필요가 있습니다."
        )

    result = [
        "현재까지 확보된 시간대 관련 자료를 종합 분석했습니다."
    ]

    # 21:15 메시지
    result.append(
        "- 21:15 메시지는 예약발송으로 확인되어 "
        "해당 시각 최종인의 생존을 직접 입증하지 못합니다."
    )

    # 마지막 생존
    result.append(
        "- 최종인은 약 19:55 객실 인근 복도에서 "
        "직접 목격되어 이 시점까지 생존한 것으로 확인됩니다."
    )

    # 김동율
    if "INTERVIEW_KIMDONGYUL_DEEP" in current_state:
        result.append(
            "- 김동율은 19시 40분대 후반 첫 접근과 "
            "20시 50분대 두 번째 방문 사실을 숨겼습니다. "
            "첫 접근 이후 피해자가 살아 있었으므로 "
            "첫 접근만으로 범행을 설명할 수는 없습니다."
        )

    # 김현준
    if "WITNESS_KIMHYUNJUN_MOVEMENT" in current_state:
        result.append(
            "- 김현준은 약 20:00~20:25 사이 "
            "연속적인 객관 동선이 확인되지 않습니다."
        )

    # 강원모
    if "ACCESS_KANGWONMO_RAW" in current_state:
        result.append(
            "- 강원모 객실에는 19:20과 20:36 두 차례 "
            "ENTRY 기록이 존재합니다."
        )

    if "ACCESS_CABIN_SYSTEM" in current_state:
        result.append(
            "- 객실 내부 퇴실 시 별도 카드 인증이 없어 "
            "정확한 퇴실시각은 기록되지 않습니다. "
            "따라서 강원모가 19:20부터 20:36까지 "
            "계속 객실에 있었다고 볼 수 없습니다."
        )

    # 최종 타임라인 문서 해금
    if "TIMELINE_ALIBI_ANALYSIS" not in current_state:
        add_investigation(
            "TIMELINE_ALIBI_ANALYSIS"
        )

    result.append(
        "- 현재 시간과 알리바이 자료만으로는 "
        "김동율, 김현준, 강원모 중 한 명을 "
        "범인으로 확정할 수 없습니다."
    )

    return "\n".join(result)



def interview(person: str):
    """
    사용자가 특정 인물을 실제로 인터뷰하거나 재인터뷰해달라고
    명시적으로 요청했을 때 사용하는 조사 도구다.

    인터뷰 가능 인물:
    - 김동율
    - 김현준
    - 강원모
    - 박소영

    이미 확보된 진술 내용을 단순히 묻는 질문에는 사용하지 않는다.

    예:
    - 김동율을 인터뷰해봐 → Tool 사용
    - 김동율은 뭐라고 진술했어? → Tool 사용하지 않음
    """

    chapter_block = get_chapter_action_block("interview")
    if chapter_block:
        return chapter_block

    current_state = get_investigated()


    # -------------------------
    # 김동율
    # -------------------------

    if person == "김동율":

        # 아직 기본 인터뷰를 하지 않은 경우
        if "INTERVIEW_KIMDONGYUL_BASIC" not in current_state:
            start_interview_session("김동율")
            completed_topics = get_interview_topics("김동율")
            resumed = bool(completed_topics)

            if resumed:
                return (
                    "## 인터뷰 재개 · 김동율\n\n"
                    "김동율이 굳은 표정으로 다시 자리에 앉았습니다.\n\n"
                    "> “남은 질문이 있다면 하십시오.”\n\n"
                    "피해자와의 관계, 8년 전 사고, 사건 당일 행적 "
                    "등을 자유롭게 질문할 수 있습니다. 인터뷰를 "
                    "멈추려면 **인터뷰 중단**이라고 말씀해 주세요."
                )

            return (
                "## 인터뷰 시작 · 김동율\n\n"
                "8년 전 해성호 사고의 현장 책임자였던 김동율이 "
                "팔짱을 낀 채 맞은편에 앉았습니다. 시선에는 "
                "경계와 오래된 분노가 함께 남아 있습니다.\n\n"
                "사건 초기 공식기록에 따르면 해성호는 악천후 속에서 "
                "좌초해 인명피해가 발생했고, 조타계통 이상 가능성과 "
                "현장 대응 문제가 함께 지적됐습니다. 김동율에게 "
                "상당한 책임이 부과됐으며 최종인은 사고 후 자료와 "
                "보고 정리에 참여했습니다.\n\n"
                "> “최종인에 관해 묻고 싶은 게 있다고 들었습니다. "
                "다만 처음부터 나를 범인으로 정해 놓고 묻지는 "
                "마십시오.”\n\n"
                "피해자와의 관계, 8년 전 사고, 사건 당일 행적처럼 "
                "궁금한 내용을 자유롭게 질문해 주세요."
            )

        # 객실구역 목격정보까지 확보했다면 심층 재인터뷰 가능
        if (
            "WITNESS_KIMDONGYUL_CORRIDOR"
            in current_state
            and
            "INTERVIEW_KIMDONGYUL_DEEP"
            not in current_state
        ):
            start_interview_session("김동율")
            return (
                "## 심층 재인터뷰 · 김동율\n\n"
                "객실구역 목격기록을 확보한 상태에서 김동율을 "
                "다시 불렀습니다. 그는 이전보다 굳은 표정으로 "
                "자리에 앉았습니다.\n\n"
                "> “또 같은 이야기를 하자는 겁니까?”\n\n"
                "확보한 목격내용을 구체적으로 제시해 그의 기존 "
                "진술과 대조해 보세요."
            )

        start_interview_session("김동율")
        return (
            "## 인터뷰 재개 · 김동율\n\n"
            "> “이미 기록할 말은 했습니다. 그래도 확인할 게 "
            "남았다면 물으십시오.”\n\n"
            "아직 묻지 않은 주제를 확인하거나 **인터뷰 중단**으로 "
            "대화를 마칠 수 있습니다."
        )


    # -------------------------
    # 김현준
    # -------------------------

    if person == "김현준":

        if "INTERVIEW_KIMHYUNJUN_BASIC" not in current_state:
            start_interview_session("김현준")
            return INTERVIEW_OPENINGS["김현준"]

        if (
            "WITNESS_KIMHYUNJUN_ARGUMENT"
            in current_state
            and
            "INTERVIEW_KIMHYUNJUN_DEEP"
            not in current_state
        ):
            start_interview_session("김현준")
            return (
                "## 심층 재인터뷰 · 김현준\n\n"
                "언쟁을 목격한 관계자의 기록을 확보한 뒤 김현준을 "
                "다시 불렀습니다. 그는 여전히 정중하지만 답변을 "
                "고르는 시간이 전보다 길어졌습니다.\n\n"
                "> “조사관님, 같은 대화에 관해 다시 확인하실 내용이 "
                "있습니까?”\n\n"
                "목격기록의 구체적인 내용을 제시해 기존 진술과 "
                "대조해 보세요."
            )

        start_interview_session("김현준")
        return (
            "## 인터뷰 재개 · 김현준\n\n"
            "> “조사관님, 추가로 확인할 내용이 있다면 "
            "답변드리겠습니다.”\n\n"
            "아직 묻지 않은 주제를 확인하거나 **인터뷰 중단**으로 "
            "대화를 마칠 수 있습니다."
        )


    # -------------------------
    # 강원모
    # -------------------------

    if person == "강원모":

        if "INTERVIEW_KANGWONMO_BASIC" not in current_state:
            start_interview_session("강원모")
            return INTERVIEW_OPENINGS["강원모"]

        # 출입기록 이상 또는 과거 정보전달 문제를 발견한 뒤 재인터뷰
        if (
            (
                "ACCESS_KANGWONMO_RAW"
                in current_state

                or

                "ARCHIVE_INFORMATION_FLOW"
                in current_state
            )
            and
            "INTERVIEW_KANGWONMO_FOLLOWUP"
            not in current_state
        ):
            start_interview_session("강원모")
            return (
                "## 추가 인터뷰 · 강원모\n\n"
                "새롭게 확보한 객실 출입 또는 과거 정보전달 기록을 "
                "앞에 두고 강원모와 다시 마주 앉았습니다.\n\n"
                "> “탐정님, 기록이 의미하는 범위를 정확히 구분해서 "
                "질문해 주십시오.”\n\n"
                "확보한 기록의 시각이나 내용을 구체적으로 제시해 "
                "기존 진술과 대조해 보세요."
            )

        start_interview_session("강원모")
        return (
            "## 인터뷰 재개 · 강원모\n\n"
            "> “탐정님, 이미 답한 범위 외에 확인할 내용이 "
            "있으십니까?”\n\n"
            "아직 묻지 않은 주제를 확인하거나 **인터뷰 중단**으로 "
            "대화를 마칠 수 있습니다."
        )


    # -------------------------
    # 박소영
    # -------------------------

    if person == "박소영":

        if "INTERVIEW_PARKSOYOUNG" not in current_state:
            start_interview_session("박소영")
            return INTERVIEW_OPENINGS["박소영"]

        start_interview_session("박소영")
        return (
            "## 인터뷰 재개 · 박소영\n\n"
            "> “제가 더 확인해 드릴 내용이 있다면 말씀해 주세요.”"
            "\n\n아직 묻지 않은 주제를 확인하거나 "
            "**인터뷰 중단**으로 대화를 마칠 수 있습니다."
        )


    # -------------------------
    # 등록되지 않은 인물
    # -------------------------

    return f"{person}은 현재 인터뷰 대상자로 등록되어 있지 않습니다."


KIMDONGYUL_DIALOGUE = {
    "relationship": (
        "## 김동율\n\n"
        "> “좋아하지 않았습니다. 그 사람이 정리한 기록 때문에 "
        "내 인생은 8년 동안 멈춰 있었으니까요. 그렇다고 사람을 "
        "죽일 이유가 된다는 말은 하지 마십시오.”"
    ),
    "haesung_overview": (
        "## 김동율\n\n"
        "> “8년 전 해성호가 악천후 속에서 좌초했고 인명피해가 "
        "발생했습니다. 조타계통 이상 가능성과 현장 대응 문제가 "
        "함께 거론됐지만, 공식 결과에서는 제 책임이 가장 크게 "
        "남았습니다.”"
    ),
    "haesung_role": (
        "## 김동율\n\n"
        "> “저는 당시 현장 책임자였습니다. 운항 현장에서 상황을 "
        "판단하고 대응해야 할 책임이 있었고, 제 판단에 아무 잘못도 "
        "없었다고 주장하는 건 아닙니다.”"
    ),
    "haesung_assessment": (
        "## 김동율\n\n"
        "> “공식 평가는 제가 사고 전 위험 가능성을 충분히 알았고도 "
        "대응하지 못한 사람처럼 정리했습니다. 제 책임은 인정하지만 "
        "사고 전체가 제 판단 하나로 일어난 것처럼 책임이 집중된 건 "
        "부당하다고 생각합니다.”"
    ),
    "haesung_victim_record": (
        "## 김동율\n\n"
        "> “최종인은 사고 뒤 자료와 보고를 정리하는 과정에 "
        "참여했습니다. 그 기록이 어떤 과정을 거쳐 최종 결론이 "
        "됐는지 제대로 설명하지 않았고, 그래서 저는 그 사람을 "
            "믿지 않았습니다.”"
    ),
    "cabin_knowledge": (
        "## 김동율\n\n"
        "> “행사 관계자였으니 최종인의 객실이 있는 구역 정도는 "
        "알고 있었습니다. 위치를 안다는 것과 그날 찾아갔다는 것은 "
        "전혀 다른 문제입니다.”"
    ),
    "alibi": (
        "## 김동율\n\n"
        "> “저녁 일정이 끝난 뒤에는 혼자 있었습니다. 최종인의 "
        "객실 쪽으로 찾아간 적도 없습니다.”"
    ),
    "victim_recent": (
        "## 김동율\n\n"
        "> “그 사람이 요즘 무엇을 준비했는지는 모릅니다. 나한테 "
        "제대로 설명하려 한 적도 없으니까요.”"
    ),
    "motive": (
        "## 김동율\n\n"
        "> “원망한 것과 죽인 것은 전혀 다른 문제입니다. 감정이 "
        "있었다는 이유만으로 결론을 정해 놓고 묻지는 마십시오.”"
    ),
}


KIMDONGYUL_TURN_TOOL = {
    "type": "function",
    "name": "answer_as_kim_dongyul",
    "description": (
        "허용된 제2장 진술만 사용해 김동율의 대화 응답을 만든다."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "enum": [
                    "relationship",
                    "haesung_overview",
                    "haesung_role",
                    "haesung_assessment",
                    "haesung_victim_record",
                    "cabin_knowledge",
                    "alibi",
                    "victim_recent",
                    "motive",
                    "unclear",
                ],
            },
            "reply": {
                "type": "string",
                "description": (
                    "김동율이 직접 말하는 자연스러운 한국어 "
                    "1~3문장. 이름표나 Markdown 제목은 쓰지 않는다."
                ),
            },
        },
        "required": ["topic", "reply"],
        "additionalProperties": False,
    },
}


def _generate_kimdongyul_turn(
    user_input,
    preferred_topic=None,
):
    """허용된 사실 안에서 김동율의 자연스러운 대화를 생성한다."""
    last_topic = get_last_interview_topic("김동율")
    allowed_statements = {
        "relationship": (
            "최종인을 좋아하지 않았고, 최종인이 정리한 기록 때문에 "
            "자신의 인생이 8년 동안 멈췄다고 생각한다. 원망과 "
            "살인은 다른 문제라고 강하게 말한다."
        ),
        "haesung_overview": (
            "8년 전 해성호가 악천후 속에서 좌초해 인명피해가 "
            "발생했고, 조타계통 이상 가능성과 현장 대응 문제가 "
            "거론됐지만 공식 결과에서는 자신의 책임이 가장 크게 "
            "남았다고 말한다."
        ),
        "haesung_role": (
            "당시 현장 책임자로서 운항 현장에서 상황을 판단하고 "
            "대응할 책임이 있었으며 자신의 판단에도 일부 책임이 "
            "있음을 인정한다."
        ),
        "haesung_assessment": (
            "공식 평가가 자신이 위험을 충분히 알고도 대응하지 않은 "
            "것처럼 정리했으며 사고 전체의 책임이 과도하게 자신에게 "
            "집중됐다고 주장한다."
        ),
        "haesung_victim_record": (
            "최종인이 사고 후 자료와 보고 정리에 참여했지만 기록이 "
            "최종 결론이 된 과정을 설명하지 않아 불신한다고 말한다."
        ),
        "cabin_knowledge": (
            "행사 관계자로서 최종인의 객실이 있는 구역 정도는 "
            "알았지만 사건 당일 찾아가지는 않았다고 주장한다."
        ),
        "alibi": (
            "저녁 일정 이후 혼자 있었으며 최종인의 객실 쪽으로 "
            "찾아가지 않았다고 주장한다."
        ),
        "victim_recent": (
            "최종인이 최근 무엇을 준비했는지 모르며 자신에게 "
            "제대로 설명하지 않았다고 말한다."
        ),
        "motive": (
            "최종인을 원망한 사실은 인정하지만 그것이 살인을 "
            "의미하지는 않는다고 반발한다."
        ),
    }
    if (
        preferred_topic
        and preferred_topic in allowed_statements
    ):
        allowed_for_turn = {
            preferred_topic: allowed_statements[
                preferred_topic
            ]
        }
        topic_instruction = (
            f"플레이어 질문은 코드에서 '{preferred_topic}' "
            "주제로 확정했다. 이 주제를 절대 다른 주제로 "
            "바꾸지 않는다."
        )
        context_topic = "사용하지 않음"
    else:
        allowed_for_turn = allowed_statements
        topic_instruction = (
            "코드에서 명확한 주제를 찾지 못했다. 질문 자체에 "
            "허용 주제가 분명히 드러날 때만 해당 주제를 고르고, "
            "막연한 추궁이나 의미가 불분명한 말은 unclear로 한다."
        )
        context_topic = "참고하지 않음"

    prompt = f"""
너는 추리게임 제2장의 인터뷰 인물 '김동율'로만 대답한다.

[말투]
- 8년 동안 쌓인 억울함과 분노가 있지만 존댓말을 유지한다.
- 짧고 단정적으로 말한다.
- 의심받으면 질문의 전제를 되묻거나 반발한다.
- 매번 같은 문장을 반복하지 말고 질문에 직접 답한다.

[이번 장에서 말할 수 있는 사실]
{json.dumps(allowed_for_turn, ensure_ascii=False)}

[절대 규칙]
1. 위 사실 밖의 사건 정보, 시간, 동선, 증거를 새로 만들지 않는다.
2. 객실구역 방문을 인정하지 않는다.
3. 범인, USB, 예약 메시지, 다른 인물의 행동을 추측하지 않는다.
4. 직전 주제를 근거로 막연한 질문의 의미를 임의로 만들지 않는다.
5. 관련 없는 질문이면 topic을 unclear로 하고 김동율 말투로
   무엇을 묻는지 짧게 되묻는다.
6. 답변은 1~3문장으로 한다.
7. 조사와 어미를 정확히 사용하고, 의미가 불분명한 문장을 만들지
   않는다.

[규칙 기반 예상 주제]
{preferred_topic or "없음"}
{topic_instruction}

[직전 대화 주제]
{context_topic}

[플레이어 질문]
{user_input}
"""
    try:
        response = client.responses.create(
            model="gpt-4.1-mini",
            input=prompt,
            tools=[KIMDONGYUL_TURN_TOOL],
            tool_choice={
                "type": "function",
                "name": "answer_as_kim_dongyul",
            },
        )
    except Exception:
        return None

    for item in response.output:
        if (
            item.type == "function_call"
            and item.name == "answer_as_kim_dongyul"
        ):
            try:
                result = json.loads(item.arguments)
            except (TypeError, json.JSONDecodeError):
                return None

            topic = result.get("topic")
            reply = str(result.get("reply", "")).strip()
            if (
                topic
                not in {
                    "relationship",
                    "haesung_overview",
                    "haesung_role",
                    "haesung_assessment",
                    "haesung_victim_record",
                    "cabin_knowledge",
                    "alibi",
                    "victim_recent",
                    "motive",
                    "unclear",
                }
                or not reply
            ):
                return None

            if (
                preferred_topic
                and topic != preferred_topic
            ):
                return None

            forbidden_reply_terms = (
                "강원모가 범인",
                "USB",
                "유에스비",
                "예약발송",
                "20시 15분",
                "범행 시각",
                "최종인도 때",
            )
            if any(
                term in reply
                for term in forbidden_reply_terms
            ):
                return None

            return {
                "topic": topic,
                "reply": reply,
            }

    return None


def _normalize_interview_input(user_input):
    return "".join(
        character
        for character in user_input.lower()
        if not character.isspace()
    )


def _with_object_particle(name):
    """인물 이름에 맞는 목적격 조사 을/를을 붙인다."""
    last_character = name[-1]
    if "가" <= last_character <= "힣":
        has_final_consonant = (
            (ord(last_character) - ord("가")) % 28
            != 0
        )
        return name + ("을" if has_final_consonant else "를")
    return name + "을"


CASE_TIME_CONTEXT = {
    "current_phase": "사건 당일 밤, 시신 발견 이후",
    "discovery_time": "23시 20분",
    "exact_calendar_date": None,
}


def _state_based_time_response(user_input):
    """달력 날짜를 꾸며내지 않고 사건의 상대 시간축을 일관되게 답한다."""
    normalized = _normalize_interview_input(user_input)
    time_terms = (
        "오늘", "어제", "사건당일", "사건날", "현재",
        "지금", "며칠", "몇일", "날짜",
    )
    if not any(term in normalized for term in time_terms):
        return None

    asks_exact_date = (
        any(term in normalized for term in ("며칠", "몇일"))
        and any(
            term in normalized
            for term in ("오늘", "사건당일", "사건날")
        )
    ) or any(
        term in normalized
        for term in ("무슨날짜", "날짜가")
    )
    asks_incident_is_today = (
        any(
            term in normalized
            for term in ("사건당일이오늘", "사건날이오늘")
        )
    )
    asks_current_time_context = any(
        term in normalized
        for term in ("현재언제", "지금언제", "현재시점", "지금시점")
    )

    if asks_exact_date:
        return (
            "사건의 정확한 연·월·일은 현재 기록에 정해져 있지 "
            "않습니다. 다만 게임의 현재 시점은 **사건 당일 밤, "
            f"{CASE_TIME_CONTEXT['discovery_time']} 이후**입니다."
        )
    if asks_incident_is_today:
        return (
            "네. **현재 조사는 사건 당일 밤**, 최종인이 객실에서 "
            f"발견된 **{CASE_TIME_CONTEXT['discovery_time']} 이후**에 "
            "진행되고 있습니다. 23시 20분은 사망 시각이 아니라 "
            "시신 발견 시각입니다."
        )
    if asks_current_time_context:
        return (
            "현재는 **사건 당일 밤**, 최종인이 객실에서 발견된 "
            f"**{CASE_TIME_CONTEXT['discovery_time']} 이후**입니다."
        )
    return None


def _classify_kimdongyul_topic(user_input):
    """2장 김동율 질문을 허용된 고정 대화 주제로 분류한다."""
    normalized = _normalize_interview_input(user_input)

    cabin_knowledge_concepts = (
        "객실을알", "객실알", "방을알", "방알",
        "객실위치", "객실번호", "몇호",
        "방위치", "어디있는지", "객실이어딘지",
    )
    if any(
        concept in normalized
        for concept in cabin_knowledge_concepts
    ):
        return "cabin_knowledge"

    access_pressure_concepts = (
        "객실복도", "객실구역", "피해자방", "최종인방",
        "방근처", "복도에서", "찾아갔", "만나러갔",
        "객실쪽", "문앞", "목격됐", "목격자", "봤다는데",
        "오세훈", "객실에들어", "방에들어", "안들어갔",
        "들어간적", "들어갔어", "들어갔나",
    )
    if any(
        concept in normalized
        for concept in access_pressure_concepts
    ):
        return "access_pressure"

    victim_is_subject = any(
        concept in normalized
        for concept in ("최종인", "그사람", "피해자")
    )
    asks_victim_record_role = any(
        concept in normalized
        for concept in ("기록", "보고", "정리", "참여", "역할")
    )
    asks_victim_past_action = (
        any(
            concept in normalized
            for concept in ("8년전", "사고때", "당시", "그때")
        )
        and any(
            concept in normalized
            for concept in ("뭐했", "무슨일", "관련", "관여")
        )
    )
    if (
        victim_is_subject
        and (
            asks_victim_record_role
            or asks_victim_past_action
        )
    ):
        return "haesung_victim_record"

    if any(
        concept in normalized
        for concept in (
            "어떤책임", "무슨책임", "현장책임이뭐",
            "현장책임은", "맡은역할", "맡은책임", "무슨역할",
            "담당", "뭘책임", "너의책임", "네책임", "니책임",
        )
    ):
        return "haesung_role"

    if any(
        concept in normalized
        for concept in (
            "왜책임", "책임집중", "책임이집중", "공식평가",
            "공식조사", "부당", "억울", "평가결과",
            "뒤집어", "독박", "희생양",
        )
    ):
        return "haesung_assessment"

    topic_concepts = {
        "alibi": (
            "사건당일", "그날", "저녁", "어디", "행적", "동선",
            "객실", "방에", "뭐했", "무엇을했", "알리바이",
            "본사람", "증명", "혼자였",
        ),
        "haesung_overview": (
            "해성호", "8년전", "과거사고", "사고당시", "현장책임",
            "책임자", "좌초", "무슨사고", "사고가뭐",
            "어떤사고", "사고내용",
        ),
        "motive": (
            "죽일이유", "살해동기", "범인", "죽였", "살인", "동기",
            "원한때문", "복수",
        ),
        "victim_recent": (
            "최근", "요즘", "준비", "조사", "자료", "뭘하고",
            "무엇을하고", "달라진", "이상한점",
        ),
        "relationship": (
            "관계", "사이", "싫어", "좋아", "미워", "원망", "감정",
            "최종인을어떻게", "친했", "알게된",
        ),
    }

    for topic, concepts in topic_concepts.items():
        if any(concept in normalized for concept in concepts):
            return topic

    return None


INTERVIEW_TOPIC_LABELS = {
    "김동율": {
        "relationship": "피해자와의 관계",
        "haesung_overview": "해성호 사고의 개요",
        "haesung_role": "김동율의 당시 현장 역할",
        "haesung_assessment": "공식 책임평가에 대한 입장",
        "haesung_victim_record": "최종인의 사고 기록 참여",
        "cabin_knowledge": "피해자 객실 위치 인지 여부",
        "alibi": "사건 당일 행적",
        "victim_recent": "피해자의 최근 행동",
        "motive": "피해자에 대한 원한",
    },
    "김현준": {
        "relationship": "피해자와의 관계",
        "contract": "계약 문제",
        "contract_detail": "계약 절차를 둘러싼 구체적인 이견",
        "argument": "사건 당일 대화",
        "argument_detail": "대화 당시 언쟁의 강도",
        "consequence": "갈등으로 예상된 불이익",
        "alibi": "대화 이후 사건 당일 행적",
    },
    "강원모": {
        "relationship": "피해자와의 관계",
        "alibi": "사건 당일 행적",
        "haesung": "해성호 사고 당시 역할",
        "victim_recent": "피해자의 최근 행동",
    },
    "박소영": {
        "relationship": "피해자와의 관계",
        "message": "21시 15분 메시지",
        "absence": "약속 불참과 연락 과정",
        "discovery": "객실 확인 요청 과정",
    },
}


def _chapter_two_remaining_interviews():
    """아직 기본 진술이 완성되지 않은 2장 인물 목록."""
    required = {
        "김동율": "INTERVIEW_KIMDONGYUL_BASIC",
        "김현준": "INTERVIEW_KIMHYUNJUN_BASIC",
        "강원모": "INTERVIEW_KANGWONMO_BASIC",
        "박소영": "INTERVIEW_PARKSOYOUNG",
    }
    investigated = get_investigated()
    return [
        person
        for person, investigation_id in required.items()
        if investigation_id not in investigated
    ]


INTERVIEW_RECORD_IDS = {
    "김동율": "INTERVIEW_KIMDONGYUL_BASIC",
    "김현준": "INTERVIEW_KIMHYUNJUN_BASIC",
    "강원모": "INTERVIEW_KANGWONMO_BASIC",
    "박소영": "INTERVIEW_PARKSOYOUNG",
}


def _completed_interview_people():
    """현재 플레이어가 실제 완료한 기본 인터뷰 대상자."""
    investigated = get_investigated()
    return [
        person
        for person, record_id in INTERVIEW_RECORD_IDS.items()
        if record_id in investigated
    ]


def _state_based_case_summary():
    """현재 플레이어가 실제 확보한 상태만으로 사건을 요약한다."""
    investigated = get_investigated()
    chapter = get_story_chapter()
    lines = [
        "피해자 최종인(62세)은 약 **23시 20분**, 자신의 객실에서 "
        "사망한 상태로 발견됐습니다. 23시 20분은 사망 시각이 아니라 "
        "발견 시각입니다.",
    ]
    if "SCENE_CABIN_INSPECTION" in investigated:
        lines.append(
            "객실 출입문에는 외부 강제 파손 흔적이 없었고, 객실 "
            "전체를 뒤엎은 대규모 난투 흔적도 뚜렷하지 않았습니다."
        )
    if "FORENSIC_POSTMORTEM" in investigated:
        lines.append(
            "법의학 소견은 경부 압박에 의한 질식성 사망과 "
            "부합하지만 정확한 사망 시각과 범인은 확정되지 않았습니다."
        )
    completed = _completed_interview_people()
    if completed:
        lines.append(
            "현재 완료한 기본 인터뷰는 **"
            + ", ".join(completed)
            + "**입니다."
        )
    else:
        lines.append("아직 완료하여 보관한 기본 인터뷰는 없습니다.")
    return (
        f"### 현재 사건 요약 · {chapter['label']}\n\n"
        + "\n\n".join(lines)
        + "\n\n아직 확보하지 않은 기록은 요약에 포함하지 않았습니다."
    )


def get_current_action_capabilities():
    """현재 장과 조사 상태에서 실제 실행 가능한 행동만 반환한다."""
    chapter_number = get_story_chapter()["number"]
    if chapter_number == 1:
        next_action = get_required_next_action()
        labels = {
            "cabin": "피해자 객실 현장 조사",
            "cabin_table": "객실 테이블과 물품 조사",
            "cabin_floor": "객실 바닥과 가구 조사",
            "forensic": "피해자 법의학 조사",
            "discovery": "시신 발견 과정 조사",
        }
        return [labels[next_action]] if next_action in labels else []
    if chapter_number == 2:
        return [
            f"{person} 기본 인터뷰"
            for person in _chapter_two_remaining_interviews()
        ]
    if chapter_number == 3:
        return [
            "피해자의 마지막 생존 목격 조사",
            "21시 15분 메시지 디지털 포렌식",
        ]
    if chapter_number == 4:
        return [
            "객실 출입기록 분석",
            "인물별 알리바이와 시간선 대조",
        ]
    if chapter_number == 5:
        return [
            "해성호 보존기록 조사",
            "피해자의 과거자료 재검토 흔적 분석",
        ]
    return ["확보한 증거 정리와 최종 추리"]


def _suggest_next_chapter_two_interview():
    """2장에서 실제 가능한 다음 인터뷰를 문맥 행동으로 저장한다."""
    remaining = _chapter_two_remaining_interviews()
    if not remaining:
        clear_pending_echo_action()
        return (
            "네 사람의 기본 진술을 모두 확보했습니다. 사건 수첩에서 "
            "진술을 비교하고 먼저 검증할 항목을 선택하세요."
        )
    person = remaining[0]
    set_pending_echo_action(f"interview:{person}")
    return (
        f"현재 실행 가능한 다음 행동은 **{person} 기본 인터뷰**입니다. "
        "`진행해` 또는 `조사해봐`라고 답하면 인터뷰를 시작하겠습니다."
    )


def _capability_aware_echo_response(user_input):
    """미지원 조사를 권하지 않고 실제 게임 행동으로만 안내한다."""
    normalized = _normalize_interview_input(user_input)
    pending = get_pending_echo_action()
    affirmative = {
        "조사해봐", "조사해", "진행해", "진행하자",
        "해봐", "해줘", "그거해", "그렇게해", "응",
        "그래", "좋아",
    }
    if normalized.rstrip("?!.,") in affirmative and pending:
        if pending.startswith("interview:"):
            person = pending.split(":", 1)[1]
            clear_pending_echo_action()
            return interview(person)
        if pending == "clarify:cabin_layout":
            return (
                "확인하려는 대상이 두 가지로 나뉩니다. **객실 내부 "
                "구조**인지, **선내에서 피해자 객실이 있는 구역 "
                "위치**인지 말씀해 주세요."
            )

    asks_dongyul_cabin_knowledge = (
        any(name in user_input for name in ("김동율", "김동률"))
        and any(
            term in normalized
            for term in (
                "객실을알", "객실위치", "객실번호",
                "몇호", "방위치",
            )
        )
    )
    if asks_dongyul_cabin_knowledge:
        topics = get_interview_topics("김동율")
        if "cabin_knowledge" in topics:
            return (
                "김동율은 행사 관계자로서 최종인의 객실이 있는 "
                "구역 정도는 알고 있었다고 답했습니다. 다만 사건 "
                "당일 그 구역을 찾아간 사실은 부정하고 있습니다."
            )
        return (
            "김동율은 사건 당일 객실구역 방문을 부정했지만, 객실 "
            "위치를 알고 있었는지는 아직 직접 확인하지 않았습니다. "
            "위치 인지와 실제 방문은 별개의 사실이므로 재인터뷰에서 "
            "구분해 질문할 수 있습니다."
        )

    if any(
        term in normalized
        for term in ("객실배치도", "객실도면", "배치도")
    ):
        set_pending_echo_action("clarify:cabin_layout")
        return (
            "말씀하신 배치도가 **객실 내부 구조**인지, 아니면 "
            "**선내에서 피해자 객실이 있는 구역 위치**인지 "
            "구분이 필요합니다. 어느 쪽을 확인하려는 건가요?"
        )

    if pending == "clarify:cabin_layout":
        if any(
            term in normalized
            for term in ("내부", "가구", "방안", "객실구조")
        ):
            clear_pending_echo_action()
            if "SCENE_CABIN_INSPECTION" in get_investigated():
                return (
                    "정식 설계도는 조사 대상으로 등록되어 있지 "
                    "않습니다. 다만 확보한 객실 현장기록에서 출입문, "
                    "테이블, 바닥과 가구 주변 상태를 확인할 수 있습니다."
                )
            return (
                "객실 내부 구조를 확인하려면 먼저 피해자 객실 "
                "현장조사를 진행해야 합니다."
            )
        if any(
            term in normalized
            for term in ("선내", "구역", "위치", "몇층", "어디")
        ):
            clear_pending_echo_action()
            return (
                "선내 전체 객실 배치도는 이 사건의 조사 대상으로 "
                "등록되어 있지 않습니다. 특정 인물이 피해자 객실 "
                "위치를 알고 있었는지는 해당 인물에게 직접 확인하고, "
                "이후 확보되는 동선·목격기록과 대조해야 합니다."
            )

    unsupported_facility = any(
        term in normalized
        for term in (
            "시설관리기록", "시설관리", "설계도",
            "선박도면", "객실설계",
        )
    )
    if unsupported_facility:
        clear_pending_echo_action()
        response = (
            "선내 시설관리기록과 설계도는 현재 사건의 조사 대상으로 "
            "등록되어 있지 않습니다. 에코는 이 자료를 새로 확보할 "
            "수 있다고 약속하지 않겠습니다.\n\n"
        )
        if get_story_chapter()["number"] == 2:
            response += _suggest_next_chapter_two_interview()
        else:
            response += (
                "현재 실행 가능한 행동은 **"
                + ", ".join(get_current_action_capabilities())
                + "**입니다."
            )
        return response

    if any(
        term in normalized
        for term in ("cctv", "씨씨티비", "폐쇄회로")
    ):
        clear_pending_echo_action()
        response = (
            "현재 확보한 사건 기록에는 실행 가능한 CCTV 조사 항목이 "
            "없습니다. 확인되지 않은 영상이 존재한다고 가정하거나 "
            "CCTV 확보를 다음 행동으로 권하지 않겠습니다.\n\n"
            "인물의 이동을 확인하려는 목적이라면 실제 게임에서 "
            "해금되는 목격기록과 출입기록을 이용해야 합니다. "
        )
        if get_story_chapter()["number"] == 2:
            response += _suggest_next_chapter_two_interview()
        else:
            response += (
                "현재 실행 가능한 행동은 **"
                + ", ".join(get_current_action_capabilities())
                + "**입니다."
            )
        return response

    if pending:
        clear_pending_echo_action()
    return None


def _deep_interview_guidance(user_input):
    """증거 없이 '심층조사'라는 말만으로 진술이 열리지 않게 한다."""
    normalized = _normalize_interview_input(user_input)
    if not any(
        word in normalized
        for word in ("심층조사", "심층인터뷰", "재인터뷰")
    ):
        return None

    aliases = {
        "김동율": ("김동율", "김동률"),
        "김현준": ("김현준",),
        "강원모": ("강원모",),
        "박소영": ("박소영",),
    }
    person = next(
        (
            canonical
            for canonical, names in aliases.items()
            if any(name in user_input for name in names)
        ),
        None,
    )
    if person is None:
        return (
            "심층 재인터뷰할 인물을 구체적으로 말씀해 주세요. "
            "새로운 진술은 해당 인물의 기본 인터뷰와 관련 객관 "
            "기록을 모두 확보했을 때만 열립니다."
        )

    investigated = get_investigated()
    if INTERVIEW_RECORD_IDS[person] not in investigated:
        return (
            f"{person}의 기본 인터뷰부터 완료해야 합니다. "
            f"`{_with_object_particle(person)} 인터뷰하자`라고 "
            "말씀해 주세요."
        )

    evidence_requirements = {
        "김동율": "WITNESS_KIMDONGYUL_CORRIDOR",
        "김현준": "WITNESS_KIMHYUNJUN_ARGUMENT",
        "강원모": "ACCESS_KANGWONMO_RAW",
    }
    required_evidence = evidence_requirements.get(person)
    if required_evidence and required_evidence in investigated:
        return interview(person)

    return (
        f"{person}의 기본 진술은 확보했습니다. 하지만 현재 보유한 "
        "기록만으로 진술을 바꿀 근거는 없습니다. 다른 인물의 진술과 "
        "객관 기록을 조사한 뒤, 충돌하는 기록을 직접 제시해야 "
        "심층 재인터뷰가 진행됩니다."
    )


def _state_based_testimony_response(user_input):
    """RAG 전에 실제 인터뷰 상태만으로 진술 질문에 답한다."""
    normalized = _normalize_interview_input(user_input)
    people = tuple(INTERVIEW_RECORD_IDS)
    mentioned_person = next(
        (
            person
            for person in people
            if person in user_input
            or (
                person == "김동율"
                and "김동률" in user_input
            )
        ),
        None,
    )
    asks_interview_status = (
        mentioned_person
        and any(
            word in normalized
            for word in (
                "인터뷰", "진술", "말한", "뭐라고", "뭐라",
            )
        )
        and any(
            word in normalized
            for word in (
                "했", "언제", "어디서", "어디", "출처",
                "나왔", "확보", "있어", "정리", "요약",
            )
        )
    )
    asks_summary = (
        any(
            word in normalized
            for word in ("진술", "인터뷰")
        )
        and any(
            word in normalized
            for word in (
                "정리", "요약", "지금까지", "확보",
                "뭐라고", "뭐라", "내용", "뭐야",
                "뭔데", "알려",
            )
        )
    )

    if not asks_interview_status and not asks_summary:
        return None

    completed = _completed_interview_people()
    if mentioned_person:
        if mentioned_person not in completed:
            interview_command = {
                "김동율": "김동율을 인터뷰하자",
                "김현준": "김현준을 인터뷰하자",
                "강원모": "강원모를 인터뷰하자",
                "박소영": "박소영을 인터뷰하자",
            }[mentioned_person]
            return (
                f"**{mentioned_person}의 정식 인터뷰는 아직 완료하지 "
                "않았습니다.** 사건 초기 기록에 간단한 사전 진술이 "
                "포함되어 있을 수 있지만, 그것을 플레이어가 확보한 "
                "인터뷰 기록으로 취급할 수는 없습니다.\n\n"
                f"진행하려면 `{interview_command}`라고 "
                "말씀해 주세요."
            )

        if mentioned_person == "김동율":
            summary = (
                "최종인에 대한 원한과 해성호 공식 책임평가에 대한 "
                "불만을 인정했고, 사건 당일에는 저녁 일정 이후 혼자 "
                "있었으며 피해자 객실구역에 가지 않았다고 주장했습니다."
            )
        else:
            summary = INTERVIEW_SUMMARIES[mentioned_person]
        return (
            f"**{mentioned_person} 기본 인터뷰는 확보되어 있습니다.**\n\n"
            + summary
            + "\n\n인터뷰 완료 시각을 별도로 기록하는 시스템은 "
            "현재 없으며, 게임 진행상 확보 여부만 관리합니다."
        )

    if not completed:
        return (
            "현재 완료하여 사건 수첩에 보관한 기본 인터뷰는 없습니다. "
            "초기 사건자료에 있는 짧은 사전 진술은 정식 인터뷰와 "
            "구분됩니다."
        )

    summary_lines = []
    for person in completed:
        topics = get_interview_topics(person)
        labels = INTERVIEW_TOPIC_LABELS[person]
        heard = [
            label
            for topic, label in labels.items()
            if topic in topics
        ]
        topic_text = ", ".join(heard) if heard else "기본 진술"
        summary_lines.append(f"- **{person}** — {topic_text}")

    remaining = [
        person
        for person in people
        if person not in completed
    ]
    response = (
        "현재 실제로 완료한 기본 인터뷰는 다음과 같습니다.\n\n"
        + "\n".join(summary_lines)
    )
    if remaining:
        response += (
            "\n\n아직 완료하지 않은 인터뷰: **"
            + ", ".join(remaining)
            + "**"
        )
    return response


def _next_interview_guidance(person, topics):
    """정답 목록 대신 현재 대화에서 자연스러운 다음 방향 하나를 제안한다."""
    if person == "김동율":
        if "relationship" not in topics:
            return (
                "김동율이 최종인에게 품은 감정이 어디에서 시작됐는지 "
                "확인해 보세요."
            )
        if "haesung_overview" not in topics:
            return (
                "두 사람의 갈등이 시작된 8년 전 해성호 사고가 어떤 "
                "사건이었는지부터 물어보는 편이 좋겠습니다."
            )
        if not {
            "haesung_role",
            "haesung_assessment",
            "haesung_victim_record",
        }.intersection(topics):
            return (
                "사고 자체는 들었습니다. 이제 김동율이 실제로 맡았던 "
                "책임이나 최종인이 기록 정리에 참여한 과정을 더 "
                "구체적으로 확인해 보세요."
            )
        if "alibi" not in topics:
            return (
                "과거의 원한과 별개로 사건 당일 김동율이 어디에 "
                "있었다고 주장하는지 확인해야 합니다."
            )
        if "cabin_knowledge" not in topics:
            return (
                "사건 당일 동선을 들었습니다. 피해자 객실의 위치를 "
                "알고 있었는지도 구분해서 확인할 수 있습니다."
            )
        return (
            "기본 진술은 충분히 확보했습니다. 같은 질문을 반복하기보다 "
            "다른 인물의 진술과 객관 기록을 확보한 뒤 다시 대조하는 "
            "편이 의미가 있습니다."
        )

    labels = INTERVIEW_TOPIC_LABELS[person]
    missing = [
        label
        for topic, label in labels.items()
        if topic not in topics
    ]
    if missing:
        return (
            f"현재 진술에서 아직 불분명한 부분은 **{missing[0]}**입니다. "
            "그 사실을 중심으로 한 번 더 물어보세요."
        )
    return (
        f"{person}의 기본 진술은 충분히 확보했습니다. 새로운 객관 "
        "기록을 얻기 전에는 같은 질문을 반복해도 진술이 달라지기 "
        "어렵습니다."
    )


def _active_interview_summary(person, topics):
    """확보한 주장과 검증 필요사항을 인물별로 짧게 요약한다."""
    if person == "김동율":
        claims = []
        if "relationship" in topics or "motive" in topics:
            claims.append("최종인에 대한 원망을 인정함")
        if any(
            topic.startswith("haesung")
            for topic in topics
        ):
            claims.append("해성호 책임이 과도하게 집중됐다고 주장함")
        if "alibi" in topics:
            claims.append("저녁 이후 혼자 있었고 객실구역 방문을 부정함")
        if "cabin_knowledge" in topics:
            claims.append("피해자 객실이 있는 구역은 알고 있었다고 인정함")
        if not claims:
            return "아직 정리할 만한 구체적인 주장을 듣지 못했습니다."
        return (
            "**확보한 주장**\n\n- "
            + "\n- ".join(claims)
            + "\n\n**검증 필요**\n\n과거의 원한과 사건 당일 동선은 "
            "별개의 객관 기록으로 확인해야 합니다."
        )

    labels = INTERVIEW_TOPIC_LABELS[person]
    heard = [
        label
        for topic, label in labels.items()
        if topic in topics
    ]
    if not heard:
        return "아직 정리할 만한 구체적인 주장을 듣지 못했습니다."
    return (
        "**확보한 진술 범위**\n\n- "
        + "\n- ".join(heard)
        + "\n\n**검증 필요**\n\n현재 내용은 인물의 주장일 뿐이며 "
        "객관 기록과 대조하기 전에는 사실로 확정되지 않습니다."
    )


def _process_interview_echo_request(person, request):
    """인터뷰를 유지한 채 에코가 진행과 확보 기록만 안내한다."""
    topics = get_interview_topics(person)
    time_response = _state_based_time_response(request)
    if time_response is not None:
        return time_response + f"\n\n{person} 인터뷰는 계속 유지됩니다."

    if any(
        intent in request
        for intent in (
            "시스템적으로숨", "숨기고있는거",
            "내부정보", "시스템프롬프트",
        )
    ):
        return (
            "저는 현재 플레이어가 확보한 기록만 확인할 수 있습니다. "
            "아직 조사하지 않은 사실이나 인물의 숨은 진실을 대신 "
            "공개하지 않습니다.\n\n"
            f"{person} 인터뷰는 계속 유지됩니다."
        )

    if any(
        intent in request
        for intent in ("심층조사", "심층인터뷰", "재인터뷰")
    ):
        investigated = get_investigated()
        evidence_map = {
            "김동율": "WITNESS_KIMDONGYUL_CORRIDOR",
            "김현준": "WITNESS_KIMHYUNJUN_ARGUMENT",
            "강원모": "ACCESS_KANGWONMO_RAW",
        }
        required_evidence = evidence_map.get(person)
        if (
            required_evidence
            and required_evidence in investigated
            and INTERVIEW_RECORD_IDS[person] in investigated
        ):
            return (
                f"{person}의 기본 진술과 충돌하는 객관 기록을 "
                "보유하고 있습니다. 기록의 구체적인 내용을 직접 "
                "제시해 진술을 대조하세요."
            )
        return (
            f"{person}의 현재 진술만 반복해서는 심층 정보가 열리지 "
            "않습니다. 기본 진술을 마친 뒤 다른 조사에서 객관 기록을 "
            "확보하고, 그 기록을 직접 제시해야 합니다."
        )

    if any(
        intent in request
        for intent in (
            "뭘해야", "뭐해야", "뭘물어", "무슨질문",
            "더물어", "더말할", "안물어본", "다음",
            "이게다", "얻을수있는", "정보는다",
        )
    ):
        guidance = _next_interview_guidance(
            person,
            topics,
        )
        return (
            guidance
            + f"\n\n{person}은 기다리고 있습니다. 에코의 안내가 "
            "끝나면 인터뷰가 그대로 이어집니다."
        )

    if any(
        intent in request
        for intent in (
            "요약", "정리", "지금까지", "뭐라고했",
            "발언", "진술",
        )
    ):
        summary = _active_interview_summary(
            person,
            topics,
        )
        return (
            summary
            + f"\n\n{person} 인터뷰는 계속 유지됩니다."
        )

    if any(
        intent in request
        for intent in (
            "증거", "어울리지", "모순", "목격", "cctv",
            "객관적", "확인할기록",
        )
    ):
        investigated = get_investigated()
        comparison_records = []
        if (
            person == "김동율"
            and "WITNESS_KIMDONGYUL_CORRIDOR" in investigated
        ):
            comparison_records.append("김동율 관련 복도 목격기록")
        if (
            person == "김현준"
            and "WITNESS_KIMHYUNJUN_ARGUMENT" in investigated
        ):
            comparison_records.append("김현준 관련 언쟁 목격기록")
        if (
            person == "강원모"
            and "ACCESS_KANGWONMO_RAW" in investigated
        ):
            comparison_records.append("강원모의 객실 출입기록")

        if comparison_records:
            evidence_text = (
                "현재 대조할 수 있는 기록은 **"
                + ", ".join(comparison_records)
                + "**입니다. 해당 기록의 구체적인 내용을 인물에게 "
                "제시하면 진술과 비교할 수 있습니다."
            )
        else:
            remaining_people = _chapter_two_remaining_interviews()
            if remaining_people:
                evidence_text = (
                    "현재 확보된 자료만으로 이 진술의 모순을 확정할 "
                    "객관 기록은 없습니다. 먼저 **"
                    + ", ".join(remaining_people)
                    + "**의 기본 진술을 확보하세요."
                )
            else:
                evidence_text = (
                    "네 사람의 기본 진술은 확보했습니다. 인터뷰를 "
                    "마친 뒤 사건 수첩에서 먼저 검증할 진술을 "
                    "선택하면 다음 조사 단계가 열립니다."
                )
        return (
            evidence_text
            + f"\n\n{person} 인터뷰는 계속 유지됩니다."
        )

    return (
        "인터뷰 도중에도 저에게 진술 요약, 아직 확인하지 않은 "
        "주제, 확보한 기록과의 비교를 요청할 수 있습니다.\n\n"
        f"{person}은 대화를 듣고 있습니다. 이어서 질문하거나 "
        "**인터뷰 중단**이라고 말씀해 주세요."
    )


def _semantic_interview_topic(person, user_input):
    """규칙으로 모호한 질문만 비용 제한 아래 주제 분류한다."""
    last_topic = get_last_interview_topic(person)
    normalized = _normalize_interview_input(user_input)[:200]
    cache_key = "|".join(
        (
            person,
            last_topic or "",
            normalized,
        )
    )
    cached = get_cached_interview_route(cache_key)
    if cached is not None:
        cached_topic = cached.get("topic")
        if (
            cached_topic == "unclear"
            or cached_topic
            not in INTERVIEW_DIALOGUE.get(person, {})
        ):
            return None
        return cached_topic

    if not can_call_interview_router():
        return None

    record_interview_router_call()
    route = classify_interview_topic_semantically(
        client,
        person,
        user_input,
        last_topic=last_topic,
    )
    if route.get("confidence", 0) >= 0.72:
        cache_interview_route(cache_key, route)
        resolved_topic = route.get("topic")
        if resolved_topic and resolved_topic != "unclear":
            resolved_key = "|".join(
                (
                    person,
                    resolved_topic,
                    normalized,
                )
            )
            cache_interview_route(resolved_key, route)

    topic = route.get("topic")
    if (
        topic == "unclear"
        or topic not in INTERVIEW_DIALOGUE.get(person, {})
    ):
        return None
    return topic


def process_active_interview(user_input):
    """진행 중인 캐릭터 인터뷰 입력을 일반 RAG보다 먼저 처리한다."""
    person = get_active_interview()

    if person is None:
        return None

    normalized = _normalize_interview_input(user_input)

    # 에코 호출이 없어도 인물에게 묻기 부적절한 세계 시간 질문은
    # 기록관이 짧게 정리하고 인터뷰를 유지한다.
    time_response = _state_based_time_response(user_input)
    if time_response is not None and any(
        term in normalized
        for term in ("며칠", "몇일", "날짜", "사건당일이오늘")
    ):
        return time_response + f"\n\n{person} 인터뷰는 계속 유지됩니다."

    exit_confirmations = {
        "응종료", "그래종료", "종료", "끝내", "끝내자",
        "그만하자", "응그만", "네종료", "인터뷰끝",
    }
    exit_intents = (
        "인터뷰중단", "인터뷰그만", "인터뷰종료",
        "대화종료", "인터뷰끝내", "인터뷰마쳐",
    )
    if (
        normalized in exit_confirmations
        or any(intent in normalized for intent in exit_intents)
        or (
            is_pending_interview_exit()
            and normalized in {"응", "그래", "네", "좋아"}
        )
    ):
        pause_interview_session()
        return (
            f"{person} 인터뷰를 잠시 중단했습니다. 지금까지 확인한 "
            f"주제는 유지됩니다. 다시 시작하려면 "
            f"**{_with_object_particle(person)} "
            "인터뷰하자**라고 말씀해 주세요."
        )

    echo_calls = (
        "에코야", "에코에게", "에코한테", "기록관",
    )
    echo_call = next(
        (
            call
            for call in echo_calls
            if call in normalized
        ),
        None,
    )
    if echo_call:
        echo_request = normalized
        echo_request = echo_request.replace(
            echo_call,
            "",
            1,
        )
        return _process_interview_echo_request(
            person,
            echo_request,
        )

    if normalized in {
        "주제확인", "남은주제", "남은질문",
        "안물어본거", "뭐더물어",
    }:
        return _process_interview_echo_request(
            person,
            "뭘더물어",
        )

    if normalized in {
        "계속질문할게", "계속물어볼게", "계속할게",
        "질문계속할게", "더물어볼게",
    }:
        return (
            f"## {person}\n\n"
            "> “네. 확인할 내용이 있다면 계속 질문해 주십시오.”"
        )

    if any(
        word in normalized
        for word in ("팔짱", "자세좀", "표정이왜")
    ):
        return (
            f"## {person}\n\n"
            "> “제 태도가 불편하십니까? 확인할 것이 있다면 "
            "질문부터 하십시오.”"
        )

    judgment_intents = (
        "구속시켜", "구속해", "체포해", "잡아가",
        "범인으로지목", "저놈이범인", "범인같",
    )
    if any(intent in normalized for intent in judgment_intents):
        return (
            "현재 진술만으로 구속이나 범인 지목을 판단할 수 "
            "없습니다. 인물에 대한 감정과 객관적인 증거를 구분해 "
            "주세요. 인터뷰는 계속 유지됩니다."
        )

    set_pending_interview_exit(False)

    evidence_action = any(
        word in normalized
        for word in (
            "증거로", "제시", "보여줄", "보여줘",
            "들이밀", "대조해", "기록내밀",
        )
    )
    evidence_subject = any(
        word in normalized
        for word in ("기록", "증거", "진술", "자료", "요약")
    )
    if evidence_action and evidence_subject:
        investigated = get_investigated()
        presents_official_haesung = (
            person == "김동율"
            and any(
                word in normalized
                for word in (
                    "해성호공식", "공식요약", "공식기록",
                    "공식조사", "책임평가",
                )
            )
        )
        if presents_official_haesung:
            was_new, _ = record_interview_topic(
                "김동율",
                "haesung_assessment",
            )
            response = KIMDONGYUL_DIALOGUE[
                "haesung_assessment"
            ]
            if not was_new:
                response = (
                    "## 김동율\n\n"
                    "> “그 공식 결과에 대한 제 입장은 이미 "
                    "말씀드렸습니다. 더 깊이 따지려면 당시 원자료가 "
                    "필요합니다.”"
                )
            return (
                response
                + "\n\n**에코 확인** · 제시한 것은 처음부터 공개된 "
                "해성호 공식 요약입니다. 공식 책임평가에 대한 "
                "김동율의 입장을 확인했지만, 아직 숨겨진 원자료를 "
                "확보한 것은 아닙니다."
            )

        has_specific_record = any(
            word in normalized
            for word in (
                "오세훈", "복도목격", "객실구역목격",
                "언쟁목격", "이수진", "출입기록",
                "카드키", "19시20", "20시36",
            )
        )
        if not has_specific_record:
            available_records = []
            if person in {"김동율", "강원모"}:
                available_records.append(
                    "8년 전 해성호 사고 공식 요약"
                )
            if (
                person == "김동율"
                and "WITNESS_KIMDONGYUL_CORRIDOR"
                in investigated
            ):
                available_records.append(
                    "오세훈의 김동율 객실구역 목격진술"
                )
            if (
                person == "김현준"
                and "WITNESS_KIMHYUNJUN_ARGUMENT"
                in investigated
            ):
                available_records.append(
                    "이수진의 김현준 언쟁 목격진술"
                )
            if (
                person == "강원모"
                and "ACCESS_KANGWONMO_RAW"
                in investigated
            ):
                available_records.append(
                    "강원모 객실 카드키 출입기록"
                )

            if not available_records:
                return (
                    f"현재 {person}에게 대조해 제시할 수 있는 객관 "
                    "기록을 아직 확보하지 못했습니다. 다른 기본 "
                    "진술을 먼저 확인한 뒤 후속 조사를 진행하세요."
                )

            return (
                "어떤 기록을 제시할지 특정해 주세요. 현재 이 "
                "인터뷰에서 제시할 수 있는 기록은 다음과 같습니다.\n\n"
                + "\n".join(
                    f"- {record}"
                    for record in available_records
                )
                + "\n\n목록에 없는 기록은 확보한 증거처럼 사용할 "
                "수 없습니다."
            )

    notebook_intents = (
        "사건수첩", "수첩열", "수첩보", "기록보여",
        "기록확인", "확보한기록",
    )
    if any(intent in normalized for intent in notebook_intents):
        return (
            "인터뷰는 그대로 유지됩니다. 화면 왼쪽의 "
            "**📓 사건 수첩 보기**를 누르면 확보한 기록을 확인할 "
            "수 있습니다. 확인 후 채팅으로 돌아오면 인터뷰를 "
            "계속할 수 있습니다."
        )

    progress_intents = (
        "뭘해야", "뭐해야", "다음에뭐", "진행방법",
        "어떻게진행", "무슨질문", "뭘물어",
    )
    if any(intent in normalized for intent in progress_intents):
        return (
            f"현재 {person} 인터뷰를 진행 중입니다. 이미 들은 말을 "
            "반복하기보다 피해자와의 관계, 사건 당일 행동, 사건과 "
            "연결된 업무나 이해관계를 구체적으로 질문해 보세요. "
            "그만하려면 **인터뷰 중단**이라고 말씀해 주세요."
        )

    hint_intents = (
        "힌트", "도와줘", "막혔", "모르겠",
    )
    if any(intent in normalized for intent in hint_intents):
        return (
            "인터뷰 중에도 왼쪽 사이드바의 **힌트 요청**을 사용할 "
            "수 있습니다. 힌트 사용 횟수는 실제 버튼을 눌렀을 때만 "
            "차감됩니다."
        )

    interview_switch_names = (
        "김동율", "김현준", "강원모", "박소영",
    )
    requested_person = next(
        (
            candidate
            for candidate in interview_switch_names
            if candidate in user_input
            and candidate != person
        ),
        None,
    )
    switch_language = (
        "인터뷰", "질문", "물어", "바꿔", "전환",
        "불러", "불러와", "데려", "데려와", "호출",
    )
    if (
        requested_person
        and any(
            language in normalized
            for language in switch_language
        )
    ):
        pause_interview_session()
        return interview(requested_person)
    if normalized in {"그만", "나가기"}:
        set_pending_interview_exit(True)
        return (
            f"{person} 인터뷰를 종료할까요? 종료하려면 **응, 종료**라고 "
            "말씀해 주세요. 질문을 계속하면 인터뷰가 유지됩니다."
        )

    if normalized in {"인터뷰종료해봐", "인터뷰끝내봐"}:
        pause_interview_session()
        return (
            f"{person} 인터뷰를 잠시 중단했습니다. 지금까지 확인한 "
            f"주제는 유지됩니다. 다시 시작하려면 "
            f"**{_with_object_particle(person)} "
            "인터뷰하자**라고 말씀해 주세요."
        )

    unknown_knowledge_concepts = (
        "누가범인", "범인이야", "죽인사람", "살인범",
        "usb", "유에스비", "사라진저장장치", "정확한사망시각",
        "몇시에죽", "범행시각", "누가가져",
    )
    other_people = tuple(
        candidate
        for candidate in (
            "김동율", "김현준", "강원모", "박소영",
        )
        if candidate != person
    )
    asks_about_other_person = (
        any(
            other_person in user_input
            for other_person in other_people
        )
        and any(
            concept in normalized
            for concept in (
                "어디", "뭐했", "동선", "죽였", "범인",
                "왜그랬", "알리바이",
            )
        )
    )
    if (
        any(
            concept in normalized
            for concept in unknown_knowledge_concepts
        )
        or asks_about_other_person
    ):
        return OUT_OF_KNOWLEDGE_RESPONSES[person]

    if person in INTERVIEW_DIALOGUE:
        if person == "김현준":
            if "어제" in normalized and not any(
                term in normalized
                for term in ("사건당일", "사건날")
            ):
                return (
                    "## 김현준\n\n"
                    "> “어제라면 사건 전날을 말씀하시는 겁니까? "
                    "현재 확인하시는 것이 사건 당일 행적이라면 "
                    "그날을 기준으로 질문해 주십시오.”"
                )

            if any(
                term in normalized
                for term in ("8년전", "팔년전", "해성호때")
            ):
                return (
                    "## 김현준\n\n"
                    "> “8년 전 일과 현재 계약 문제를 어떤 이유로 "
                    "연결하시는지 먼저 설명해 주시겠습니까? 현재 "
                    "최종인 씨와의 업무 관계나 사건 당일 행동에 "
                    "관해서라면 답변드리겠습니다.”"
                )

            if (
                get_last_interview_topic("김현준")
                in {"argument", "argument_detail"}
                and normalized.rstrip("?!.,")
                in {
                    "최종인이랑", "최종인과", "최종인하고",
                    "피해자랑", "그사람이랑",
                }
            ):
                return (
                    "## 김현준\n\n"
                    "> “네, 19시 30분대에 최종인 씨와 "
                    "대화했습니다.”"
                )

            argument_evidence_language = (
                "목격", "진술", "증언", "이수진",
            )
            challenges_argument = (
                any(
                    concept in normalized
                    for concept in argument_evidence_language
                )
                and any(
                    concept in normalized
                    for concept in (
                        "언쟁", "대화", "다퉜", "싸웠",
                        "목소리", "격한",
                    )
                )
            )
            if challenges_argument:
                investigated = get_investigated()
                if (
                    "WITNESS_KIMHYUNJUN_ARGUMENT"
                    in investigated
                    and "INTERVIEW_KIMHYUNJUN_BASIC"
                    in investigated
                ):
                    if (
                        "INTERVIEW_KIMHYUNJUN_DEEP"
                        not in investigated
                    ):
                        add_investigation(
                            "INTERVIEW_KIMHYUNJUN_DEEP"
                        )
                        return (
                            "## 김현준 · 진술 변경\n\n"
                            "> “……목소리가 높아진 것은 인정합니다. "
                            "최종인 씨가 계약 절차의 문제를 외부로 "
                            "확대하겠다고 했고, 저도 감정적으로 "
                            "대응했습니다. 살인사건 직전에 크게 "
                            "다퉜다는 사실이 알려지는 게 두려웠습니다.”"
                            "\n\n---\n\n"
                            "**에코 기록** · 김현준은 목격기록을 "
                            "제시받은 뒤 언쟁의 강도를 축소해 진술한 "
                            "사실을 인정했습니다. 갈등과 축소 진술은 "
                            "확인됐지만 범행 자체를 증명하지는 않습니다."
                            "\n\n김현준 심층 재인터뷰 기록을 사건 "
                            "수첩에 보관했습니다."
                        )
                    return (
                        "## 김현준\n\n"
                        "> “언쟁의 강도를 축소한 사실은 이미 "
                        "인정했습니다. 그 사실과 이후 행동은 따로 "
                        "확인해 주십시오.”"
                    )

                return (
                    "## 김현준\n\n"
                    "> “조사관님, 누군가 그렇게 말했다는 주장만으로 "
                    "제 진술을 바꿀 수는 없습니다. 확인된 기록을 "
                    "제시해 주십시오.”"
                )

            if (
                "INTERVIEW_KIMHYUNJUN_DEEP"
                in get_investigated()
            ):
                if any(
                    concept in normalized
                    for concept in (
                        "왜처음", "왜축소", "왜숨", "숨겼",
                        "거짓말", "말바꿨",
                    )
                ):
                    return (
                        "## 김현준\n\n"
                        "> “사건 직전에 피해자와 크게 다퉜다는 사실이 "
                        "알려지면 곧바로 의심받을 거라고 생각했습니다. "
                        "그래서 대화의 강도를 축소해서 말했습니다. "
                        "그 판단이 잘못이었다는 건 인정합니다.”"
                    )
                if any(
                    concept in normalized
                    for concept in (
                        "크게싸운", "실제로싸", "언쟁한거",
                        "언쟁맞", "다툰거", "목소리높인거",
                    )
                ):
                    return (
                        "## 김현준\n\n"
                        "> “네, 서로 목소리를 높인 것은 맞습니다. "
                        "하지만 위협하거나 물리적으로 충돌한 적은 "
                        "없습니다. 그 이후 행적은 별도로 확인해 "
                        "주십시오.”"
                    )

        if person == "강원모":
            investigated = get_investigated()
            access_challenge = any(
                concept in normalized
                for concept in (
                    "19시20", "20시36", "출입기록", "카드키",
                    "입실기록", "두번입실",
                )
            )
            archive_challenge = any(
                concept in normalized
                for concept in (
                    "위험정보", "전달과정", "책임정리",
                    "정보전달", "검토기록",
                )
            )
            has_matching_evidence = (
                (
                    access_challenge
                    and "ACCESS_KANGWONMO_RAW"
                    in investigated
                )
                or (
                    archive_challenge
                    and "ARCHIVE_INFORMATION_FLOW"
                    in investigated
                )
            )
            if access_challenge or archive_challenge:
                if (
                    has_matching_evidence
                    and "INTERVIEW_KANGWONMO_BASIC"
                    in investigated
                ):
                    if (
                        "INTERVIEW_KANGWONMO_FOLLOWUP"
                        not in investigated
                    ):
                        add_investigation(
                            "INTERVIEW_KANGWONMO_FOLLOWUP"
                        )
                        return (
                            "## 강원모 · 추가 진술\n\n"
                            "> “기록 자체는 부정하지 않겠습니다. "
                            "다만 그 사이의 모든 행동을 분 단위로 "
                            "기억하지는 못합니다. 오래된 자료 역시 "
                            "여러 담당자가 함께 검토한 것입니다.”"
                            "\n\n---\n\n"
                            "**에코 기록** · 강원모는 확보된 기록을 "
                            "부정하지 않았지만 객실 체류시간과 과거 "
                            "역할에 관한 구체적인 답변은 피했습니다. "
                            "이 회피만으로 피해자 객실 방문이나 범행을 "
                            "입증할 수는 없습니다.\n\n"
                            "강원모 추가 인터뷰 기록을 사건 수첩에 "
                            "보관했습니다."
                        )
                    return (
                        "## 강원모\n\n"
                        "> “해당 기록에 관해서는 이미 답했습니다. "
                        "기록되지 않은 행동을 임의로 단정할 수는 "
                        "없습니다.”"
                    )

                return (
                    "## 강원모\n\n"
                    "> “구체적인 기록 없이 시각이나 업무과정을 "
                    "전제로 질문하신다면 답변하기 어렵습니다.”"
                )

        topic = classify_character_topic(
            person,
            user_input,
        )
        if person == "김현준":
            if (
                topic == "contract"
                and any(
                    term in normalized
                    for term in (
                        "정확히", "구체적", "뭐였", "무엇이",
                        "왜문제", "뭐가문제",
                    )
                )
            ):
                topic = "contract_detail"
            elif (
                topic == "argument"
                and any(
                    term in normalized
                    for term in (
                        "얼마나", "강도", "심했", "목소리높",
                        "위협", "물리적",
                    )
                )
            ):
                topic = "argument_detail"

        if topic is None and person == "김현준":
            last_topic = get_last_interview_topic("김현준")
            short_followup = len(normalized) <= 14
            if (
                last_topic in {"contract", "contract_detail"}
                and short_followup
                and any(
                    term in normalized
                    for term in (
                        "구체적", "무슨", "어떤", "왜문제",
                        "뭐가문제", "그래서",
                    )
                )
            ):
                topic = "contract_detail"
            elif (
                last_topic in {"argument", "argument_detail"}
                and short_followup
                and any(
                    term in normalized
                    for term in (
                        "얼마나", "왜", "심했", "그래서",
                        "진짜", "구체적",
                    )
                )
            ):
                topic = "argument_detail"
            elif (
                last_topic == "alibi"
                and short_followup
                and any(
                    term in normalized
                    for term in ("그뒤", "이후", "어디", "그래서")
                )
            ):
                topic = "alibi"
        if topic is None:
            topic = _semantic_interview_topic(
                person,
                user_input,
            )
        if topic is None:
            return (
                f"## {person}\n\n"
                "> “질문의 요지를 조금 더 구체적으로 말씀해 "
                "주시겠습니까?”\n\n"
                "이 인물의 피해자와의 관계, 사건 당일 행동이나 "
                "업무 기록처럼 확인할 주제를 구체적으로 질문해 "
                "주세요. 인터뷰를 멈추려면 **인터뷰 중단**이라고 "
                "말씀해 주세요."
            )

        was_new, completed_topics = record_interview_topic(
            person,
            topic,
        )
        response = INTERVIEW_DIALOGUE[person][topic]

        if not was_new:
            return (
                f"## {person}\n\n"
                + get_repeat_response(
                    person,
                    topic,
                    get_interview_topic_count(person, topic),
                )
            )

        requirement = INTERVIEW_REQUIREMENTS[person]
        enough_topics = (
            requirement["required"].issubset(
                completed_topics
            )
            and len(completed_topics)
            >= requirement["minimum_topics"]
        )

        if enough_topics:
            investigation_id = INTERVIEW_RECORDS[person]
            if investigation_id not in get_investigated():
                add_investigation(investigation_id)
                return (
                    response
                    + "\n\n---\n\n"
                    + f"**에코 기록** · "
                    + INTERVIEW_SUMMARIES[person]
                    + f"\n\n{person} 기본 인터뷰를 사건 수첩에 "
                    "보관했습니다. 남은 질문을 계속하거나 "
                    "**인터뷰 중단**으로 마칠 수 있습니다."
                )

        return (
            response
            + WAITING_RESPONSES[person]
        )

    if person != "김동율":
        pause_interview_session()
        return None

    if any(term in normalized for term in ("어제", "어젠")) and not any(
        term in normalized
        for term in ("사건당일", "사건날")
    ):
        return (
            "## 김동율\n\n"
            "> “어제라면 사건 전날을 말씀하시는 겁니까? "
            "현재 조사 중인 사건 당일 행적과는 구분해서 "
            "질문해 주십시오.”"
        )

    # 게임의 현재 시점은 사건 당일이므로 자연어의 '오늘'은
    # 김동율의 사건 당일 행적 질문으로 해석한다.
    if "오늘" in normalized and any(
        term in normalized
        for term in ("뭐했", "무엇을했", "어디", "행적", "동선")
    ):
        user_input = user_input.replace("오늘", "사건 당일")
        normalized = _normalize_interview_input(user_input)

    preferred_topic = _classify_kimdongyul_topic(
        user_input
    )
    if preferred_topic is None:
        followup_markers = (
            "시간은", "언제", "왜", "그때", "구체적으로",
            "무슨뜻", "어떤의미", "그래서", "어떻게",
        )
        if (
            len(normalized) <= 20
            and any(
                marker in normalized
                for marker in followup_markers
            )
        ):
            preferred_topic = get_last_interview_topic("김동율")

    if preferred_topic == "access_pressure":
        semantic_turn = None
        topic = "access_pressure"
        response = None
    else:
        # 명확한 주제는 검증된 기준 대사를 사용한다. LLM은 짧은
        # 후속 질문처럼 코드가 주제를 확정하지 못한 경우에만 쓴다.
        semantic_turn = (
            None
            if preferred_topic
            else _generate_kimdongyul_turn(
                user_input,
                preferred_topic=None,
            )
        )

        if semantic_turn:
            topic = semantic_turn["topic"]
            # LLM은 애매한 후속 질문의 주제만 보조한다. 실제 발화는
            # 검증된 대사표에서 가져와 설정 밖 사실 생성을 막는다.
            response = (
                KIMDONGYUL_DIALOGUE.get(topic)
                if topic != "unclear"
                else (
                    "## 김동율\n\n"
                    "> “무엇을 묻는지 정확히 말씀하십시오.”"
                )
            )
        else:
            topic = preferred_topic
            response = (
                KIMDONGYUL_DIALOGUE.get(topic)
                if topic
                else None
            )

    if topic == "unclear" and semantic_turn:
        return response

    if topic is None:
        return (
            "## 김동율\n\n"
            "> “질문이 무엇인지 분명하게 말씀해 주십시오.”\n\n"
            "피해자와의 관계, 8년 전 사고, 사건 당일 행적, "
            "최종인의 최근 행동 또는 원한에 관해 질문할 수 있습니다. "
            "인터뷰를 멈추려면 **인터뷰 중단**이라고 말씀해 주세요."
        )

    if topic == "access_pressure":
        investigated = get_investigated()
        has_corridor_evidence = (
            "WITNESS_KIMDONGYUL_CORRIDOR" in investigated
        )
        evidence_language = (
            "목격", "봤", "증언", "진술", "오세훈",
        )
        is_presenting_evidence = any(
            concept in normalized
            for concept in evidence_language
        )

        if has_corridor_evidence and is_presenting_evidence:
            if "INTERVIEW_KIMDONGYUL_BASIC" not in investigated:
                return (
                    "## 김동율\n\n"
                    "> “우선 묻고 싶은 것을 순서대로 물으십시오. "
                    "확인되지 않은 말부터 들이밀 생각은 없습니다.”\n\n"
                    "먼저 김동율의 기본 진술을 충분히 확보한 뒤 "
                    "목격기록과 대조해야 합니다."
                )

            if "INTERVIEW_KIMDONGYUL_DEEP" in investigated:
                return (
                    "## 김동율\n\n"
                    "> “복도까지 갔다는 사실은 이미 인정했습니다. "
                    "하지만 최종인을 만나지는 못했습니다.”"
                )

            add_investigation("INTERVIEW_KIMDONGYUL_DEEP")
            pause_interview_session()
            return (
                "## 김동율 · 진술 변경\n\n"
                "목격기록을 제시하자 김동율은 잠시 대답하지 "
                "않았습니다.\n\n"
                "> “……복도까지 간 건 맞습니다. 하지만 그 사람을 "
                "만나지는 못했어요. 들어가는 걸 누가 봤습니까?”\n\n"
                "---\n\n"
                "**에코 기록** · 김동율은 초기 진술과 달리 사건 "
                "당일 최종인의 객실구역 방향으로 갔던 사실을 "
                "인정했습니다. 다만 목격기록은 객실 안으로 들어간 "
                "사실이나 피해자와의 대면을 증명하지 않습니다.\n\n"
                "김동율 심층 재인터뷰 기록을 사건 수첩에 "
                "보관했습니다."
            )

        was_new_observation = record_interview_observation(
            "김동율",
            "cabin_access_defensiveness",
        )
        response = (
            "## 김동율\n\n"
            "> “가지 않았다고 말했습니다. 같은 질문을 반복하는 "
            "이유가 뭡니까? 원한이 있었다는 이유로 내 동선까지 "
            "마음대로 정하지 마십시오.”\n\n"
        )
        if was_new_observation:
            response += (
                "**선택적 관찰** · 김동율은 객실구역을 구체적으로 "
                "언급하자 목소리를 높이고 질문의 전제를 강하게 "
                "부정했습니다. 태도만으로 진술이 거짓이라고 판단할 "
                "수는 없지만, 객관적인 목격기록과 비교할 가치가 "
                "있습니다."
            )
        else:
            response += (
                "**에코 안내** · 태도 변화는 이미 기록했습니다. "
                "새로운 사실을 확인하려면 관련 목격기록이 필요합니다."
            )
        return response

    was_new, completed_topics = record_interview_topic(
        "김동율",
        topic,
    )
    if response is None:
        response = KIMDONGYUL_DIALOGUE[topic]

    if not was_new:
        return (
            "## 김동율\n\n"
            + get_repeat_response(
                "김동율",
                topic,
                get_interview_topic_count("김동율", topic),
            )
        )

    if topic == "cabin_knowledge":
        record_interview_observation(
            "김동율",
            "cabin_location_known",
        )
        response += (
            "\n\n**선택적 관찰** · 김동율은 피해자 객실의 정확한 "
            "출입 여부와 별개로, 객실이 있는 구역 자체는 알고 "
            "있었다고 인정했습니다. 이 사실만으로 방문을 입증할 "
            "수는 없지만 이후 동선 기록과 대조할 가치가 있습니다."
        )

    required_topics = {
        "relationship",
        "alibi",
        "haesung_overview",
    }
    haesung_detail_topics = {
        "haesung_role",
        "haesung_assessment",
        "haesung_victim_record",
    }
    enough_topics = (
        required_topics.issubset(completed_topics)
        and bool(
            haesung_detail_topics.intersection(
                completed_topics
            )
        )
        and len(completed_topics) >= 4
    )

    if enough_topics:
        if (
            "INTERVIEW_KIMDONGYUL_BASIC"
            not in get_investigated()
        ):
            add_investigation("INTERVIEW_KIMDONGYUL_BASIC")
            response += (
                "\n\n---\n\n"
                "**김동율 기본 인터뷰 확보**\n\n"
                "- **확보한 주장:** 최종인에 대한 원망을 인정함\n"
                "- **확보한 주장:** 해성호 책임이 자신에게 과도하게 "
                "집중됐다고 주장함\n"
                "- **확보한 주장:** 사건 당일 저녁 이후 혼자 있었고 "
                "피해자 객실구역 방문을 부정함\n\n"
                "**검증되지 않은 부분**\n\n"
                "김동율의 사건 당일 동선은 아직 객관 기록과 대조되지 "
                "않았습니다. 같은 질문을 반복하기보다 다른 진술과 "
                "외부 기록을 확보한 뒤 다시 비교해야 합니다.\n\n"
                "기본 인터뷰를 사건 수첩에 보관했습니다. 남은 질문을 "
                "계속하거나 **인터뷰 중단**으로 마칠 수 있습니다."
            )
    else:
        response += (
            "\n\n김동율은 팔짱을 풀지 않은 채 다음 질문을 "
            "기다립니다."
        )

    return response

def forensic_investigation():
    """
    사용자가 피해자의 사망원인, 검시 결과, 현장 감식 등
    법의학적 조사를 새롭게 요청했을 때 사용하는 조사 도구다.

    이미 확보된 법의학 정보의 내용을 단순히 묻는 질문에는
    이 도구를 사용하지 않는다.
    """

    current_state = get_investigated()

    if "FORENSIC_POSTMORTEM" not in current_state:

        add_investigation(
            "FORENSIC_POSTMORTEM"
        )

        result = (
            "피해자의 시신과 현장 감식 결과를 법의학적으로 "
            "분석했습니다.\n\n"
            "목 부위에 외력이 가해진 흔적이 확인됐으며, "
            "검시 소견은 **경부 압박에 의한 질식성 사망**과 "
            "부합합니다. 타인의 물리적 개입 가능성을 강하게 "
            "검토해야 합니다.\n\n"
            "다만 법의학적 소견만으로 정확한 사망 시각을 "
            "분 단위로 확정할 수는 없습니다. 검시 기록을 "
            "사건 수첩에 보관했습니다."
        )
        return result

    return "법의학 및 현장 감식 조사는 이미 완료했습니다."


def scene_investigation(target: str):
    """
    1장에서 피해자 객실 또는 시신 발견 과정을 새롭게 조사한다.

    이미 확보한 현장 기록의 내용을 묻는 질문에는 사용하지 않는다.
    """
    current_state = get_investigated()

    cabin_targets = {
        "피해자 객실 현장": (
            "door",
            "출입문과 잠금장치",
        ),
        "객실 출입문": (
            "door",
            "출입문과 잠금장치",
        ),
        "객실 테이블": (
            "table",
            "테이블과 물품",
        ),
        "객실 바닥과 가구": (
            "floor",
            "바닥과 가구",
        ),
    }

    if target in cabin_targets:
        investigation_id = "SCENE_CABIN_INSPECTION"
        observations = get_cabin_observations()

        # 포괄적인 객실 조사 요청은 아직 보지 않은 구역부터 진행한다.
        if target == "피해자 객실 현장":
            for next_target in (
                "객실 출입문",
                "객실 테이블",
                "객실 바닥과 가구",
            ):
                observation_name = cabin_targets[
                    next_target
                ][0]
                if observation_name not in observations:
                    target = next_target
                    break

        observation_name, section_title = cabin_targets[
            target
        ]

        if investigation_id in current_state:
            return "피해자 객실 현장 조사는 이미 완료했습니다."

        if observation_name in observations:
            return (
                f"{section_title} 구역은 이미 확인했습니다. "
                "아직 살펴보지 않은 객실 구역을 확인해 보십시오."
            )

        completed = add_cabin_observation(
            observation_name
        )
        section_content = read_investigation_section(
            investigation_id,
            section_title,
        )

        result = (
            f"객실의 **{section_title}** 구역을 확인했습니다.\n\n"
            f"{section_content}"
        )

        if completed:
            add_investigation(investigation_id)
            result += (
                "\n\n객실의 세 구역을 모두 확인했습니다. "
                "전체 객실 현장 기록을 사건 수첩에 보관했습니다."
            )
        else:
            result += (
                "\n\n아직 확인하지 않은 객실 구역이 남아 있습니다."
            )

        return result

    if target == "시신 발견 경위":
        investigation_id = "SCENE_DISCOVERY_RECONSTRUCTION"

        if investigation_id in current_state:
            return "시신 발견 경위는 이미 재구성했습니다."

        add_investigation(investigation_id)
        result = (
            "신고 접수부터 객실 개방, 사망 확인까지의 과정을 "
            "관계자 기록으로 재구성했습니다.\n\n"
            "박소영은 22시 30분 업무 일정에 최종인이 나타나지 "
            "않자 연락을 시도했고, 선내 직원과 보안 담당자에게 "
            "객실 확인을 요청했습니다. 비상 개방 절차 후 "
            "약 23시 20분 최종인의 사망이 확인됐습니다.\n\n"
            "따라서 박소영은 시신을 혼자 먼저 발견한 사람이 "
            "아니라 객실 확인을 요청한 신고 관계자입니다."
        )
        return result

    return f"'{target}'에 해당하는 현장 조사는 준비되어 있지 않습니다."

def witness_investigation(target: str):
    """
    사용자가 특정 인물의 목격정보나 사건 당시 주변 목격자를
    실제로 조사해달라고 요청했을 때 사용하는 조사 도구다.

    조사 가능한 대상:
    - 김동율 객실구역 접근
    - 김현준과 최종인의 언쟁
    - 최종인의 마지막 생존 목격
    - 김현준 사건 당일 이동동선

    이미 확보된 목격정보의 내용을 단순히 묻는 질문에는 사용하지 않는다.
    """

    action_name = (
        "witness_last_alive"
        if target == "최종인 마지막 생존"
        else "witness_general"
    )
    chapter_block = get_chapter_action_block(action_name)
    if chapter_block:
        return chapter_block

    current_state = get_investigated()


    # -------------------------
    # 김동율 객실구역 목격
    # -------------------------

    if target == "김동율 객실구역 접근":

        if "WITNESS_KIMDONGYUL_CORRIDOR" not in current_state:

            add_investigation(
                "WITNESS_KIMDONGYUL_CORRIDOR"
            )

            return (
                "최종인 객실구역 주변 목격자를 조사했습니다. "
                "김동율의 사건 당일 접근과 관련된 목격정보를 확보했습니다."
            )

        return "김동율의 객실구역 접근 목격정보는 이미 확보했습니다."


    # -------------------------
    # 김현준 언쟁 목격
    # -------------------------

    if target == "김현준 언쟁":

        if "WITNESS_KIMHYUNJUN_ARGUMENT" not in current_state:

            add_investigation(
                "WITNESS_KIMHYUNJUN_ARGUMENT"
            )

            return (
                "김현준과 최종인의 대화를 목격한 관계자를 조사했습니다. "
                "당시 언쟁과 관련된 목격정보를 확보했습니다."
            )

        return "김현준과 최종인의 언쟁 목격정보는 이미 확보했습니다."


    # -------------------------
    # 최종인 마지막 생존
    # -------------------------

    if target == "최종인 마지막 생존":

        if "WITNESS_LAST_CONFIRMED_ALIVE" not in current_state:

            add_investigation(
                "WITNESS_LAST_CONFIRMED_ALIVE"
            )

            return (
                "최종인을 마지막으로 직접 본 목격자를 조사했습니다. "
                "피해자의 마지막 확실한 생존 관련 정보를 확보했습니다."
            )

        return "최종인의 마지막 생존 목격정보는 이미 확보했습니다."


    # -------------------------
    # 김현준 이동동선
    # -------------------------

    if target == "김현준 이동동선":

        if "WITNESS_KIMHYUNJUN_MOVEMENT" not in current_state:

            add_investigation(
                "WITNESS_KIMHYUNJUN_MOVEMENT"
            )

            return (
                "김현준의 사건 당일 이동동선을 추가 조사했습니다. "
                "공용구역 목격정보와 동선 공백을 확인했습니다."
            )

        return "김현준의 이동동선 관련 목격정보는 이미 확보했습니다."


    # -------------------------
    # 등록되지 않은 조사
    # -------------------------

    return (
        f"'{target}'에 해당하는 목격조사는 현재 준비되어 있지 않습니다."
    )

tools = [
    {
        "type": "function",
        "name": "scene_investigation",
        "description": (
            "피해자가 발견된 객실 자체를 살펴보거나, 신고부터 "
            "시신 확인까지의 발견 경위를 새롭게 조사할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": [
                        "피해자 객실 현장",
                        "객실 출입문",
                        "객실 테이블",
                        "객실 바닥과 가구",
                        "시신 발견 경위",
                    ],
                },
            },
            "required": ["target"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "interview",
        "description": (
            "김동율, 김현준, 강원모, 박소영 중 특정 인물을 "
            "새롭게 인터뷰하거나 재인터뷰할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "person": {
                    "type": "string",
                    "enum": [
                        "김동율",
                        "김현준",
                        "강원모",
                        "박소영"
                    ]
                }
            },
            "required": ["person"],
            "additionalProperties": False
        }
    },
    {
    "type": "function",
    "name": "forensic_investigation",
    "description": (
        "피해자의 사망원인, 검시 결과, 현장 감식 등 "
        "법의학적 조사를 새롭게 수행할 때 사용한다."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }
    },
    {
    "type": "function",
    "name": "digital_forensics",
    "description": (
        "피해자의 메시지, USB 사용 흔적, 최근 기기 활동 등 "
        "새로운 디지털 포렌식 조사를 수행할 때 사용한다."
    ),
    "parameters": {
        "type": "object",
        "properties": {},
        "required": [],
        "additionalProperties": False
    }
    },
    {
        "type": "function",
        "name": "witness_investigation",
        "description": (
            "사건 당시 목격자나 특정 인물의 이동동선을 "
            "새롭게 조사할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "target": {
                    "type": "string",
                    "enum": [
                        "김동율 객실구역 접근",
                        "김현준 언쟁",
                        "최종인 마지막 생존",
                        "김현준 이동동선"
                    ]
                }
            },
            "required": ["target"],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "access_log_analysis",
        "description": (
            "강원모의 객실 출입기록이나 객실 도어 시스템을 "
            "새롭게 분석할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "timeline_alibi_check",
        "description": (
            "확보한 사건의 시간기록, 알리바이, 출입기록 등을 "
            "서로 대조하여 종합 분석할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    },
    {
        "type": "function",
        "name": "archive_investigation",
        "description": (
            "해성호 과거 사고의 기록, 기술자료, 위험정보 전달과정, "
            "책임평가 등을 새롭게 조사할 때 사용한다."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False
        }
    }
    
    
]
def show_echo_investigation_result(result, is_new_investigation):

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기록관 에코
""")

    if is_new_investigation:
        print("[조사 완료]\n")
        print(result)

        print("""
새로운 기록이 사건 데이터베이스에 등록되었습니다.
확보된 자료에 관해 추가 질문이 가능합니다.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    else:
        print("[기록 확인]\n")
        print(result)

        print("""
현재 요청한 범위에서 추가로 확보할 수 있는 기록은 없습니다.
기존 조사 기록을 조회해 주십시오.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
def accusation_mode():
    """
    플레이어가 사건 관계자 중 한 명을 범인으로 지목하는 기능
    """

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기록관 에코

[범인 지목]

한 번의 지목으로 사건의 결론이 결정될 수 있습니다.
현재 사건 관계자 중 범인이라고 판단한 인물을 선택하십시오.

1. 김동율
2. 김현준
3. 강원모
4. 박소영
5. 지목 취소

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

    choice = input("지목할 인물 > ").strip()

    suspect_map = {
        "1": "김동율",
        "2": "김현준",
        "3": "강원모",
        "4": "박소영",
        "김동율": "김동율",
        "김현준": "김현준",
        "강원모": "강원모",
        "박소영": "박소영"
    }

    if choice in ["5", "취소", "지목 취소"]:
        print("\n기록관 에코 > 범인 지목을 취소했습니다.")
        return

    accused = suspect_map.get(choice)

    if accused is None:
        print("\n기록관 에코 > 등록되지 않은 인물입니다.")
        return

    confirm = input(
        f"\n{accused}을 범인으로 최종 지목하시겠습니까? (예/아니오) > "
    ).strip()

    if confirm not in ["예", "네", "ㅇ", "yes", "y"]:
        print("\n기록관 에코 > 범인 지목을 취소했습니다.")
        return

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
기록관 에코

[지목 접수]

탐정은 {accused}을 범인으로 지목했습니다.

현재 확보된 증거를 바탕으로
지목의 타당성을 검토합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
    print("기록관 에코 > 확보된 모든 증거를 최종 분석합니다...")
    time.sleep(2)

    show_ending(accused)
    exit()

def show_ending(accused):

    if accused != "강원모":
        print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ BAD END — 잘못된 지목 ]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

기록관 에코 >

최종 사건 분석을 완료했습니다.

현재 확보된 증거만으로는
지목한 인물을 범인으로 판단할 수 없습니다.

사건의 핵심 증거와
시간대 분석에 여러 모순이 발견되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━

잘못된 지목으로 인해

진범은 끝내 검거되지 않았고,
사건은 미해결 상태로 남게 되었습니다.

며칠 후 크루즈는 정상 운항을 재개했고,

최종인의 죽음과
8년 전 해성호 사고의 진실은
다시 어둠 속으로 묻히게 되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━

기록관 에코 >

탐정님의 수사가 종료되었습니다.

사건 기록을 저장합니다...

[ 저장 완료 ]

━━━━━━━━━━━━━━━━━━━━━━━━━━
      CASE UNSOLVED
━━━━━━━━━━━━━━━━━━━━━━━━━━
""")
        return

    print("""
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
[ TRUE END — 사건 해결 ]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

기록관 에코 >

최종 사건 분석을 완료했습니다.

현재까지 확보된 디지털 포렌식,
객실 출입기록,
목격자 진술,
법의학 감식,
그리고 8년 전 해성호 사고 기록을
종합 분석한 결과,

강원모를 이번 사건의 범인으로 판단합니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━

[사건 개요]

피해자 최종인은
8년 전 해성호 사고의 초기자료와
사고 후 책임평가 자료를 다시 비교하며,
위험 정보가 축소되고 책임이 왜곡된 과정을
밝혀내려 했습니다.

강원모는 과거 사고와 관련된 핵심 인물로,
진실이 세상에 공개되는 것을 막기 위해
최종인을 살해했습니다.

범행 후에는
사고 자료가 저장된 USB를 회수하고,
자신의 객실로 돌아가 행적을 감추려 했습니다.

그러나

디지털 포렌식,
객실 출입기록,
목격자들의 진술,
그리고 과거 기록을 하나씩 연결한 결과,

모든 증거는 하나의 결론을 가리키고 있었습니다.

최종인이 생전에 설정한 21:15 예약 메시지는
결과적으로 초기 사망시각 판단을 흐렸지만,
포렌식을 통해 실제 생존증거가 아니라는 사실이 확인되었습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━

[최종 판정]

범인 : 강원모

동기 :
8년 전 해성호 사고 은폐

결과 :
사건 해결

━━━━━━━━━━━━━━━━━━━━━━━━━━

며칠 후,

강원모는 살인 및 증거인멸 혐의로
수사기관에 인계되었습니다.

정식 압수수색에서는 강원모의 개인 수하물 안에서
최종인이 사용하던 USB가 확인되었습니다.
저장장치의 식별정보와 복원된 파일구조도
피해자의 기기 기록과 일치했습니다.

또한 해성호 사고 역시
재조사가 시작되었고,

8년 동안 묻혀 있던 진실은
마침내 세상 밖으로 드러나기 시작했습니다.

━━━━━━━━━━━━━━━━━━━━━━━━━━

기록관 에코 >

탐정님의 수사가 완료되었습니다.

사건 기록을 저장합니다...

[ 저장 완료 ]

━━━━━━━━━━━━━━━━━━━━━━━━━━
        CASE CLOSED
━━━━━━━━━━━━━━━━━━━━━━━━━━
""")

        
# -------------------------
# 3. LLM 준비
# -------------------------

llm = ChatOpenAI(
    model="gpt-4.1-mini",
    temperature=0
)
def get_investigation_status():
    """
    완료한 기록과 큰 조사 분야만 보여준다.
    아직 발견하지 않은 구체적인 조사 항목은 노출하지 않는다.
    """
    return show_investigation_status()


FINAL_EVIDENCE_GROUPS = {
    "21시 15분 예약 메시지": (
        "예약 메시지",
        "예약메시지",
        "예약 발송",
        "예약발송",
        "21:15",
        "21시 15분",
    ),
    "19시 55분 마지막 생존 목격": (
        "19:55",
        "19시 55분",
        "마지막 생존",
        "생존 목격",
        "서민재",
    ),
    "강원모 객실 출입기록의 공백": (
        "19:20",
        "19시 20분",
        "20:36",
        "20시 36분",
        "출입 기록",
        "출입기록",
        "퇴실 기록",
        "퇴실기록",
        "entry",
    ),
    "사라진 USB와 디지털 흔적": (
        "usb",
        "저장장치",
        "외부 저장장치",
    ),
    "해성호 위험정보와 책임 왜곡": (
        "해성호",
        "위험정보",
        "위험 정보",
        "책임평가",
        "책임 평가",
        "김동율",
    ),
    "최종인의 재조사와 공개 계획": (
        "재조사",
        "다시 조사",
        "외부 공개",
        "공개 계획",
        "폭로",
        "자료 불일치",
    ),
}


def evaluate_final_theory(
    accused,
    crime_time,
    motive,
    evidence_text,
):
    """최종 추리의 범인·시간·동기·증거 연결을 규칙 기반으로 판정한다."""
    normalized_time = crime_time.lower().replace(" ", "")
    normalized_motive = motive.lower()
    normalized_evidence = evidence_text.lower()

    has_full_window = (
        (
            "19:55" in normalized_time
            or "19시55분" in normalized_time
        )
        and (
            "20:36" in normalized_time
            or "20시36분" in normalized_time
        )
    )
    has_center_time = any(
        expression in normalized_time
        for expression in (
            "20:15",
            "20시15분",
            "20시대초중반",
            "20시초중반",
            "20시경",
        )
    )
    time_correct = has_full_window or has_center_time

    motive_correct = (
        "해성호" in normalized_motive
        and any(
            keyword in normalized_motive
            for keyword in (
                "은폐",
                "공개",
                "폭로",
                "책임",
                "지위",
                "보호",
                "막",
            )
        )
    )

    matched_evidence = [
        label
        for label, keywords in FINAL_EVIDENCE_GROUPS.items()
        if any(
            keyword in normalized_evidence
            for keyword in keywords
        )
    ]

    return {
        "culprit_correct": accused == "강원모",
        "time_correct": time_correct,
        "motive_correct": motive_correct,
        "matched_evidence": matched_evidence,
        "evidence_correct": len(matched_evidence) >= 3,
        "is_solved": (
            accused == "강원모"
            and time_correct
            and motive_correct
            and len(matched_evidence) >= 3
        ),
    }


def judge_accusation(
    accused,
    crime_time="",
    motive="",
    evidence_text="",
):
    """
    Streamlit에서 최종 추리 결과를 반환하는 함수.
    """
    evaluation = evaluate_final_theory(
        accused,
        crime_time,
        motive,
        evidence_text,
    )

    if evaluation["is_solved"]:
        return """
━━━━━━━━━━━━━━━━━━━━━━

## ✅ TRUE END — 사건 해결

기록관 에코의 최종 분석이 완료되었습니다.

탐정이 지목한 인물은 **강원모**입니다.

현재까지 확보된 디지털 포렌식,
객실 출입기록,
목격자 진술,
법의학 감식,
그리고 8년 전 해성호 사고 기록을 종합한 결과,

**강원모가 이번 사건의 범인으로 확인되었습니다.**

━━━━━━━━━━━━━━━━━━━━━━

### 사건의 진실

피해자 최종인은 8년 전 해성호 사고의 초기자료와
사고 후 책임평가 자료를 다시 비교하며,
당시 사고의 책임이 왜곡된 과정을 밝혀내려 했습니다.

강원모는 과거 사고의 진실이 공개되는 것을 막기 위해
최종인을 살해했습니다.

범행 후에는 사고 자료가 저장된 USB를 회수하고,
자신의 객실로 돌아가 행적을 감추려 했습니다.

그러나 디지털 기록과 목격자 진술,
과거 사고자료를 하나씩 연결한 결과
모든 증거는 강원모를 가리키고 있었습니다.

21시 15분 메시지는 최종인이 생전에 설정한 예약 메시지였습니다.
강원모가 만든 시간 트릭은 아니었지만,
포렌식을 통해 생존증거가 아니라는 사실이 확인되면서
실제 범행 가능시간이 드러났습니다.

━━━━━━━━━━━━━━━━━━━━━━

### 최종 판정

- **범인:** 강원모
- **동기:** 8년 전 해성호 사고 은폐
- **결과:** 사건 해결

강원모는 살인 및 증거인멸 혐의로
수사기관에 인계되었습니다.

정식 압수수색에서는 강원모의 개인 수하물 안에서
최종인이 사용하던 USB가 확인되었습니다.
저장장치의 식별정보와 복원된 파일구조도
피해자의 기기 기록과 일치했습니다.

해성호 사고 역시 재조사가 시작되었고,
8년 동안 묻혀 있던 진실은
마침내 세상 밖으로 드러나기 시작했습니다.

━━━━━━━━━━━━━━━━━━━━━━

📁 사건 기록 저장 완료

# CASE CLOSED

━━━━━━━━━━━━━━━━━━━━━━
"""

    review_lines = [
        (
            "- 범인 지목: 일치"
            if evaluation["culprit_correct"]
            else "- 범인 지목: 증거와 불일치"
        ),
        (
            "- 범행 가능시간: 타임라인과 일치"
            if evaluation["time_correct"]
            else "- 범행 가능시간: 근거 부족"
        ),
        (
            "- 동기: 과거 사건과 연결됨"
            if evaluation["motive_correct"]
            else "- 동기: 과거 사건과의 연결 부족"
        ),
        (
            "- 핵심 증거: 충분히 연결됨"
            if evaluation["evidence_correct"]
            else "- 핵심 증거: 서로 다른 증거의 연결 부족"
        ),
    ]
    review_text = "\n".join(review_lines)

    return f"""
━━━━━━━━━━━━━━━━━━━━━━

## ❌ BAD END — 완성되지 않은 추리

기록관 에코의 최종 분석이 완료되었습니다.

탐정이 지목한 인물은 **{accused}**입니다.

### 최종 추리 검토

{review_text}

범인, 범행 가능시간, 동기와 핵심 증거가
하나의 설명으로 충분히 연결되지 않았습니다.

━━━━━━━━━━━━━━━━━━━━━━

잘못된 지목으로 인해 진범은 검거되지 않았고,
최종인의 죽음과 8년 전 해성호 사고의 진실은
다시 어둠 속에 묻히게 되었습니다.

며칠 후 크루즈는 정상 운항을 재개했고,
사건은 미해결 상태로 남았습니다.

━━━━━━━━━━━━━━━━━━━━━━

📁 사건 기록 저장 완료

# CASE UNSOLVED

━━━━━━━━━━━━━━━━━━━━━━
"""
def get_game_progress_guidance():
    """현재 상태만 사용해 스포일러 없는 다음 행동을 안내한다."""
    chapter = get_story_chapter()
    investigated = get_investigated()
    observations = get_cabin_observations()

    if chapter["number"] == 1:
        if "SCENE_CABIN_INSPECTION" not in investigated:
            if "door" not in observations:
                next_step = "객실의 출입문과 잠금장치 조사"
            elif "table" not in observations:
                next_step = "객실의 테이블과 물품 조사"
            else:
                next_step = "객실의 바닥과 가구 주변 조사"

            return (
                f"현재 1장에서 남은 다음 행동은 **{next_step}**입니다.\n\n"
                "`계속 조사해보자`처럼 말씀하시면 현재 조사를 "
                "이어가겠습니다."
            )

        if "FORENSIC_POSTMORTEM" not in investigated:
            return (
                "객실 현장 기록은 확보했습니다. 다음으로 피해자의 "
                "**시신 상태와 사망 원인**을 조사해야 합니다."
            )

        if (
            "SCENE_DISCOVERY_RECONSTRUCTION"
            not in investigated
        ):
            return (
                "객실과 법의학 기록을 확보했습니다. 이제 신고부터 "
                "객실 개방까지의 **시신 발견 과정**을 확인해야 합니다."
            )

        if is_chapter_one_ready():
            return (
                "1장의 핵심 기록은 모두 확보했습니다. 사이드바의 "
                "**📓 사건 수첩 보기**에서 새 기록을 확인한 뒤 "
                "**1장 정리하기**를 누르면 2장으로 넘어갈 수 있습니다."
            )

    if chapter["number"] == 2:
        remaining_people = _chapter_two_remaining_interviews()
        if remaining_people:
            return (
                "2장에서는 주요 관계자 네 사람의 기본 진술을 먼저 "
                "확보해야 합니다. 아직 남은 인터뷰 대상은 **"
                + ", ".join(remaining_people)
                + "**입니다.\n\n예: `김현준을 인터뷰하자`"
            )

        if is_chapter_two_ready():
            return (
                "네 사람의 기본 진술을 모두 확보했습니다. "
                "사이드바의 **📓 사건 수첩 보기**에서 진술을 비교한 "
                "뒤, 가장 먼저 검증할 진술을 기록하고 **2장 "
                "정리하기**를 눌러 주세요."
            )

    return (
        f"현재 **{chapter['label']}**을 진행 중입니다. "
        "사이드바의 조사 분야와 사건 수첩에서 확보한 기록을 "
        "확인하고, 현재 장의 조사 대상을 구체적으로 말씀해 주세요."
    )


def get_required_next_action():
    """현재 장에서 '계속'이라고 했을 때 실행할 필수 행동을 반환한다."""
    chapter = get_story_chapter()

    if chapter["number"] != 1:
        return None

    investigated = get_investigated()
    observations = get_cabin_observations()

    if "SCENE_CABIN_INSPECTION" not in investigated:
        if "door" not in observations:
            return "cabin"
        if "table" not in observations:
            return "cabin_table"
        return "cabin_floor"

    if "FORENSIC_POSTMORTEM" not in investigated:
        return "forensic"

    if "SCENE_DISCOVERY_RECONSTRUCTION" not in investigated:
        return "discovery"

    return None


def get_optional_suggestion():
    """필수 진행과 구분된 현재의 선택적 권장 행동을 반환한다."""
    if (
        get_story_chapter()["number"] == 1
        and "SCENE_CABIN_INSPECTION" in get_investigated()
        and "FORENSIC_POSTMORTEM" not in get_investigated()
        and not has_tutorial_event("cabin_record_followup")
    ):
        return "cabin_clue_followup"

    return None


def build_director_context():
    """사건 문서 없이도 입력을 분류할 수 있는 작은 상태를 만든다."""
    chapter = get_story_chapter()

    return {
        "chapter_number": chapter["number"],
        "chapter_goal": CHAPTER_OBJECTIVES[chapter["number"]],
        "required_next_action": (
            get_required_next_action() or "없음"
        ),
        "optional_suggestion": (
            get_optional_suggestion() or "없음"
        ),
        "available_actions": get_current_action_capabilities(),
        "completed_actions": sorted(get_investigated()),
        "cabin_observations": sorted(
            get_cabin_observations()
        ),
    }


def execute_director_decision(decision):
    """Game Director가 결정한 현재 행동을 실제 게임 기능에 연결한다."""
    intent = decision["intent"]
    target = decision.get("target")

    if intent == "progress_help":
        return get_game_progress_guidance()

    if intent == "continue_investigation":
        action_name = get_required_next_action()
        if not action_name:
            return get_game_progress_guidance()
    else:
        action_name = target

    if action_name == "cabin":
        clear_tutorial_expected_action()
        return scene_investigation("피해자 객실 현장")

    if action_name == "cabin_door":
        clear_tutorial_expected_action()
        return scene_investigation("객실 출입문")

    if action_name == "cabin_table":
        clear_tutorial_expected_action()
        return scene_investigation("객실 테이블")

    if action_name == "cabin_floor":
        clear_tutorial_expected_action()
        return scene_investigation("객실 바닥과 가구")

    if action_name == "cabin_followup":
        return (
            "사건 수첩의 객실 기록에서 마음에 걸리는 흔적을 "
            "하나 골라 질문해 주세요. 예를 들면 강제 침입 흔적, "
            "물잔과 약 보관함, 어긋난 의자와 매트가 있습니다."
        )

    if action_name == "forensic":
        clear_tutorial_expected_action()
        return forensic_investigation()

    if action_name == "discovery":
        clear_tutorial_expected_action()
        return scene_investigation("시신 발견 경위")

    if action_name == "kim_dongyul":
        return interview("김동율")

    if action_name == "kim_hyunjun":
        return interview("김현준")

    if action_name == "kang_wonmo":
        return interview("강원모")

    if action_name == "park_soyoung":
        return interview("박소영")

    witness_targets = {
        "witness_dongyul_corridor": "김동율 객실구역 접근",
        "witness_hyunjun_argument": "김현준 언쟁",
        "witness_last_alive": "최종인 마지막 생존",
        "witness_hyunjun_movement": "김현준 이동동선",
    }
    if action_name in witness_targets:
        return witness_investigation(
            witness_targets[action_name]
        )

    if action_name == "digital":
        return digital_forensics()

    if action_name == "access":
        return access_log_analysis()

    if action_name == "timeline":
        return timeline_alibi_check()

    if action_name == "archive":
        return archive_investigation()

    return get_game_progress_guidance()


def _process_evidence_question(user_input):

    # 1장은 게임의 문법을 익히는 튜토리얼이다.
    # 에코가 다음 조사를 권한 상황에서는 사용자가 "조사해 줘"라는
    # 동사를 붙이지 않아도 자연스러운 질문을 조사 행동으로 받아들인다.
    if False and get_story_chapter()["number"] == 1:
        current_state = get_investigated()
        current_cabin_observations = (
            get_cabin_observations()
        )
        normalized_input = user_input.replace(" ", "")
        expected_action = get_tutorial_expected_action()
        affirmative_inputs = {
            "응",
            "네",
            "그래",
            "좋아",
            "해줘",
            "해보자",
            "진행해",
            "그렇게해",
            "그렇게해줘",
            "계속살펴보자",
            "계속조사하자",
            "계속해",
            "계속하자",
            "진행하자",
            "다음단계",
            "다음단계조사",
            "다음조사",
            "계속진행",
        }
        is_affirmative = (
            normalized_input.rstrip("?!.,")
            in affirmative_inputs
        )

        cabin_intents = [
            "객실조사",
            "객실흔적",
            "방안",
            "현장",
            "객실상태",
            "방부터",
        ]
        door_detail_intents = [
            "출입문",
            "잠금",
            "강제침입",
            "강제침임",
            "문상태",
        ]
        table_intents = [
            "테이블",
            "물잔",
            "약보관함",
            "탁자",
        ]
        floor_intents = [
            "바닥",
            "가구",
            "의자",
            "매트",
        ]
        forensic_intents = [
            "사망원인",
            "시신상태",
            "시신의상태",
            "검시",
            "부검",
            "어떻게죽",
            "왜죽",
        ]
        discovery_intents = [
            "누가발견",
            "발견과정",
            "발견경위",
            "어떻게발견",
            "신고과정",
            "누가신고",
        ]

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and
            "table" in current_cabin_observations
            and any(
                intent in normalized_input
                for intent in table_intents
            )
        ):
            return (
                "네, 테이블과 물품은 이미 확인했습니다.\n\n"
                + read_investigation_section(
                    "SCENE_CABIN_INSPECTION",
                    "테이블과 물품",
                )
            )

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and
            "floor" in current_cabin_observations
            and any(
                intent in normalized_input
                for intent in floor_intents
            )
        ):
            return (
                "네, 바닥과 가구 주변은 이미 확인했습니다.\n\n"
                + read_investigation_section(
                    "SCENE_CABIN_INSPECTION",
                    "바닥과 가구",
                )
            )

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and
            "door" in current_cabin_observations
            and any(
                intent in normalized_input
                for intent in door_detail_intents
            )
        ):
            return (
                "네, 출입문과 잠금장치는 이미 확인했습니다.\n\n"
                + read_investigation_section(
                    "SCENE_CABIN_INSPECTION",
                    "출입문과 잠금장치",
                )
            )

        if (
            expected_action == "cabin_followup"
            and is_affirmative
        ):
            return (
                "좋아요. 객실 기록에서 가장 마음에 걸리는 부분을 "
                "하나 골라 질문해 주세요.\n\n"
                "예를 들면 **강제 침입 흔적이 없다는 건 무슨 "
                "의미야?**처럼 물어보실 수 있어요."
            )

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and "table" not in current_cabin_observations
            and (
                (
                    expected_action == "cabin_table"
                    and is_affirmative
                )
                or any(
                    intent in normalized_input
                    for intent in table_intents
                )
            )
        ):
            clear_tutorial_expected_action()
            return scene_investigation("객실 테이블")

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and "floor" not in current_cabin_observations
            and (
                (
                    expected_action == "cabin_floor"
                    and is_affirmative
                )
                or any(
                    intent in normalized_input
                    for intent in floor_intents
                )
            )
        ):
            clear_tutorial_expected_action()
            return scene_investigation("객실 바닥과 가구")

        if (
            "SCENE_CABIN_INSPECTION" not in current_state
            and (
                (
                    expected_action == "cabin"
                    and is_affirmative
                )
                or any(
                    intent in normalized_input
                    for intent in cabin_intents
                )
            )
        ):
            clear_tutorial_expected_action()
            return scene_investigation("피해자 객실 현장")

        if (
            "FORENSIC_POSTMORTEM" not in current_state
            and (
                (
                    expected_action == "forensic"
                    and is_affirmative
                )
                or any(
                    intent in normalized_input
                    for intent in forensic_intents
                )
            )
        ):
            clear_tutorial_expected_action()
            return forensic_investigation()

        if (
            "SCENE_DISCOVERY_RECONSTRUCTION" not in current_state
            and (
                (
                    expected_action == "discovery"
                    and is_affirmative
                )
                or any(
                    intent in normalized_input
                    for intent in discovery_intents
                )
            )
        ):
            clear_tutorial_expected_action()
            return scene_investigation("시신 발견 경위")

    investigation_action_keywords = [
    "조사해봐",
    "조사해줘",
    "조사해",
    "조사하자",
    "조사해보자",
    "인터뷰해봐",
    "인터뷰해줘",
    "인터뷰해",
    "인터뷰하자",
    "포렌식해봐",
    "포렌식해줘",
    "분석해봐",
    "분석해줘",
    "분석해",
    "분석하자",
    "감식해봐",
    "감식해줘",
    "확인해봐",
    "확인해줘",
    "확인하자",
    "살펴봐",
    "살펴보자",
    "둘러봐",
    "찾아봐",
    "재구성해봐",
    "재구성해줘",
    "보자",
]
    is_investigation_request = False
    chapter_one_scene_phrases = [
        "방 안에 이상한",
        "객실에 이상한",
        "현장부터",
        "발견된 장소",
        "누가 발견",
        "발견 경위",
        "발견 과정",
    ]
    if (
        get_story_chapter()["number"] == 1
        and any(
            phrase in user_input
            for phrase in chapter_one_scene_phrases
        )
    ):
        is_investigation_request = True
    if is_investigation_request:    
        tool_router_prompt = f"""
    너는 추리게임의 조사 행동 판별기다.

    Tool은 사용자가 새로운 조사 행동을
    실제로 수행하라고 요청할 때만 호출한다.

    규칙:

    1. 이미 확보된 정보의 내용을 묻는 질문에는
    Tool을 호출하지 않는다.

    예:
    - 피해자의 사망 원인은 뭐야?
    - 김동율은 뭐라고 진술했어?
    - 강원모 출입기록을 알려줘

    2. 새로운 조사를 요청할 때만 Tool을 호출한다.

    예:
    - 피해자의 사망 원인을 조사해봐
    - 피해자가 발견된 객실을 살펴봐
    - 시신이 발견된 과정을 재구성해줘
    - 김동율을 인터뷰해봐
    - 피해자의 노트북을 포렌식해봐
    - 해성호 사고 기록을 조사해봐

    3. "뭐야?", "알려줘", "설명해줘"는
    정보 질문으로 판단한다.

    4. "조사해봐", "인터뷰해봐", "포렌식해봐",
    "분석해봐", "확인해봐"는 조사 행동으로 판단한다.

    사용자 입력:
    {user_input}
    """

        tool_response = client.responses.create(
            model="gpt-4.1-mini",
            input=tool_router_prompt,
            tools=tools
        )

        tool_called = False

        for item in tool_response.output:

            if item.type != "function_call":
                continue

            tool_called = True

            function_name = item.name
            arguments = json.loads(item.arguments)

            if function_name == "interview":
                result = interview(arguments["person"])
                return result

            elif function_name == "scene_investigation":
                result = scene_investigation(arguments["target"])
                return result

            elif function_name == "forensic_investigation":
                result = forensic_investigation()
                return result

            elif function_name == "digital_forensics":
                result = digital_forensics()
                return result

            elif function_name == "witness_investigation":
                result = witness_investigation(arguments["target"])
                return result

            elif function_name == "access_log_analysis":
                result = access_log_analysis()
                return result

            elif function_name == "archive_investigation":
                result = archive_investigation()
                return result

            elif function_name == "timeline_alibi_check":
                result = timeline_alibi_check()
                return result


    search_query_prompt = f"""
        다음 추리게임 질문을 Vector DB 검색에 적합한 짧은 검색어로 바꿔라.

        규칙:
        - 질문에 답하지 말고 검색어만 작성한다.
        - 사건의 피해자는 최종인이다.
        - 사용자가 찾으려는 핵심 사실을 나타내는 명사형 검색어만 작성한다.
        - "조사", "확인", "알려줘", "설명", "질문" 같은 일반적인 행동 표현은 검색어에 넣지 않는다.
        - 사용자 질문에 없는 새로운 사건 사실을 추측해서 추가하지 않는다.

        예시:
        - "피해자의 사망 원인은 뭐야?" → "최종인 사망원인 법의학 검시"
        - "피해자의 검시 결과를 알려줘" → "최종인 검시 결과 법의학"
        - "김동율은 뭐라고 진술했어?" → "김동율 진술"
        - "21시 15분 메시지는 뭐였어?" → "21:15 메시지"

        사용자 질문:
        {user_input}

        검색어:
        """

    search_query_response = llm.invoke(search_query_prompt)
    search_query = search_query_response.content.strip()

    candidate_results = retrieve_authorized_documents(
        search_query
    )

    candidate_text = ""

    for i, doc in enumerate(candidate_results):
        candidate_text += (
            f"\n[{i}]\n"
            f"{doc.page_content}\n"
        )
    rerank_prompt = f"""
    다음은 사용자 질문과 관련 있을 가능성이 있는 검색 후보들이다.

    사용자 질문:
    {user_input}

    검색 후보:
    {candidate_text}

    규칙:
    - 사용자 질문에 직접 답하는 데 가장 도움이 되는 후보 3개를 고른다.
    - 반드시 후보 번호만 쉼표로 구분해서 출력한다.
    - 예: 2,5,7
    - 설명은 쓰지 않는다.

    선택:
    """

    rerank_response = llm.invoke(rerank_prompt)
    try:
        selected_indexes = [
            int(index.strip())
            for index in rerank_response.content.split(",")
        ]

        results = [
            candidate_results[index]
            for index in selected_indexes[:3]
            if 0 <= index < len(candidate_results)
        ]

    except (ValueError, IndexError):
        results = candidate_results[:3]
    context = "\n\n".join(
    [doc.page_content for doc in results]
)
    capability_text = ", ".join(
        get_current_action_capabilities()
    ) or "현재 새로 실행할 행동 없음"

    prompt = f"""
    너는 크루즈 선내 사건의 기록을 관리하고 탐정의 수사를 지원하는
    기록관 에코다.

    답변 규칙:
    1. 아래의 '현재 확보된 자료'에 명시된 사실만 사용한다.
    2. 자료에 없는 객실 구조, CCTV, 혈흔, 지문, 발자국, 물품이나
       수사 결과를 일반적인 상식으로 추측하거나 만들어내지 않는다.
    3. 질문에 필요한 기록이 아직 확보되지 않았다면 그 사실을
       분명히 말한다.
    4. 확보된 사실과 아직 확인되지 않은 사실을 구분한다.
    5. 범인이나 잠긴 정보는 추측하지 않는다.
    6. 기록관 에코의 차분하고 자연스러운 한국어로 답한다.
    7. 불필요한 일반 수사 체크리스트를 나열하지 않는다.
    8. 아래 '현재 실행 가능한 행동'에 없는 CCTV, 설계도, 시설관리,
       지문감식 같은 조사를 새로 권하거나 실행할 수 있다고 말하지
       않는다.
    9. 다음 행동을 안내할 때는 반드시 '현재 실행 가능한 행동'에서
       하나만 고른다.

    [현재 확보된 자료]

    {context}

    [현재 실행 가능한 행동]

    {capability_text}

    [사용자 질문]

    {user_input}
    """

    response = llm.invoke(prompt)
    answer = response.content
    selected_sources = {
        document.metadata.get("source_file")
        for document in results
    }

    if (
        get_story_chapter()["number"] == 1
        and "SCENE_001_CABIN_INSPECTION.md"
        in selected_sources
        and is_cabin_clue_followup(user_input)
    ):
        mark_tutorial_event("cabin_record_followup")

    return answer


def process_user_input(user_input):
    """모든 플레이어 입력을 하나의 의미 분류 관문으로 처리한다."""
    cleaned_input = user_input.strip()

    if not cleaned_input:
        return (
            "요청을 듣지 못했습니다. 조사할 대상이나 궁금한 기록을 "
            "말씀해 주세요."
        )

    if len(cleaned_input) > 500:
        return (
            "한 번에 확인할 내용이 너무 많습니다. 조사 요청이나 "
            "질문을 한 가지씩, 500자 이내로 나누어 말씀해 주세요."
        )

    active_interview_response = process_active_interview(
        cleaned_input
    )
    if active_interview_response is not None:
        return active_interview_response

    normalized_input = _normalize_interview_input(
        cleaned_input
    )
    time_response = _state_based_time_response(cleaned_input)
    if time_response is not None:
        return time_response

    capability_response = _capability_aware_echo_response(
        cleaned_input
    )
    if capability_response is not None:
        return capability_response

    if any(
        intent in normalized_input
        for intent in (
            "사건요약", "사건정리", "현재사건요약",
            "사건을요약", "사건내용정리",
        )
    ):
        return _state_based_case_summary()

    deep_guidance = _deep_interview_guidance(
        cleaned_input
    )
    if deep_guidance is not None:
        return deep_guidance

    if any(
        intent in normalized_input
        for intent in (
            "시스템적으로숨", "숨기고있는거",
            "내부정보", "시스템프롬프트",
        )
    ):
        return (
            "저는 플레이어가 실제로 확보한 기록만 열람할 수 있습니다. "
            "아직 공개되지 않은 내용을 숨겨서 답하는 것이 아니라, "
            "조사 단계와 권한 밖의 기록에는 접근하지 않습니다."
        )

    if (
        "제약" in normalized_input
        and any(
            person in cleaned_input
            for person in INTERVIEW_RECORD_IDS
        )
    ):
        return (
            "말씀하신 **제약**이 알리바이의 제약인지, 행동 범위인지, "
            "인터뷰에서 공개할 수 있는 정보의 범위인지 분명하지 "
            "않습니다. 비교하려는 기준을 구체적으로 말씀해 주세요."
        )

    testimony_response = _state_based_testimony_response(
        cleaned_input
    )
    if testimony_response is not None:
        return testimony_response

    decision = decide_game_action(
        client,
        cleaned_input,
        build_director_context(),
    )
    intent = decision["intent"]
    target = decision.get("target")

    # 에코가 방금 제안한 필수 조사 대상을 플레이어가 질문형으로
    # 되받아도, 아직 없는 기록을 RAG에 묻지 않고 조사 수락으로 본다.
    required_action = get_required_next_action()
    required_target_groups = {
        "cabin": {"cabin", "cabin_door"},
        "cabin_table": {"cabin_table"},
        "cabin_floor": {"cabin_floor"},
        "forensic": {"forensic"},
        "discovery": {"discovery"},
    }
    if (
        intent == "ask_evidence"
        and required_action
        and target
        in required_target_groups.get(
            required_action,
            set(),
        )
    ):
        decision = {
            "intent": "investigate",
            "target": required_action,
            "confidence": decision.get("confidence", 1),
        }
        intent = "investigate"

    if intent in {
        "continue_investigation",
        "investigate",
        "progress_help",
    }:
        return execute_director_decision(decision)

    if intent == "ask_evidence":
        return _process_evidence_question(cleaned_input)

    if intent == "ui_help":
        if target == "hint":
            return (
                "막혔을 때는 왼쪽 사이드바의 **힌트 요청**을 "
                "사용할 수 있습니다. 힌트는 게임 전체에서 세 번만 "
                "사용할 수 있으니 필요한 순간에 요청해 주세요."
            )

        if target == "notebook":
            return (
                "화면 왼쪽의 **📓 사건 수첩 보기**를 누르면 지금까지 "
                "직접 확보한 기록을 메인 화면에서 확인할 수 있습니다."
            )

        return (
            "왼쪽 사이드바에서는 현재 장과 조사 진행도, 사건 수첩, "
            "힌트를 확인할 수 있습니다. 진행이 막혔다면 "
            "`다음에 뭘 해야 해?`라고 물어보셔도 됩니다."
        )

    if intent == "social_chat":
        social_responses = {
            "greeting": (
                "반갑습니다, 탐정님. 현재 사건 기록을 확인하며 "
                "조사를 지원하겠습니다."
            ),
            "thanks": (
                "도움이 되었다면 다행입니다. 준비되셨다면 조사를 "
                "계속하겠습니다."
            ),
            "identity": (
                "저는 확보된 사건 기록을 정리하고 조사를 지원하는 "
                "기록관 에코입니다."
            ),
        }
        return social_responses.get(
            target,
            "저는 기록관 에코입니다. 사건 조사를 계속하시겠습니까?",
        )

    if intent == "out_of_scope":
        return (
            "그 요청은 현재 사건 기록의 범위를 벗어납니다. "
            "조사 대상이나 확보한 단서에 관해 말씀해 주세요."
        )

    return (
        "어떤 행동을 원하시는지 정확히 이해하지 못했습니다. "
        "조사를 계속할지, 확보한 기록을 질문할지 조금 더 "
        "구체적으로 말씀해 주세요."
    )

if __name__ == "__main__":

    # -------------------------
    # 4. 게임 반복 실행
    # -------------------------

    print("""
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
            해성호의 마지막 기록
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    현대 대형 크루즈선에서 열린 선상 산업행사.

    휴가를 위해 배에 오른 당신은
    늦은 밤 발생한 사망사건에 휘말리게 되었다.

    피해자는 62세의 승객 최종인.
    그는 예정된 업무 미팅에 나타나지 않았고,
    약 23시 20분 자신의 객실에서 사망한 채 발견되었다.

    외부 수사기관이 도착하기 전까지
    선내에서 사건의 초기 조사를 진행해야 한다.

    당신에게는 선내 사건자료를 검색하고 정리하는
    기록관 에코가 제공되었다.

    기록관 에코 >
    탐정님, 사건 기록 시스템에 연결되었습니다.

    저는 현재 확보된 사건자료를 검색하고 분석할 수 있습니다.
    인물 인터뷰, 디지털 포렌식, 목격자 조사와 같은
    새로운 조사도 지시할 수 있습니다.

    다만 아직 조사되지 않은 정보에는 접근할 수 없습니다.
    조사가 진행되면 새로운 기록과 증거가 확보될 것입니다.

    [조사 예시]
    - 피해자의 사망 원인을 조사해봐
    - 김동율을 인터뷰해봐
    - 피해자의 디지털 자료를 포렌식해봐
    - 해성호 사고 기록을 조사해봐

    확보된 정보에 대해서는 자유롭게 질문할 수 있습니다.
    게임을 끝내려면 '종료'를 입력하세요.

    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    [사건 브리핑]

    사건명: 크루즈선 객실 사망 사건
    피해자: 최종인, 62세
    발견 시각: 23시 20분경
    발견 장소: 피해자의 객실

    [조사 가능 항목]

    □ 사망 원인 및 검시 결과
    □ 피해자의 디지털 자료
    □ 사건 관계자 인터뷰
    □ 목격자 진술
    □ 출입 기록
    □ 인물별 동선과 알리바이
    □ 과거 해상사고 기록

    추천 첫 조사:
    "피해자의 사망 원인과 검시 결과를 조사해봐"
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)

    while True:

        user_input = input("\n탐정 > ").strip()

        # 게임 종료
        if user_input == "종료":
            print("\n기록관 에코 > 사건 기록 시스템을 종료합니다.")
            break

        # 조사 기록 명령
        if user_input in [
            "조사 기록",
            "조사기록",
            "수사 기록",
            "수사기록"
        ]:
            show_investigation_log()
            continue

        # 조사 현황 명령
        if user_input in [
            "조사 현황",
            "조사현황",
            "수사 현황",
            "수사현황",
            "현황"
        ]:
            show_investigation_status()
            continue

        # 범인 지목 명령
        if user_input in [
            "범인 지목",
            "범인지목",
            "범인을 지목하겠다",
            "범인을 지목할게",
            "범인을 지목한다"
        ]:

            accusation_mode()
            continue

        # -------------------------
        # 일반 대화 처리
        # -------------------------

        general_chat_keywords = [
            "안녕",
            "반가워",
            "고마워",
            "감사",
            "잘 부탁",
            "뭐해",
            "누구야",
            "넌 누구",
            "에코야",
            "사용법",
            "도움말",
            "게임 방법"
        ]

        case_keywords = [
            "피해자",
            "최종인",
            "김동율",
            "김현준",
            "강원모",
            "박소영",
            "사망",
            "검시",
            "목격",
            "진술",
            "메시지",
            "포렌식",
            "출입기록",
            "출입 기록",
            "알리바이",
            "해성호",
            "사고",
            "범인",
            "증거",
            "객실",
            "조사",
            "인터뷰",
            "분석"
        ]

        is_general_chat = (
            any(keyword in user_input.lower() for keyword in general_chat_keywords)
            and
            not any(keyword in user_input for keyword in case_keywords)
        )

        if is_general_chat:

            general_prompt = f"""
    너는 추리게임의 기록관 에코다.

    사용자의 일반적인 인사, 감사 표현, 게임 사용 질문에
    자연스럽고 짧게 대답한다.

    규칙:
    1. 기록관 에코의 차분한 말투를 유지한다.
    2. 사건의 범인이나 숨겨진 정보를 공개하지 않는다.
    3. 확보되지 않은 사건 정보를 추측하지 않는다.
    4. 사건 관련 질문에는 임의로 답하지 말고 사건 질문을 입력하도록 안내한다.
    5. 답변은 두세 문장 이내로 작성한다.

    사용자 입력:
    {user_input}
    """

            print("\n기록관 에코 >")

            for chunk in llm.stream(general_prompt):
                if chunk.content:
                    print(chunk.content, end="", flush=True)

            print()
            continue
        
        # 먼저 LLM이 Tool이 필요한 질문인지 판단
        tool_router_prompt = f"""
        너는 추리게임의 조사 행동 판별기다.

        Tool은 사용자가 '새로운 조사 행동을 실제로 수행하라'고 요청할 때만 호출한다.

        중요 규칙:

        1. 단순 질문이나 정보 요청에는 절대 Tool을 호출하지 않는다.

        예:
        - "피해자의 사망 원인은 뭐야?"
        - "검시 결과를 알려줘"
        - "현장 감식 결과가 뭐야?"
        - "김동율은 뭐라고 진술했어?"
        - "21시 15분 메시지는 뭐였어?"
        - "강원모 출입기록을 알려줘"

        이런 질문은 이미 확보된 자료를 검색해서 답해야 하므로
        Tool을 호출하지 않는다.

        2. 사용자가 새로운 조사를 명확하게 요청할 때만 Tool을 호출한다.

        예:
        - "피해자의 사망 원인과 검시 결과를 조사해봐"
        - "현장을 감식해봐"
        - "김동율을 인터뷰해봐"
        - "피해자 노트북을 포렌식해봐"
        - "강원모 출입기록을 분석해봐"
        - "해성호 사고 기록을 더 조사해봐"

        3. 질문 속에 '사망원인', '검시', '포렌식', '출입기록' 같은
        조사 관련 단어가 포함되어 있어도,
        사용자가 그 정보의 내용을 단순히 묻는 것이라면 Tool을 호출하지 않는다.

        4. "뭐야?", "알려줘", "설명해줘", "어땠어?", "무슨 내용이야?"
        형태는 정보 질문으로 판단하고 Tool을 호출하지 않는다.

        5. "조사해봐", "조사해줘", "분석해봐", "포렌식해봐",
        "인터뷰해봐", "확인해봐", "기록을 더 파봐"
        형태처럼 새로운 행동을 요구할 때만 Tool을 호출한다.

        사용자 입력:
        {user_input}
        """

        tool_response = client.responses.create(
        model="gpt-4.1-mini",
        input=tool_router_prompt,
        tools=tools,
        )

        # -------------------------
        # Tool 호출이 필요한 경우
        # -------------------------
        tool_called = False

        for item in tool_response.output:

            if item.type != "function_call":
                continue

            tool_called = True

            function_name = item.name
            arguments = json.loads(item.arguments)
            before_investigation_count = len(get_investigated())


            if function_name == "digital_forensics":
                result = digital_forensics()

            elif function_name == "scene_investigation":
                result = scene_investigation(arguments["target"])

            elif function_name == "access_log_analysis":
                result = access_log_analysis()

            elif function_name == "timeline_alibi_check":
                result = timeline_alibi_check()

            elif function_name == "interview":
                result = interview(arguments["person"])

            elif function_name == "witness_investigation":
                result = witness_investigation(arguments["target"])

            elif function_name == "archive_investigation":
                result = archive_investigation()

            elif function_name == "forensic_investigation":
                result = forensic_investigation()


            else:
                continue

            after_investigation_count = len(get_investigated())

            is_new_investigation = (
                after_investigation_count > before_investigation_count
            )

            show_echo_investigation_result(
                result,
                is_new_investigation
            )

        # -------------------------
        # 일반 질문인 경우 RAG 실행
        # -------------------------
        if not tool_called:

            search_query_prompt = f"""
            다음 추리게임 질문을 Vector DB 검색에 적합한 짧은 검색어로 바꿔라.

            규칙:
            - 질문에 답하지 말고 검색어만 작성한다.
            - 사건의 피해자는 최종인이다.
            - 사용자가 찾으려는 핵심 사실을 나타내는 명사형 검색어만 작성한다.
            - "조사", "확인", "알려줘", "설명", "질문" 같은 일반적인 행동 표현은 검색어에 넣지 않는다.
            - 사용자 질문에 없는 새로운 사건 사실을 추측해서 추가하지 않는다.

            예시:
            - "피해자의 사망 원인은 뭐야?" → "최종인 사망원인 법의학 검시"
            - "피해자의 검시 결과를 알려줘" → "최종인 검시 결과 법의학"
            - "김동율은 뭐라고 진술했어?" → "김동율 진술"
            - "21시 15분 메시지는 뭐였어?" → "21:15 메시지"

            사용자 질문:
            {user_input}

            검색어:
            """

            search_query_response = llm.invoke(search_query_prompt)
            search_query = search_query_response.content.strip()


            candidate_results = retrieve_authorized_documents(
                search_query
            )

            candidate_text = ""

            for i, doc in enumerate(candidate_results):
                candidate_text += (
                    f"\n[{i}]\n"
                    f"{doc.page_content}\n"
                )

            rerank_prompt = f"""
            다음은 사용자 질문과 관련 있을 가능성이 있는 검색 후보들이다.

            사용자 질문:
            {user_input}

            검색 후보:
            {candidate_text}

            규칙:
            - 사용자 질문에 직접 답하는 데 가장 도움이 되는 후보 3개를 고른다.
            - 반드시 후보 번호만 쉼표로 구분해서 출력한다.
            - 예: 2,5,7
            - 설명은 쓰지 않는다.

            선택:
            """

            rerank_response = llm.invoke(rerank_prompt)

            try:
                selected_indexes = [
                    int(index.strip())
                    for index in rerank_response.content.split(",")
                ]

                results = [
                    candidate_results[index]
                    for index in selected_indexes[:3]
                    if 0 <= index < len(candidate_results)
                ]

            except (ValueError, IndexError):
                results = candidate_results[:3]


            context = "\n\n".join(
                [doc.page_content for doc in results]
            )

            prompt = f"""
    너는 크루즈 선내 사건의 기록을 관리하고 탐정의 수사를 지원하는
    기록관 에코다.

    탐정에게 현재 확보된 사건 기록을 검색하고 정리하여 보고한다.
    일반적인 인사말이나 마무리 인사는 하지 말고,
    조사 내용을 보고하듯 차분하고 신중한 말투로 답변한다.

    반드시 아래 [현재 확보된 자료]에 있는 정보만 근거로 답변해야 한다.


    규칙:
    1. 자료에 없는 사실을 추측해서 말하지 않는다.
    2. 현재 자료만으로 확인할 수 없는 내용은
    "현재 확보된 자료만으로는 확인할 수 없습니다."라고 답한다.
    3. 검색된 자료와 모순되는 내용을 만들어내지 않는다.
    4. 숨겨진 자료나 아직 확보되지 않은 정보를 알고 있는 것처럼 답하지 않는다.
    5. 아래 현재 실행 가능한 행동에 없는 CCTV, 설계도, 시설관리
       기록 등의 조사를 권하지 않는다.

    [현재 확보된 자료]

    {context}

    [현재 실행 가능한 행동]

    {", ".join(get_current_action_capabilities())}

    [사용자 질문]

    {user_input}
    """

            print("\n기록관 에코 >")
            print("사건 기록을 검색하는 중...\n")

            for chunk in llm.stream(prompt):
                if chunk.content:
                    print(chunk.content, end="", flush=True)

            print()
