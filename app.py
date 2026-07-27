import streamlit as st
import time
from game import (
    process_user_input,
    get_start_message,
    judge_accusation,
    get_investigation_status
)

st.set_page_config(
    page_title="해성호의 마지막 기록",
    page_icon="🔎"
)

st.title("해성호의 마지막 기록")
st.caption("기록관 에코와 함께 사건을 조사하십시오.")


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
    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

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