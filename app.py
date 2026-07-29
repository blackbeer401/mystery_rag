import streamlit as st
import time
from game import (
    process_user_input,
    get_start_message,
    judge_accusation,
    get_investigation_status
)
from game_state import (
    bind_session_state,
    reset_game_state,
    get_sidebar_summary,
    use_hint,
    get_story_chapter,
    get_chapter_transition_message,
    get_chapter_action_block
)

st.set_page_config(
    page_title="해성호의 마지막 기록",
    page_icon="🔎"
)

# 사용자 질문에 따라 답변 앞에 붙일 아이콘 결정
def get_answer_icon(user_input):
    text = user_input.strip()

    if any(word in text for word in ["종료", "끝내", "그만"]):
        return "🏁"

    if any(word in text for word in ["인터뷰", "신문", "진술", "물어봐"]):
        return "👤"

    if any(word in text for word in ["조사", "증거", "현장", "객실", "확인"]):
        return "🔍"

    if any(word in text for word in ["범인", "진범", "범행"]):
        return "⚠️"

    return "📁"

def stream_text(text, animate=True, delay=0.02):

    # 과거에 이미 출력된 메시지는 즉시 표시
    if not animate:
        st.markdown(text)
        return text

    # 새로 생성된 메시지는 타이핑처럼 표시
    placeholder = st.markdown("")
    displayed_text = ""

    for char in text:
        displayed_text += char
        placeholder.markdown(displayed_text)
        time.sleep(delay)

    return displayed_text


def render_investigation_sidebar():
    """조사 화면에 스포일러 없는 진행 정보를 표시한다."""
    summary = get_sidebar_summary()
    status_icons = {
        "completed": "●",
        "in_progress": "◐",
        "not_started": "○",
    }

    with st.sidebar:
        st.markdown("## 🔎 수사 기록")
        st.caption("현재 장")
        st.markdown(
            f"**{summary['current_stage']}**"
        )
        st.progress(summary["chapter_number"] / 6)
        st.caption(f"전체 6장 중 {summary['chapter_number']}장")

        st.metric(
            "확보한 기록",
            f"{summary['completed_count']}건"
        )

        st.markdown("### 조사 분야")

        for category, status in summary["categories"].items():
            icon = status_icons[status]
            st.write(f"{icon} {category}")

        st.caption("● 확인 완료 · ◐ 조사 중 · ○ 단서 부족")

        if summary["recent_records"]:
            st.markdown("### 최근 확보")

            for record in reversed(
                summary["recent_records"]
            ):
                st.write(f"- {record}")

        with st.expander("사건 수첩"):
            if summary["all_records"]:
                for index, record in enumerate(
                    summary["all_records"],
                    start=1
                ):
                    st.write(f"{index}. {record}")
            else:
                st.write(
                    "아직 확보한 조사 기록이 없습니다."
                )

        st.divider()
        st.markdown(
            "### 💡 남은 힌트: "
            f"{summary['remaining_hints']} / "
            f"{summary['max_hints']}"
        )

        if "confirm_hint" not in st.session_state:
            st.session_state.confirm_hint = False

        if (
            summary["remaining_hints"] > 0
            and not st.session_state.confirm_hint
        ):
            if st.button(
                "힌트 요청",
                use_container_width=True
            ):
                st.session_state.confirm_hint = True
                st.rerun()

        elif summary["remaining_hints"] > 0:
            st.warning(
                "힌트를 사용하면 남은 횟수가 "
                "1회 차감됩니다."
            )

            use_column, cancel_column = st.columns(2)

            with use_column:
                if st.button(
                    "힌트 사용",
                    type="primary",
                    use_container_width=True
                ):
                    use_hint()
                    st.session_state.confirm_hint = False
                    st.rerun()

            with cancel_column:
                if st.button(
                    "취소",
                    use_container_width=True
                ):
                    st.session_state.confirm_hint = False
                    st.rerun()

        else:
            st.caption(
                "이번 게임에서 사용할 수 있는 "
                "힌트를 모두 사용했습니다."
            )

        if summary["last_hint"]:
            st.info(summary["last_hint"])

# 현재 화면을 기억하는 상태
if "screen" not in st.session_state:
    st.session_state.screen = "start"

# 이 브라우저 세션의 조사 상태를 game_state와 연결
bind_session_state(st.session_state)

