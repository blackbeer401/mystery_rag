"""《기억의 증언》 독립 게임 진입점.

실행: streamlit run memory_app.py
"""

from pathlib import Path

import streamlit as st

from memory_prototype_ui import render_memory_prototype
from memory_reconstruction import create_memory_state
from memory_story import (
    CASE_TITLE, ECHO_INTRO_LINES, ECHO_PROFILE, GAME_TITLE,
    PLAYER_ROLE, PROLOGUE_BEATS, PROLOGUE_DISCOVERY_LINES,
)


ROOT = Path(__file__).resolve().parent
TITLE_IMAGE = ROOT / "assets" / "chapters" / "title_hero.webp"
PROLOGUE_IMAGE = ROOT / "assets" / "chapters" / "prologue.webp"

st.set_page_config(page_title=GAME_TITLE, page_icon="◈", layout="wide")
st.markdown(
    """
    <style>
    :root { --ink:#0c0f13; --panel:#171c23; --line:#394351; --paper:#e5dfd2; --gold:#c8a261; --muted:#929cab; }
    .stApp { background:radial-gradient(circle at 50% -10%,#242b35 0,#10141a 42rem); color:var(--paper); }
    [data-testid="stHeader"] { background:transparent; }
    .block-container { max-width:1050px; padding-top:4.75rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--paper)!important; letter-spacing:.02em; }
    [data-testid="stSidebar"] { display:none; }
    .memory-kicker { color:var(--gold); font:600 .78rem monospace; letter-spacing:.18em; }
    .memory-title { font-size:clamp(2.4rem,7vw,3.5rem); font-weight:800; line-height:1.12; margin:.5rem 0; }
    .memory-subtitle { color:var(--muted); font-size:1.05rem; margin-bottom:1.5rem; }
    .scene-log { border-left:2px solid var(--gold); padding:.3rem 0 .3rem 1.2rem; margin:1rem 0; }
    .scene-time { color:var(--gold); font:600 .8rem monospace; letter-spacing:.1em; }
    .scene-text { color:var(--paper); margin:.25rem 0 1.25rem; }
    .role-card { border:1px solid var(--line); background:rgba(23,28,35,.86); padding:1.25rem; margin:1rem 0; }
    .stButton > button { border-radius:2px; min-height:3rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _set_screen(screen: str) -> None:
    st.session_state.memory_screen = screen
    st.rerun()


def _reset_new_game() -> None:
    st.session_state.memory_prototype_state = create_memory_state().to_json()
    for key in tuple(st.session_state):
        if key.startswith("memory_relation_") or key in {
            "memory_echo_last", "memory_echo_input", "memory_connection_flash",
        }:
            del st.session_state[key]
    st.session_state.memory_screen = "prologue"
    st.rerun()


def _render_title() -> None:
    st.markdown('<div class="memory-kicker">A MEMORY RECONSTRUCTION MYSTERY</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="memory-title">{GAME_TITLE}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="memory-subtitle">CASE 01 · {CASE_TITLE}</div>', unsafe_allow_html=True)
    st.image(TITLE_IMAGE, use_container_width=True)
    st.caption("사람의 기억과 기계의 기록 사이에서, 사라진 사건의 연결망을 복원하십시오.")
    left, center, right = st.columns([1, 1.5, 1])
    with center:
        if st.button("새 기억 기록 열기", type="primary", use_container_width=True):
            _reset_new_game()
    with st.expander("이 게임에 대하여"):
        st.write(
            "등장인물의 기억과 객관 기록을 비교해 사건을 재구성하는 수사극입니다. "
            "AI 기록관 에코는 가설을 검토하지만 증거 해금이나 정답을 결정하지 않습니다."
        )


def _render_prologue() -> None:
    st.markdown('<div class="memory-kicker">PROLOGUE · JULY 20</div>', unsafe_allow_html=True)
    st.title("객실이 열린 밤")
    st.image(PROLOGUE_IMAGE, use_container_width=True)
    st.write(
        "폭풍이 선체를 두드리던 밤, 선내 보안팀의 호출이 객실 복도를 깨웠습니다. "
        "문 안쪽에는 응답이 없었고 외부 수사팀은 아직 승선할 수 없었습니다."
    )
    logs = "".join(
        f'<div class="scene-log"><div class="scene-time">{beat["time"]} · {beat["label"]}</div>'
        f'<div class="scene-text">{beat["text"]}</div></div>'
        for beat in PROLOGUE_BEATS
    )
    st.markdown(logs, unsafe_allow_html=True)
    for speaker, line in PROLOGUE_DISCOVERY_LINES:
        with st.chat_message("assistant", avatar="👤"):
            st.markdown(f"**{speaker}**")
            st.write(line)
    st.markdown("### 현장에 남은 세 가지 의문")
    message_col, room_col, usb_col = st.columns(3)
    with message_col:
        with st.container(border=True):
            st.caption("DIGITAL TRACE")
            st.markdown("**21:15 메시지**")
            st.write("사망이 확인되기 두 시간 전, 피해자 명의의 정상적인 업무 메시지가 도착했다.")
    with room_col:
        with st.container(border=True):
            st.caption("CABIN 0712")
            st.markdown("**닫힌 객실**")
            st.write("문은 닫혀 있었고 외부에서 강제로 침입한 흔적은 확인되지 않았다.")
    with usb_col:
        with st.container(border=True):
            st.caption("MISSING ITEM")
            st.markdown("**사라진 USB**")
            st.write("최종인이 과거 사건 자료를 정리하던 저장장치가 현장에서 보이지 않는다.")
    st.warning(
        "메시지가 도착한 시각과 사람이 살아 있던 시각은 같은 것인가? "
        "첫 복원은 이 질문에서 시작됩니다."
    )
    if st.button("선내 기록관에 접속", type="primary", use_container_width=True):
        _set_screen("echo_intro")


def _render_echo_intro() -> None:
    st.markdown('<div class="memory-kicker">ARCHIVE SYSTEM · ECHO ONLINE</div>', unsafe_allow_html=True)
    st.title("기록은 남았지만, 연결은 사라졌다")
    for speaker, line in ECHO_INTRO_LINES:
        with st.chat_message("assistant", avatar="🗃️"):
            st.markdown(f"**{speaker}**")
            st.write(line)
    st.markdown(
        f'<div class="role-card"><div class="memory-kicker">YOUR ROLE</div>'
        f'<h3>초동 기록 재구성 조사관</h3><p>{PLAYER_ROLE}</p></div>',
        unsafe_allow_html=True,
    )
    st.info(ECHO_PROFILE["principle"])
    st.markdown("**복원 원칙**")
    st.markdown(
        "1. 장면에서 중요한 주장을 확인합니다.\n"
        "2. 사람의 기억과 객관 기록을 비교합니다.\n"
        "3. 자료가 증명하는 것과 증명하지 못하는 것을 구분합니다.\n"
        "4. 연결과 진행은 기록 규칙으로만 확정됩니다."
    )
    if st.button("첫 번째 기억 장면 복원", type="primary", use_container_width=True):
        _set_screen("episode_2115")


def _render_chapter_complete() -> None:
    st.markdown('<div class="memory-kicker">RECONSTRUCTION 01 · COMPLETE</div>', unsafe_allow_html=True)
    st.title("잘못된 시간이 지워졌다")
    st.success(
        "21시 15분은 최종인의 생존 시각이 아니었다. 현재 확인된 마지막 생존은 19시 55분이다."
    )
    st.write(
        "메시지가 만든 잘못된 전제가 제거되면서 조사해야 할 시간이 앞으로 이동했습니다. "
        "정확한 사망시각과 범인을 밝히려면 19시 55분 이후의 목격과 출입기록을 복원해야 합니다."
    )
    st.caption("다음 기록 · 마지막으로 본 사람 — 이후 단계에서 제작 예정")
    if st.button("타이틀로 돌아가기", use_container_width=True):
        _set_screen("title")


screen = st.session_state.get("memory_screen", "title")
if screen == "title":
    _render_title()
elif screen == "prologue":
    _render_prologue()
elif screen == "echo_intro":
    _render_echo_intro()
elif screen == "episode_2115":
    render_memory_prototype(show_back_button=False)
elif screen == "chapter_complete":
    _render_chapter_complete()
else:
    st.session_state.memory_screen = "title"
    st.rerun()
