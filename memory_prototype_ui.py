"""기억 복원 수직 시제품의 Streamlit 화면."""

from __future__ import annotations

import streamlit as st

from memory_echo import analyze_hypothesis
from memory_reconstruction import (
    CLAIMS, EVIDENCE, FORENSIC_REQUESTS, INITIAL_HYPOTHESES,
    RELATIONS, MemoryState,
    can_submit_reconstruction, connect_workspace, create_memory_state,
    set_workspace, start_memory_scene, submit_reconstruction,
    get_adaptive_hint, get_memory_phase, record_initial_hypothesis,
    request_message_forensics,
)
from memory_story import INITIAL_HYPOTHESIS_RESPONSES, PLAYER_GUIDES, STORY_BEATS


STATE_KEY = "memory_prototype_state"

RESETTABLE_WIDGET_KEYS = (
    "memory_workspace_selector",
    "memory_echo_last",
    "memory_echo_input",
    "memory_initial_hypothesis",
    "memory_forensic_request",
    "memory_relation_connect_message",
    "memory_relation_connect_window",
    "memory_final_alive",
    "memory_final_message",
    "memory_final_conclusion",
)

RELATION_OPTION_ORDER = {
    "connect_message": (
        "SAME_EVENT", "ONE_PROVES_OTHER", "RECEIPT_VS_SURVIVAL",
        "LAST_SEEN_VS_DISCOVERY",
    ),
    "connect_window": (
        "ONE_PROVES_OTHER", "SAME_EVENT", "LAST_SEEN_VS_DISCOVERY",
        "RECEIPT_VS_SURVIVAL",
    ),
}


def _load_state() -> MemoryState:
    payload = st.session_state.get(STATE_KEY)
    if not payload:
        return create_memory_state()
    try:
        return MemoryState.from_json(payload)
    except (TypeError, ValueError):
        return create_memory_state()


def _save_state(state: MemoryState) -> None:
    st.session_state[STATE_KEY] = state.to_json()


def render_memory_prototype(show_back_button: bool = True) -> None:
    if st.session_state.pop("memory_prototype_reset_pending", False):
        for key in RESETTABLE_WIDGET_KEYS:
            st.session_state.pop(key, None)
    state = _load_state()
    phase = get_memory_phase(state)
    header, back = st.columns([5, 1])
    with header:
        st.caption(
            "DEVELOPER PREVIEW · MEMORY RECONSTRUCTION"
            if show_back_button
            else "RECONSTRUCTION 01 · ACTIVE MEMORY"
        )
        st.title("21시 15분 — 죽은 사람이 보낸 메시지")
    with back:
        if show_back_button and st.button("조사로 돌아가기", use_container_width=True):
            st.session_state.main_view = "chat"
            st.rerun()

    _render_story_beat(phase)
    _render_player_guide(phase)
    connection_flash = st.session_state.pop("memory_connection_flash", None)
    if connection_flash:
        (st.success if connection_flash["success"] else st.error)(connection_flash["message"])
        if not connection_flash["success"]:
            hint = get_adaptive_hint(state, phase)
            if hint:
                st.info(f"에코 보조 분석 · {hint}")
    if phase == "briefing":
        st.info(
            "현재 확보된 자료를 바탕으로 에코가 구성한 장면이며 "
            "확정된 영상 기록이 아닙니다."
        )
        if st.button("기억 장면에 진입", type="primary", use_container_width=True):
            start_memory_scene(state)
            _save_state(state)
            st.rerun()
    else:
        _render_progress(phase)
        _render_timeline(state)

    if phase == "inspect_message":
        _render_message_investigation(state)
    elif phase == "initial_hypothesis":
        _render_initial_hypothesis(state)
    elif phase in ("connect_message", "connect_window"):
        if phase == "connect_window":
            _render_message_hypothesis_result()
        _render_connection(state, phase)
    elif phase == "final_reconstruction":
        _render_final(state)
    elif phase == "complete":
        initial_label = INITIAL_HYPOTHESES.get(
            state.initial_hypothesis_id,
            "초기 판단 없음",
        )
        st.markdown("### 당신의 판단은 어떻게 바뀌었는가")
        left, right = st.columns(2)
        with left:
            with st.container(border=True):
                st.caption("복원 전 판단")
                st.write(initial_label)
        with right:
            with st.container(border=True):
                st.caption("기록으로 확정된 결론")
                st.write("21시 15분에는 예약된 전송만 실행됐다. 해당 시각의 생존 여부는 증명되지 않는다.")
        st.success(
            "21시 15분이라는 잘못된 생존 전제가 제거됐다. "
            "이제 19시 55분 이후의 실제 범행 가능창을 다시 조사할 수 있다."
        )
        if not show_back_button and st.button("첫 복원 기록 닫기", type="primary", use_container_width=True):
            st.session_state.memory_screen = "chapter_complete"
            st.rerun()

    if phase != "briefing":
        with st.expander("기록 보관함 · 확보 자료와 주장"):
            _render_archive(state, show_ids=show_back_button)
        with st.expander("에코에게 현재 가설 검토 요청"):
            _render_echo(state, show_ids=show_back_button)

    if show_back_button:
        with st.expander("개발자 상태"):
            st.code(state.to_json(), language="json")
            if st.button("시제품만 초기화", key="reset_memory_prototype"):
                st.session_state[STATE_KEY] = create_memory_state().to_json()
                st.session_state.memory_prototype_reset_pending = True
                st.rerun()