# 시작 화면
if st.session_state.screen == "start":
    st.markdown(
        """
        <style>
        .start-title {
            text-align: center;
            font-size: 3rem;
            font-weight: 700;
            margin-top: 12vh;
            margin-bottom: 0.5rem;
        }
        .start-subtitle {
            text-align: center;
            color: #9aa4b2;
            line-height: 1.8;
            margin-bottom: 2rem;
        }
        </style>

        <div class="start-title">🔎 해성호의 마지막 기록</div>
        <div class="start-subtitle">
            폭풍 속 크루즈에서 발생한 의문의 살인사건.<br>
            8년 전 해성호 사고의 기록이 다시 모습을 드러냅니다.
        </div>
        """,
        unsafe_allow_html=True
    )

    left, center, right = st.columns([1, 1.4, 1])

    with center:
        if st.button(
            "새 게임 시작",
            type="primary",
            use_container_width=True
        ):
            reset_game_state(st.session_state)
            st.session_state.messages = []
            st.session_state.intro_played = False
            st.session_state.game_phase = "investigation"
            st.session_state.selected_suspect = None
            st.session_state.confirm_hint = False
            st.session_state.screen = "prologue"
            st.rerun()

        with st.expander("게임 방법"):
            st.markdown(
                """
                - 기록관 에코에게 사건에 관해 자유롭게 질문할 수 있습니다.
                - 새로운 조사를 요청하면 관련 기록과 증거를 확보할 수 있습니다.
                - **조사 현황**을 입력하면 현재까지의 진행 상황을 확인할 수 있습니다.
                - 충분한 증거를 모은 뒤 **범인 지목**으로 최종 추리를 시작하세요.
                """
            )

    st.stop()

# 프롤로그 화면
if st.session_state.screen == "prologue":
    st.markdown("## 프롤로그")
    st.caption("7월 20일 밤 · 현대 대형 크루즈선")

    st.markdown(
        """
        창밖의 바다는 거칠게 흔들리고 있었습니다.

        선상 산업행사가 끝나갈 무렵, 한 승객이 자신의 객실에서
        숨진 채 발견됩니다. 피해자는 **최종인, 62세**.

        처음에는 갑작스러운 죽음처럼 보였지만,
        객실에 남은 기록들은 서로 다른 시간을 가리키고 있었습니다.

        그리고 그의 이름 뒤에는 8년 동안 묻혀 있던
        **해성호 사고**의 기록이 남아 있었습니다.

        외부 수사기관이 도착하기 전까지,
        선내 보안팀은 휴가 중이던 당신에게
        현장 보존과 초기 조사를 요청합니다.
        """
    )

    st.divider()

    st.info(
        "기록관 에코가 확보된 기록을 정리하고 "
        "당신의 조사를 보조합니다."
    )

    back_column, start_column = st.columns(2)

    with back_column:
        if st.button("처음으로", use_container_width=True):
            st.session_state.screen = "start"
            st.rerun()

    with start_column:
        if st.button(
            "조사 시작",
            type="primary",
            use_container_width=True
        ):
            st.session_state.screen = "game"
            st.rerun()

    st.stop()

st.title("해성호의 마지막 기록")
st.caption("기록관 에코와 함께 사건을 조사하십시오.")
render_investigation_sidebar()

# 최초 실행 시 시작 메시지 저장
# 최초 실행 시 대화 기록 생성
if "messages" not in st.session_state:
    st.session_state.messages = []

# 시작 메시지를 이미 출력했는지 확인
if "intro_played" not in st.session_state:
    st.session_state.intro_played = False
if "game_phase" not in st.session_state:
    st.session_state.game_phase = "investigation"

if "selected_suspect" not in st.session_state:
    st.session_state.selected_suspect = None

# 기존 대화 출력
for message in st.session_state.messages:

    if message["role"] == "user":
        with st.chat_message("user", avatar="🕵️"):
            st.write(message["content"])

    else:
        with st.chat_message("assistant", avatar="🤖"):
            icon = message.get("icon", "📁")
            st.markdown(f"### {icon} 기록관 에코")
            stream_text(message["content"], animate=False)
            
