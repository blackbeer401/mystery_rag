from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_chroma import Chroma
from openai import OpenAI
import json
import time
from pathlib import Path

from game_director import decide_game_action
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

            add_investigation(
                "INTERVIEW_KIMDONGYUL_BASIC"
            )

            return "김동율에 대한 기본 인터뷰를 완료했습니다."

        # 객실구역 목격정보까지 확보했다면 심층 재인터뷰 가능
        if (
            "WITNESS_KIMDONGYUL_CORRIDOR"
            in current_state
            and
            "INTERVIEW_KIMDONGYUL_DEEP"
            not in current_state
        ):

            add_investigation(
                "INTERVIEW_KIMDONGYUL_DEEP"
            )

            return (
                "김동율에게 객실구역 목격정보를 제시하고 "
                "심층 재인터뷰를 진행했습니다."
            )

        return (
            "현재 확보된 정보만으로는 "
            "김동율에게 추가로 확인할 새로운 질문이 부족합니다."
        )


    # -------------------------
    # 김현준
    # -------------------------

    if person == "김현준":

        if "INTERVIEW_KIMHYUNJUN_BASIC" not in current_state:

            add_investigation(
                "INTERVIEW_KIMHYUNJUN_BASIC"
            )

            return "김현준에 대한 기본 인터뷰를 완료했습니다."

        if (
            "WITNESS_KIMHYUNJUN_ARGUMENT"
            in current_state
            and
            "INTERVIEW_KIMHYUNJUN_DEEP"
            not in current_state
        ):

            add_investigation(
                "INTERVIEW_KIMHYUNJUN_DEEP"
            )

            return (
                "김현준에게 언쟁 목격정보를 제시하고 "
                "심층 재인터뷰를 진행했습니다."
            )

        return (
            "현재 확보된 정보만으로는 "
            "김현준에게 추가로 확인할 새로운 질문이 부족합니다."
        )


    # -------------------------
    # 강원모
    # -------------------------

    if person == "강원모":

        if "INTERVIEW_KANGWONMO_BASIC" not in current_state:

            add_investigation(
                "INTERVIEW_KANGWONMO_BASIC"
            )

            return "강원모에 대한 기본 인터뷰를 완료했습니다."

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

            add_investigation(
                "INTERVIEW_KANGWONMO_FOLLOWUP"
            )

            return (
                "새롭게 확보한 기록을 바탕으로 "
                "강원모에 대한 추가 인터뷰를 진행했습니다."
            )

        return (
            "현재 확보된 정보만으로는 "
            "강원모를 다시 추궁할 새로운 근거가 부족합니다."
        )


    # -------------------------
    # 박소영
    # -------------------------

    if person == "박소영":

        if "INTERVIEW_PARKSOYOUNG" not in current_state:

            add_investigation(
                "INTERVIEW_PARKSOYOUNG"
            )

            return "박소영에 대한 인터뷰를 완료했습니다."

        return "박소영에 대한 인터뷰는 이미 완료했습니다."


    # -------------------------
    # 등록되지 않은 인물
    # -------------------------

    return f"{person}은 현재 인터뷰 대상자로 등록되어 있지 않습니다."

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

    prompt = f"""
    너는 크루즈 선내 사건의 기록을 관리하고 탐정의 수사를 지원하는
    기록관 에코다.

    답변 규칙:
    1. 아래의 '현재 확보된 자료'에 명시된 사실만 사용한다.
    2. 자료에 없는 객실 구조, CCTV, 혈흔, 지문, 발자국, 물품이나
       수사 결과를 일반적인 상식으로 추측하거나 만들어내지 않는다.
    3. 질문에 필요한 기록이 아직 확보되지 않았다면 그 사실을
       분명히 말하고, 어떤 종류의 조사가 필요한지만 짧게 안내한다.
    4. 확보된 사실과 아직 확인되지 않은 사실을 구분한다.
    5. 범인이나 잠긴 정보는 추측하지 않는다.
    6. 기록관 에코의 차분하고 자연스러운 한국어로 답한다.
    7. 불필요한 일반 수사 체크리스트를 나열하지 않는다.

    [현재 확보된 자료]

    {context}

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

    [현재 확보된 자료]

    {context}

    [사용자 질문]

    {user_input}
    """

            print("\n기록관 에코 >")
            print("사건 기록을 검색하는 중...\n")

            for chunk in llm.stream(prompt):
                if chunk.content:
                    print(chunk.content, end="", flush=True)

            print()