def _render_story_beat(phase: str) -> None:
    beat = STORY_BEATS[phase]
    st.caption(f"{beat['number']} · MEMORY SCENE")
    st.subheader(beat["title"])
    for speaker, line in beat["lines"]:
        with st.chat_message("assistant", avatar="🗃️" if speaker == "에코" else "👤"):
            st.markdown(f"**{speaker}**")
            st.write(line)
    st.info(f"현재 목표 · {beat['objective']}")


def _render_player_guide(phase: str) -> None:
    guide = PLAYER_GUIDES.get(phase)
    if not guide:
        return
    with st.container(border=True):
        st.caption(f"처음 하는 조사관 안내 · {guide['step']}")
        st.markdown(f"**지금 할 일**  \n{guide['action']}")
        st.caption(f"왜 하는가 · {guide['reason']}")
        st.caption(f"진행 규칙 · {guide['rule']}")


def _render_progress(phase: str) -> None:
    order = ("initial_hypothesis", "inspect_message", "connect_message", "connect_window", "final_reconstruction", "complete")
    step = min(order.index(phase) + 1, 5)
    st.progress(step / 5, text=f"기억 복원 진행 · {step}/5")


def _render_timeline(state: MemoryState) -> None:
    st.subheader("확인된 시간축")
    columns = st.columns(4)
    timeline = (
        (
            "19:55",
            "마지막 생존 목격"
            if "CLAIM_CONFIRMED_WINDOW" in state.unlocked_claim_ids
            else "서민재와 대화",
        ),
        (
            "21:15",
            "자동 전송 실행"
            if "CLAIM_MESSAGE_NOT_SURVIVAL" in state.unlocked_claim_ids
            else "업무 메시지 수신",
        ),
        ("22:30", "업무 불참"),
        ("23:20", "사망 공식 확인"),
    )
    for column, (time, label) in zip(columns, timeline):
        with column:
            st.metric(time, label)
    if "CLAIM_MESSAGE_NOT_SURVIVAL" in state.unlocked_claim_ids:
        st.warning("21:15 생존 전제 제거 · 메시지 수신 시각을 생존 하한선으로 사용할 수 없습니다.")


def _render_evidence_cards(evidence_ids) -> None:
    columns = st.columns(len(evidence_ids))
    for column, evidence_id in zip(columns, evidence_ids):
        item = EVIDENCE[evidence_id]
        with column:
            with st.container(border=True):
                st.caption(f"{item.source_type} · {item.time}")
                st.markdown(f"#### {item.title}")
                st.write(item.body)
                st.caption(f"관련 인물 · {', '.join(item.people)}")