# 최초 실행 시 시작 메시지를 스트리밍으로 출력
if not st.session_state.intro_played:
    intro = get_start_message()

    with st.chat_message("assistant", avatar="🤖"):
        st.markdown("### 📖 기록관 에코")
        stream_text(intro, animate=True)

    st.session_state.messages.append({
        "role": "assistant",
        "content": intro,
        "icon": "📖"
    })

    st.session_state.intro_played = True
    st.rerun()

# 사용자 입력
user_input = st.chat_input("조사 내용이나 질문을 입력하세요.")

if user_input:
    chapter_before = get_story_chapter()["number"]

    # 사용자 메시지 저장
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # 사용자 메시지 즉시 출력
    with st.chat_message("user", avatar="🕵️"):
        st.write(user_input)
    # 1. 평소 조사 상태
    if st.session_state.game_phase == "investigation":

        accusation_commands = [
            "범인 지목",
            "범인지목",
            "범인을 지목하겠다",
            "범인을 지목할게",
            "범인을 지목한다",
            "최종 추리"
        ]

        status_commands = [
            "조사 현황",
            "조사현황",
            "수사 현황",
            "수사현황",
            "현황"
        ]

        if user_input.strip() in accusation_commands:
            accusation_block = get_chapter_action_block(
                "accusation"
            )

            if accusation_block:
                answer = accusation_block
            else:
                answer = """
최종 추리를 시작합니다.

범인으로 지목할 인물의 이름을 입력하십시오.

- 김동율
- 김현준
- 강원모
- 박소영

지목을 중단하려면 **지목 취소**라고 입력하십시오.
"""
                st.session_state.game_phase = "selecting_suspect"
        elif user_input.strip() in status_commands:
            answer = get_investigation_status()

        else:
            answer = process_user_input(user_input)

    # 2. 범인 선택 상태
    elif st.session_state.game_phase == "selecting_suspect":

        suspects = ["김동율", "김현준", "강원모", "박소영"]

        if user_input.strip() in ["취소", "지목 취소"]:
            answer = "범인 지목을 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.game_phase = "investigation"

        elif user_input.strip() in suspects:
            accused = user_input.strip()
            st.session_state.selected_suspect = accused
            st.session_state.game_phase = "confirming"

            answer = f"""
━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ 최종 추리

현재 확보된 모든 증거를 바탕으로
최종 판정을 진행합니다.

이후에는 추가 조사를 진행할 수 없습니다.

**{accused}**을 범인으로 최종 지목하시겠습니까?

확정하려면 **예**
취소하려면 **아니오**

━━━━━━━━━━━━━━━━━━━━━━
"""

        else:
            answer = """
등록되지 않은 인물입니다.

김동율, 김현준, 강원모, 박소영 중 한 명을 입력하십시오.
"""

    # 3. 최종 확인 상태
    elif st.session_state.game_phase == "confirming":

        if user_input.strip().lower() in ["예", "네", "ㅇ", "yes", "y"]:

            with st.spinner("🔎 확보된 증거를 최종 분석하는 중입니다..."):
                time.sleep(2)

            accused = st.session_state.selected_suspect
            answer = judge_accusation(accused)
            st.session_state.game_phase = "finished"

        elif user_input.strip() in ["아니오", "아니요", "취소", "ㄴ"]:
            answer = "범인 지목을 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.selected_suspect = None
            st.session_state.game_phase = "investigation"

        else:
            answer = "최종 지목하려면 **예**, 취소하려면 **아니오**라고 입력하십시오."

    # 4. 게임 종료 상태
    else:
        answer = """
이미 사건의 최종 판정이 완료되었습니다.

새로운 게임을 시작하려면 앱을 다시 실행하십시오.
"""
    chapter_after = get_story_chapter()["number"]
    if chapter_after > chapter_before:
        answer += get_chapter_transition_message(chapter_after)

    if st.session_state.game_phase == "finished":
        answer_icon = "🏁"

    elif user_input.strip() in [
        "조사 현황",
        "조사현황",
        "수사 현황",
        "수사현황",
        "현황"
    ]:
        answer_icon = "📋"

    else:
        answer_icon = get_answer_icon(user_input)    

    with st.chat_message("assistant", avatar="🤖"):
        st.markdown(f"### {answer_icon} 기록관 에코")
        stream_text(answer, animate=True)

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "icon": answer_icon
    })

    st.rerun()