def _render_message_investigation(state: MemoryState) -> None:
    if "MESSAGE_2115" not in state.workspace_ids:
        set_workspace(state, ["MESSAGE_2115"])
        _save_state(state)
    selected_hypothesis = INITIAL_HYPOTHESES[state.initial_hypothesis_id]
    st.caption("당신의 초기 가설")
    st.markdown(f"> {selected_hypothesis}")
    st.info(INITIAL_HYPOTHESIS_RESPONSES[state.initial_hypothesis_id])
    st.subheader("21시 15분 수신 기록")
    _render_evidence_cards(("MESSAGE_2115",))
    st.warning(
        "이 화면은 발신 계정과 수신 시각만 보여줍니다. "
        "메시지가 언제 작성됐고 어떤 방식으로 실행됐는지는 기록되어 있지 않습니다."
    )
    st.markdown("### 어떤 기록을 먼저 요청할 것인가")
    request_id = st.radio(
        "작성 시점과 실행 방식을 확인할 수 있는 기록을 선택하세요.",
        options=list(FORENSIC_REQUESTS),
        format_func=lambda item: FORENSIC_REQUESTS[item]["label"],
        index=None,
        key="memory_forensic_request",
    )
    if st.button(
        "포렌식 기록 요청",
        type="primary",
        disabled=request_id is None,
        use_container_width=True,
    ):
        result = request_message_forensics(state, request_id)
        _save_state(state)
        if result["success"]:
            set_workspace(state, ["MESSAGE_2115", "MESSAGE_METADATA"])
            _save_state(state)
            st.rerun()
        else:
            st.session_state.memory_forensic_flash = result["message"]
            st.rerun()
    forensic_flash = st.session_state.pop("memory_forensic_flash", None)
    if forensic_flash:
        st.warning(forensic_flash)
        hint = get_adaptive_hint(state, "inspect_message")
        if hint:
            st.info(f"에코 보조 분석 · {hint}")


def _render_initial_hypothesis(state: MemoryState) -> None:
    st.subheader("초기 판단 기록")
    st.write(
        "박소영의 휴대전화에 표시된 것은 발신자, 내용, 수신 시각입니다. "
        "이 기록만 놓고 볼 때 가장 타당한 판단을 선택하세요."
    )
    selected = st.radio(
        "21시 15분 메시지는 무엇을 의미합니까?",
        options=list(INITIAL_HYPOTHESES),
        format_func=lambda item: INITIAL_HYPOTHESES[item],
        index=None,
        key="memory_initial_hypothesis",
    )
    if st.button(
        "이 판단으로 조사 시작",
        type="primary",
        disabled=selected is None,
        use_container_width=True,
    ):
        record_initial_hypothesis(state, selected)
        _save_state(state)
        st.rerun()


def _render_connection(state: MemoryState, phase: str) -> None:
    expected = (
        ["MESSAGE_2115", "MESSAGE_METADATA"]
        if phase == "connect_message"
        else ["WITNESS_1955", "DISCOVERY_2320"]
    )
    if set(state.workspace_ids) != set(expected):
        set_workspace(state, expected)
        _save_state(state)
    st.subheader("재구성 작업대")
    _render_evidence_cards(expected)
    relation = st.selectbox(
        "두 자료 사이에서 가장 중요한 관계는 무엇입니까?",
        options=RELATION_OPTION_ORDER[phase],
        format_func=lambda item: RELATIONS[item],
        index=None,
        key=f"memory_relation_{phase}",
    )
    if st.button("기억 연결", type="primary", disabled=relation is None, use_container_width=True):
        result = connect_workspace(state, relation)
        if result["success"] and phase == "connect_message":
            set_workspace(state, ["WITNESS_1955", "DISCOVERY_2320"])
        _save_state(state)
        st.session_state.memory_connection_flash = result
        st.rerun()


def _render_message_hypothesis_result() -> None:
    st.markdown("### 21시 15분 가설 대조 결과")
    columns = st.columns(3)
    results = (
        ("실시간 작성", "배제", "21시 15분에는 사용자 작성 이벤트가 없었다."),
        ("생전 예약발송", "지지", "이전 기기 세션에서 작성과 예약 등록이 확인됐다."),
        ("제3자 전송", "배제", "예약 이후 수정이나 외부 접속 흔적이 없었다."),
    )
    for column, (label, status, reason) in zip(columns, results):
        with column:
            with st.container(border=True):
                st.caption(label)
                st.markdown(f"**{status}**")
                st.write(reason)


def _render_archive(state: MemoryState, show_ids: bool = False) -> None:
    st.markdown("#### 확보한 자료")
    for evidence_id in state.unlocked_evidence_ids:
        item = EVIDENCE[evidence_id]
        prefix = f"`{evidence_id}` · " if show_ids else ""
        st.markdown(f"- {prefix}{item.title}")
    st.markdown("#### 확정한 주장")
    if not state.unlocked_claim_ids:
        st.caption("아직 확정한 주장이 없습니다.")
    for claim_id in state.unlocked_claim_ids:
        st.markdown(f"- **{CLAIMS[claim_id].title}** — {CLAIMS[claim_id].explanation}")


def _render_echo(state: MemoryState, show_ids: bool = False) -> None:
    st.caption("자연어는 선택한 자료에 대한 가설 검토에만 사용되며 게임 상태를 변경하지 않습니다.")
    hypothesis = st.text_area("가설 또는 질문", key="memory_echo_input")
    if st.button("선택 자료로 검토", disabled=not state.workspace_ids):
        result = analyze_hypothesis(state, hypothesis)
        st.session_state.memory_echo_last = result
    result = st.session_state.get("memory_echo_last")
    if result:
        st.write(result["summary"])
        sources = [
            item if show_ids else EVIDENCE[item].title
            for item in result["source_ids"]
            if item in EVIDENCE
        ]
        unknown = [
            item if show_ids else CLAIMS[item].title
            for item in result["unknown_claim_ids"]
            if item in CLAIMS
        ]
        st.caption("근거 기록 · " + (", ".join(sources) or "없음"))
        st.caption("판단할 수 없는 주장 · " + (", ".join(unknown) or "없음"))


def _render_final(state: MemoryState) -> None:
    if not can_submit_reconstruction(state):
        st.warning("두 필수 연결을 완성하면 마지막 장면을 재구성할 수 있습니다.")
        return
    with st.form("memory_final_reconstruction"):
        alive = st.radio(
            "1. 현재 기록에서 마지막으로 직접 확인된 생존 시각은?",
            ("21:15", "19:55", "22:30"), index=None, key="memory_final_alive",
        )
        message = st.radio(
            "2. 21시 15분 메시지가 증명하는 것은?",
            ("ALIVE_AT_2115", "CULPRIT_SENT_MESSAGE", "AUTO_SENT_AT_2115"),
            format_func=lambda item: {
                "AUTO_SENT_AT_2115": "예약 메시지가 해당 시각 자동 전송됨",
                "ALIVE_AT_2115": "최종인이 해당 시각 살아 있었음",
                "CULPRIT_SENT_MESSAGE": "범인이 사후에 메시지를 전송함",
            }[item], index=None, key="memory_final_message",
        )
        conclusion = st.radio(
            "3. 현재 가능한 결론은?",
            ("DEATH_TIME_REQUIRES_MORE_RECORDS", "CULPRIT_IDENTIFIED", "DIED_AT_2115"),
            format_func=lambda item: {
                "DEATH_TIME_REQUIRES_MORE_RECORDS": "21:15는 생존 하한선이 아니며 정확한 사망시각에는 추가 기록이 필요함",
                "DIED_AT_2115": "최종인은 정확히 21:15에 사망함",
                "CULPRIT_IDENTIFIED": "현재 기록만으로 범인이 확정됨",
            }[item], index=None, key="memory_final_conclusion",
        )
        submitted = st.form_submit_button("재구성 제출", type="primary")
    if submitted:
        result = submit_reconstruction(state, {
            "last_confirmed_alive": alive,
            "message_proves": message,
            "possible_conclusion": conclusion,
        })
        _save_state(state)
        if result["solved"]:
            st.rerun()
        else:
            st.error("일부 판단이 확보한 기록의 범위를 벗어났습니다. 진행 상태는 유지됩니다.")
            for message in result["feedback"]:
                st.warning(message)
