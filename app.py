import streamlit as st
import time
import os
from pathlib import Path
from game import (
    process_user_input,
    get_start_message,
    judge_accusation,
    get_investigation_status,
    get_required_next_action,
)
from game_state import (
    bind_session_state,
    reset_game_state,
    get_sidebar_summary,
    use_hint,
    get_story_chapter,
    get_chapter_transition_message,
    get_chapter_action_block,
    get_chapter_one_coach_message,
    set_tutorial_expected_action,
    get_pending_tutorial_reminder,
    mark_tutorial_event,
    is_chapter_one_ready,
    complete_chapter_one,
    get_investigated,
    get_cabin_observations,
    get_chapter_one_reflection,
    set_chapter_one_reflection,
    is_chapter_two_ready,
    complete_chapter_two,
    get_chapter_two_reflection,
    set_chapter_two_reflection,
    apply_debug_checkpoint,
    get_active_interview,
)

st.set_page_config(
    page_title="해성호의 마지막 기록",
    page_icon="🔎"
)

# 로컬 2장 테스트를 위한 임시 플래그.
# 배포하거나 main 브랜치에 병합하기 전 반드시 False로 바꾼다.
LOCAL_DEBUG_TOOLS_ENABLED = True

st.markdown(
    """
    <style>
    :root {
        --archive-bg: #11130d;
        --archive-panel: #191c13;
        --archive-panel-soft: #202419;
        --archive-line: #4c513c;
        --archive-text: #d6dac2;
        --archive-muted: #969b82;
        --archive-accent: #c4c99e;
        --archive-warning: #b48b63;
    }

    .stApp {
        background:
            radial-gradient(
                circle at 50% 0%,
                rgba(76, 81, 60, 0.14),
                transparent 34rem
            ),
            var(--archive-bg);
        color: var(--archive-text);
    }

    .stApp,
    .stApp p,
    .stApp li,
    .stApp label {
        color: var(--archive-text);
        font-family:
            "Malgun Gothic",
            "Apple SD Gothic Neo",
            sans-serif;
    }

    h1, h2, h3, h4 {
        color: var(--archive-accent) !important;
        letter-spacing: 0.02em;
    }

    [data-testid="stSidebar"] {
        background: #0d0f0a;
        border-right: 1px solid var(--archive-line);
    }

    [data-testid="stSidebar"] [data-testid="stMetric"] {
        background: var(--archive-panel);
        border: 1px solid var(--archive-line);
        padding: 0.7rem 0.9rem;
    }

    [data-testid="stChatMessage"] {
        background: rgba(25, 28, 19, 0.84);
        border: 1px solid var(--archive-line);
        border-radius: 2px;
        margin-bottom: 0.85rem;
        padding: 0.5rem 0.75rem;
    }

    [data-testid="stChatMessage"] img,
    [data-testid="stImage"] img {
        border: 1px solid var(--archive-line);
        filter: contrast(1.04);
    }

    [data-testid="stChatInput"] {
        background: #0d0f0a;
        border: 1px solid var(--archive-line);
        border-radius: 2px;
    }

    [data-testid="stChatInput"] textarea {
        color: var(--archive-text) !important;
        caret-color: var(--archive-accent);
    }

    .stButton > button {
        background: var(--archive-panel) !important;
        color: var(--archive-text) !important;
        border: 1px solid var(--archive-line) !important;
        border-radius: 2px !important;
        transition:
            background 120ms ease,
            border-color 120ms ease;
    }

    .stButton > button * {
        color: inherit !important;
    }

    .stButton > button:hover {
        background: var(--archive-panel-soft) !important;
        border-color: var(--archive-accent) !important;
        color: var(--archive-accent) !important;
    }

    .stButton > button[kind="primary"],
    button[data-testid="stBaseButton-primary"] {
        background: var(--archive-accent) !important;
        color: var(--archive-bg) !important;
        border-color: var(--archive-accent) !important;
        font-weight: 700;
    }

    .stButton > button[kind="primary"] *,
    button[data-testid="stBaseButton-primary"] * {
        color: var(--archive-bg) !important;
    }

    .stButton > button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover {
        background: #d6dac2 !important;
        color: #0d0f0a !important;
        border-color: #d6dac2 !important;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background: rgba(25, 28, 19, 0.72);
        border-color: var(--archive-line) !important;
        border-radius: 2px !important;
    }

    [data-testid="stExpander"] {
        background: var(--archive-panel);
        border-color: var(--archive-line);
        border-radius: 2px;
    }

    [data-testid="stProgressBar"] > div > div {
        background-color: var(--archive-accent);
    }

    hr {
        border-color: var(--archive-line) !important;
    }

    .case-header {
        border-top: 1px solid var(--archive-line);
        border-bottom: 1px solid var(--archive-line);
        margin: 0 0 1rem 0;
        padding: 0.8rem 0.2rem;
    }

    .case-kicker {
        color: var(--archive-muted);
        font-family: Consolas, monospace;
        font-size: 0.76rem;
        letter-spacing: 0.14em;
        margin-bottom: 0.3rem;
    }

    .case-title {
        color: var(--archive-accent);
        font-size: 1.7rem;
        font-weight: 700;
        line-height: 1.25;
    }

    .case-subtitle {
        color: var(--archive-muted);
        font-size: 0.88rem;
        margin-top: 0.3rem;
    }

    .evidence-card-header {
        background:
            linear-gradient(
                90deg,
                rgba(196, 201, 158, 0.16),
                rgba(196, 201, 158, 0.03)
            );
        border-left: 3px solid var(--archive-accent);
        margin-bottom: 0.8rem;
        padding: 0.7rem 0.9rem;
    }

    .evidence-card-kicker {
        color: var(--archive-warning);
        font-family: Consolas, monospace;
        font-size: 0.72rem;
        font-weight: 700;
        letter-spacing: 0.14em;
    }

    .evidence-card-title {
        color: var(--archive-accent);
        font-size: 1.18rem;
        font-weight: 700;
        margin-top: 0.18rem;
    }

    .evidence-card-footer {
        border-top: 1px solid var(--archive-line);
        color: var(--archive-muted);
        font-family: Consolas, monospace;
        font-size: 0.75rem;
        letter-spacing: 0.06em;
        line-height: 1.55;
        margin-top: 0.9rem;
        margin-bottom: 0.55rem;
        overflow-wrap: anywhere;
        padding: 0.65rem 0.15rem 0.4rem 0.15rem;
    }

    .start-title {
        color: var(--archive-accent);
    }

    .title-screen {
        border-bottom: 1px solid var(--archive-line);
        border-top: 1px solid var(--archive-line);
        margin: 0.5rem 0 1rem 0;
        padding: 1.2rem 0.4rem 1rem 0.4rem;
        text-align: center;
    }

    .title-screen-kicker {
        color: var(--archive-warning);
        font-family: Consolas, monospace;
        font-size: 0.76rem;
        letter-spacing: 0.2em;
        margin-bottom: 0.65rem;
    }

    .title-screen-name {
        color: var(--archive-accent);
        font-size: clamp(2.1rem, 6vw, 4.2rem);
        font-weight: 700;
        letter-spacing: -0.03em;
        line-height: 1.08;
    }

    .title-screen-subtitle {
        color: var(--archive-muted);
        font-size: 0.95rem;
        letter-spacing: 0.08em;
        margin-top: 0.85rem;
    }

    .title-screen-status {
        color: var(--archive-muted);
        font-family: Consolas, monospace;
        font-size: 0.75rem;
        letter-spacing: 0.08em;
        margin: 0.85rem 0 1.1rem 0;
        text-align: center;
    }

    .prologue-log {
        background: rgba(25, 28, 19, 0.78);
        border-left: 3px solid var(--archive-accent);
        margin: 1rem 0;
        padding: 1rem 1.2rem;
    }

    .prologue-log-time {
        color: var(--archive-warning);
        font-family: Consolas, monospace;
        font-size: 0.78rem;
        font-weight: 700;
        letter-spacing: 0.12em;
        margin-top: 0.75rem;
    }

    .prologue-log-text {
        color: var(--archive-text);
        line-height: 1.7;
        margin-top: 0.2rem;
    }

    .start-subtitle,
    [data-testid="stCaptionContainer"] {
        color: var(--archive-muted) !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

CHAPTER_ASSET_DIR = Path("assets") / "chapters"
PROLOGUE_IMAGE = CHAPTER_ASSET_DIR / "prologue.webp"
TITLE_HERO_IMAGE = CHAPTER_ASSET_DIR / "title_hero.webp"
CHAPTER_IMAGES = {
    chapter_number: (
        CHAPTER_ASSET_DIR
        / f"chapter_{chapter_number:02d}_banner.webp"
    )
    for chapter_number in range(1, 7)
}
EVIDENCE_ASSET_DIR = Path("assets") / "evidence"
EVIDENCE_CARDS = {
    "door": {
        "title": "객실 출입문과 잠금장치",
        "image": EVIDENCE_ASSET_DIR / "cabin_door.webp",
        "record": "CABIN / ENTRY",
    },
    "table": {
        "title": "테이블 위 물잔과 약 보관함",
        "image": EVIDENCE_ASSET_DIR / "cabin_table.webp",
        "record": "CABIN / TABLE",
    },
    "floor": {
        "title": "어긋난 의자와 바닥 매트",
        "image": EVIDENCE_ASSET_DIR / "cabin_floor.webp",
        "record": "CABIN / FLOOR",
    },
    "FORENSIC_POSTMORTEM": {
        "title": "피해자 법의학 기록",
        "image": None,
        "record": "FORENSIC / POSTMORTEM",
    },
    "SCENE_DISCOVERY_RECONSTRUCTION": {
        "title": "시신 발견 과정 재구성",
        "image": None,
        "record": "SCENE / DISCOVERY",
    },
}

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


def render_illustrated_message(
    image_path,
    content,
    animate=False,
):
    """장 이미지를 크게 보여주고 축약된 내용을 아래에 배치한다."""
    st.image(
        image_path,
        use_container_width=True,
    )
    stream_text(
        content,
        animate=animate,
        delay=0.01,
    )


def render_evidence_card(
    card,
    content,
    animate=False,
    compact=False,
):
    """새 조사 결과를 일반 대화와 분리된 증거 카드로 표시한다."""
    st.markdown(
        f"""
        <div class="evidence-card-header">
            <div class="evidence-card-kicker">NEW EVIDENCE ACQUIRED</div>
            <div class="evidence-card-title">{card["title"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    image_path = card.get("image")
    has_image = image_path and Path(image_path).exists()

    if compact and has_image:
        image_column, text_column = st.columns(
            [1, 1.35],
            gap="medium",
        )
        with image_column:
            st.image(
                image_path,
                use_container_width=True,
            )
        with text_column:
            stream_text(
                content,
                animate=False,
            )
    else:
        if has_image:
            st.image(
                image_path,
                use_container_width=True,
            )
        stream_text(
            content,
            animate=animate,
            delay=0.01,
        )
    st.markdown(
        f"""
        <div class="evidence-card-footer">
            ARCHIVED · {card["record"]} · 사건 수첩에 보관됨
        </div>
        """,
        unsafe_allow_html=True,
    )


def detect_new_evidence_card(
    investigated_before,
    observations_before,
):
    """방금 입력으로 처음 확보한 기록 또는 객실 관찰을 찾는다."""
    observations_after = get_cabin_observations()
    new_observations = (
        observations_after - observations_before
    )

    for observation_name in ("door", "table", "floor"):
        if observation_name in new_observations:
            return EVIDENCE_CARDS[observation_name]

    investigated_after = get_investigated()
    new_investigations = (
        investigated_after - investigated_before
    )
    for investigation_id in (
        "FORENSIC_POSTMORTEM",
        "SCENE_DISCOVERY_RECONSTRUCTION",
    ):
        if investigation_id in new_investigations:
            return EVIDENCE_CARDS[investigation_id]

    return None


def render_opening_briefing(image_path):
    """1장 이미지 아래에 최초 발견 기록과 인물을 배치한다."""
    st.image(
        image_path,
        use_container_width=True,
    )

    briefing_column, people_column = st.columns(
        2,
        gap="large",
    )

    with briefing_column:
        with st.container(border=True):
            st.markdown(
                """
                #### 23:20 · 비상 개방 기록

                22시 30분의 업무 일정에 나타나지 않은
                **최종인(62세)**.

                반복된 연락에도 응답이 없자 선내 직원과 보안
                담당자가 객실을 비상 개방했습니다.

                문 안쪽에서 최종인이 발견됐습니다.
                **23시 20분은 발견 시각일 뿐입니다.**
                """
            )

    with people_column:
        with st.container(border=True):
            st.markdown(
                """
                #### 기록에 남은 네 사람

                - **김동율** — 8년 전 사건 이후의 원한
                - **김현준** — 피해자와의 최근 업무 충돌
                - **강원모** — 해성호 사고 관련자
                - **박소영** — 마지막 업무 약속과 신고
                """
            )

    st.caption(
        "문이 열리기 전, 객실 안에서는 무슨 일이 있었을까요? "
        "현장에 남은 사실부터 확인하십시오."
    )


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

        if summary["chapter_number"] == 1:
            st.markdown("### 1장 · 객실 세부 조사")
            st.progress(
                summary["cabin_observation_count"] / 3
            )
            st.caption(
                f"{summary['cabin_observation_count']} / 3 구역 확인"
            )

            cabin_steps = [
                ("door", "출입문과 잠금장치"),
                ("table", "테이블과 물품"),
                ("floor", "바닥과 가구"),
            ]
            for observation_id, label in cabin_steps:
                if (
                    observation_id
                    in summary["cabin_observations"]
                ):
                    st.write(f"● {label}")
                else:
                    st.write("○ 미확인 구역")

            st.caption(
                "1장에서는 에코의 안내를 따라 게임 기능을 "
                "익힐 수 있습니다."
            )

        if summary["recent_records"]:
            st.markdown("### 최근 확보")

            for record in reversed(
                summary["recent_records"]
            ):
                st.write(f"- {record}")

        seen_count = st.session_state.get(
            "notebook_seen_count",
            0,
        )
        unread_count = max(
            0,
            len(summary["notebook_entries"])
            - seen_count,
        )
        notebook_label = "📓 사건 수첩 보기"
        if unread_count:
            notebook_label += f" · 새 기록 {unread_count}"

        if (
            st.session_state.get("tutorial_stage")
            == "notebook_prompt"
        ):
            st.info(
                "에코 안내 · 아래 사건 수첩 보기 버튼을 눌러 보세요."
            )

        if st.button(
            notebook_label,
            key="case_notebook_button",
            use_container_width=True,
        ):
            st.session_state.notebook_previous_seen_count = (
                seen_count
            )
            st.session_state.main_view = "notebook"

            if (
                st.session_state.get("tutorial_stage")
                == "notebook_prompt"
            ):
                st.session_state.tutorial_stage = (
                    "notebook_opened"
                )
                set_tutorial_expected_action("cabin")
                mark_tutorial_event("coach_cabin")
                st.session_state.setdefault(
                    "messages",
                    [],
                ).append({
                    "role": "assistant",
                    "content": (
                        "좋습니다. **사건 수첩**에는 앞으로 "
                        "당신이 직접 확보한 조사 기록만 쌓입니다.\n\n"
                        "아직 발견하지 않은 단서는 표시하지 않으니, "
                        "수첩 자체가 정답 목록이 되지는 않습니다. "
                        "조사가 길어졌을 때 무엇을 확인했는지 "
                        "되짚는 용도로 사용하세요.\n\n"
                        "그 아래의 **힌트 요청**은 막혔을 때만 "
                        "사용하면 됩니다. 기회는 세 번뿐이지만, "
                        "지금 안내를 확인한 것으로 횟수가 "
                        "차감되지는 않습니다.\n\n"
                        "이제 객실에 남은 흔적부터 살펴보는 게 "
                        "좋겠어요. 저에게 **객실을 조사해 달라**고 "
                        "말씀해 주시겠어요? 표현은 자유롭게 하셔도 "
                        "알아들을 수 있습니다."
                    ),
                    "icon": "📓",
                })

            st.rerun()

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

        env_debug_enabled = os.getenv(
            "GAME_DEBUG",
            "",
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        if LOCAL_DEBUG_TOOLS_ENABLED or env_debug_enabled:
            st.divider()
            with st.expander("🛠 개발자 도구"):
                checkpoint_labels = {
                    "1장 시작": "chapter_1_start",
                    "2장 시작": "chapter_2_start",
                    "2장 · 박소영 인터뷰 직전": (
                        "chapter_2_last_interview"
                    ),
                    "2장 · 진술 비교 직전": (
                        "chapter_2_compare"
                    ),
                }
                selected_checkpoint_label = st.selectbox(
                    "테스트 지점",
                    options=list(checkpoint_labels),
                    key="debug_checkpoint_selector",
                )
                st.caption(
                    "현재 플레이 기록을 테스트 상태로 교체합니다. "
                    "실제 서비스에서는 표시되지 않습니다."
                )

                if st.button(
                    "테스트 상태 적용",
                    key="apply_debug_checkpoint_button",
                    use_container_width=True,
                ):
                    checkpoint = checkpoint_labels[
                        selected_checkpoint_label
                    ]
                    apply_debug_checkpoint(
                        st.session_state,
                        checkpoint,
                    )
                    st.session_state.screen = "game"
                    st.session_state.game_phase = "investigation"
                    st.session_state.selected_suspect = None
                    st.session_state.final_theory = {}
                    st.session_state.confirm_hint = False
                    st.session_state.main_view = "chat"
                    st.session_state.notebook_seen_count = 0
                    st.session_state.notebook_previous_seen_count = 0
                    st.session_state.notebook_acknowledged_count = 0

                    if checkpoint == "chapter_1_start":
                        st.session_state.messages = []
                        st.session_state.intro_played = False
                        st.session_state.tutorial_stage = (
                            "awaiting_briefing"
                        )
                    else:
                        st.session_state.messages = [{
                            "role": "assistant",
                            "content": (
                                get_chapter_transition_message(2)
                            ),
                            "icon": "📖",
                            "image": str(CHAPTER_IMAGES[2]),
                            "layout": "chapter_card",
                        }]
                        st.session_state.intro_played = True
                        st.session_state.tutorial_stage = "completed"

                    st.rerun()

    return summary


def render_case_notebook_main(summary):
    """확보한 기록을 메인 화면 전체 너비로 보여준다."""
    title_column, back_column = st.columns(
        [4, 1],
    )

    with title_column:
        st.markdown("## 📓 사건 수첩")
        st.caption(
            "직접 확보한 기록만 보관됩니다. "
            "기록을 눌러 원문을 확인하세요."
        )

    with back_column:
        if st.button(
            "조사로 돌아가기",
            use_container_width=True,
        ):
            reviewed_count = len(
                summary["notebook_entries"]
            )
            last_acknowledged = st.session_state.get(
                "notebook_acknowledged_count",
                0,
            )

            if (
                reviewed_count > 0
                and reviewed_count > last_acknowledged
            ):
                # 인터뷰 중에는 수첩 열람 알림을 채팅에 끼워 넣지
                # 않는다. 플레이어의 다음 질문이 인물에게 그대로
                # 전달되도록 열람 상태만 갱신한다.
                if get_active_interview() is None:
                    if (
                        summary["chapter_number"] == 1
                        and is_chapter_one_ready()
                    ):
                        notebook_message = (
                            "객실 현장·법의학·발견 경위 기록을 모두 "
                            "확인하셨군요. 이제 조사 화면 아래의 "
                            "**탐정의 첫 판단**에서 가장 주목한 기록 "
                            "하나를 선택한 뒤 **판단 기록하기**를 "
                            "눌러 주세요."
                        )
                    elif (
                        summary["chapter_number"] == 2
                        and is_chapter_two_ready()
                    ):
                        notebook_message = (
                            "네 사람의 기본 진술을 모두 확인하셨군요. "
                            "조사 화면 아래의 **가장 먼저 검증할 진술**에서 "
                            "객관적인 기록과 대조할 항목을 선택한 뒤 "
                            "**검증 우선순위 기록하기**를 눌러 주세요."
                        )
                    else:
                        notebook_message = (
                            "새로 확보한 기록을 확인하셨군요. 기록에서 "
                            "마음에 걸리는 사실이 있다면 제게 질문하거나 "
                            "남은 조사를 이어가세요."
                        )

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": notebook_message,
                        "icon": "📓",
                    })
                st.session_state.notebook_acknowledged_count = (
                    reviewed_count
                )

            st.session_state.main_view = "chat"
            st.rerun()

    st.divider()

    if not summary["notebook_entries"]:
        st.info(
            "아직 사건 수첩에 등록된 조사 기록이 없습니다. "
            "조사를 진행하면 이곳에 기록이 추가됩니다."
        )
        return

    previous_seen_count = st.session_state.get(
        "notebook_previous_seen_count",
        st.session_state.get("notebook_seen_count", 0),
    )

    for index, entry in enumerate(
        summary["notebook_entries"],
        start=1,
    ):
        is_new_entry = index > previous_seen_count
        entry_label = f"{index:02d} · {entry['title']}"
        if is_new_entry:
            entry_label += " · NEW"

        with st.expander(
            entry_label,
            expanded=is_new_entry,
        ):
            if entry["content"]:
                st.markdown(entry["content"])
            else:
                st.caption(
                    "이 기록의 상세 내용은 에코에게 질문해 "
                    "확인할 수 있습니다."
                )

    st.session_state.notebook_seen_count = len(
        summary["notebook_entries"]
    )


def render_chapter_one_completion(summary):
    """1장 핵심 기록을 정리한 뒤 플레이어가 직접 장을 종료한다."""
    if (
        summary["chapter_number"] != 1
        or not is_chapter_one_ready()
    ):
        return

    records_reviewed = (
        st.session_state.get("notebook_seen_count", 0)
        >= len(summary["notebook_entries"])
    )
    reflection = get_chapter_one_reflection()
    reflection_options = {
        "forced_entry": "강제 침입 흔적이 없다는 점",
        "table_items": "물잔과 약 보관함이 남아 있다는 점",
        "disturbed_layout": "의자와 바닥 매트가 어긋나 있다는 점",
        "discovery_time": "23시 20분이 사망 시각이 아닌 발견 시각이라는 점",
        "insufficient": "아직 어느 한 단서도 단정하기 어렵다는 점",
    }
    reflection_responses = {
        "forced_entry": (
            "좋은 관찰입니다. 외부 파손이 없다는 사실은 출입 방식의 "
            "범위를 좁히지만, 누가 문을 열었는지는 아직 설명하지 "
            "못합니다. 다음 장에서 관계자들의 진술과 비교해 보십시오."
        ),
        "table_items": (
            "눈에 띄는 물품이지만 존재 자체가 복용이나 사인을 "
            "증명하지는 않습니다. 물품과 법의학 기록을 구분해 "
            "판단한 점을 기억해 두십시오."
        ),
        "disturbed_layout": (
            "작은 배치의 어긋남을 놓치지 않으셨군요. 다만 이것이 "
            "충돌의 결과인지 일상적인 흔적인지는 아직 단정할 수 "
            "없습니다."
        ),
        "discovery_time": (
            "중요한 구분입니다. 발견 시각을 사망 시각으로 오인하면 "
            "이후 모든 동선 분석이 흔들립니다. 정확한 시간대는 "
            "추가 기록과 함께 좁혀야 합니다."
        ),
        "insufficient": (
            "신중한 판단입니다. 현재 단서는 가능성을 보여줄 뿐 "
            "특정 인물을 가리키지 않습니다. 다음 장의 진술을 통해 "
            "각 기록의 의미를 검증하십시오."
        ),
    }

    with st.container(border=True):
        st.markdown("## 제1장 핵심 기록 확보 완료")
        st.markdown(
            """
            - 피해자 객실 현장 기록
            - 법의학 및 사망 원인 기록
            - 시신 발견 경위 기록
            """
        )

        if not records_reviewed:
            st.info(
                "2장으로 넘어가기 전에 사건 수첩에서 새로 확보한 "
                "기록을 확인해 주세요."
            )
        elif reflection is None:
            st.markdown("### 탐정의 첫 판단")
            st.caption(
                "현재 기록에서 가장 주목할 점을 하나 선택해 "
                "사건 수첩에 남겨 주세요. 정답을 맞히는 단계는 "
                "아니며, 이후 조사 관점을 정리하기 위한 기록입니다."
            )
            st.info(
                "아래 항목 중 하나를 클릭한 뒤, "
                "**판단 기록하기** 버튼을 눌러 주세요."
            )
            selected_label = st.radio(
                "가장 주목한 기록을 하나 선택하세요",
                options=list(reflection_options.values()),
                index=None,
            )

            if st.button(
                "판단 기록하기",
                type="primary",
                disabled=selected_label is None,
                use_container_width=True,
            ):
                selected_key = next(
                    key
                    for key, label in reflection_options.items()
                    if label == selected_label
                )
                if set_chapter_one_reflection(selected_key):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": (
                            f"**탐정의 첫 판단**\n\n"
                            f"> {reflection_options[selected_key]}\n\n"
                            f"{reflection_responses[selected_key]}"
                        ),
                        "icon": "🧭",
                    })
                    st.rerun()
        else:
            st.caption(
                "사건 수첩 검토 및 첫 판단 기록 완료 · "
                "관계자 진술 조사 준비"
            )
            st.markdown(
                f"**기록한 판단:** {reflection_options[reflection]}"
            )

        if reflection is not None:
            if st.button(
                "1장 정리하기",
                type="primary",
                use_container_width=True,
            ):
                if complete_chapter_one():
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": get_chapter_transition_message(2),
                        "icon": "📖",
                        "image": str(CHAPTER_IMAGES[2]),
                        "layout": "chapter_card",
                    })
                    st.session_state.tutorial_stage = "completed"
                    st.session_state.main_view = "chat"
                    st.rerun()


def render_chapter_two_completion(summary):
    """네 사람의 진술을 비교하고 검증할 기록을 선택한다."""
    if (
        summary["chapter_number"] != 2
        or not is_chapter_two_ready()
    ):
        return

    records_reviewed = (
        st.session_state.get("notebook_seen_count", 0)
        >= len(summary["notebook_entries"])
    )
    reflection = get_chapter_two_reflection()
    reflection_options = {
        "dongyul_access": (
            "김동율은 정말 피해자 객실구역에 가지 않았는가"
        ),
        "hyunjun_conflict": (
            "김현준은 피해자와의 업무상 언쟁을 얼마나 축소했는가"
        ),
        "kangwonmo_room": (
            "강원모는 저녁 이후 대부분 자기 객실에 있었는가"
        ),
        "parksoyoung_message": (
            "21시 15분 메시지는 피해자의 생존을 증명하는가"
        ),
    }
    reflection_responses = {
        "dongyul_access": (
            "김동율의 원한은 강한 동기처럼 보이지만, 진술이 사실인지 "
            "확인하려면 객실구역 목격기록이 필요합니다."
        ),
        "hyunjun_conflict": (
            "업무 갈등의 존재와 실제 언쟁의 강도는 다를 수 있습니다. "
            "당시 대화를 본 목격자의 기록으로 검증해야 합니다."
        ),
        "kangwonmo_room": (
            "객실에 있었다는 말은 출입 시스템이 무엇을 기록하고 "
            "무엇을 기록하지 않는지 확인해야 평가할 수 있습니다."
        ),
        "parksoyoung_message": (
            "메시지가 도착한 시각과 피해자가 직접 작성한 시각은 "
            "같지 않을 수 있습니다. 디지털 기록 확인이 필요합니다."
        ),
    }

    with st.container(border=True):
        st.markdown("## 제2장 진술 확보 완료")
        st.markdown(
            """
            네 사람은 모두 사실의 일부를 말했지만, 진술만으로는
            어느 말이 정확한지 판단할 수 없습니다.
            """
        )

        if not records_reviewed:
            st.info(
                "사건 수첩을 열어 네 사람의 진술을 먼저 확인해 "
                "주세요. 확인한 뒤 조사 화면으로 돌아오면 진술을 "
                "비교할 수 있습니다."
            )
        elif reflection is None:
            st.markdown("### 가장 먼저 검증할 진술")
            st.caption(
                "범인을 지목하는 단계가 아닙니다. 객관적인 기록과 "
                "가장 먼저 대조하고 싶은 진술을 선택하세요."
            )
            selected_label = st.radio(
                "검증할 진술을 하나 선택하세요",
                options=list(reflection_options.values()),
                index=None,
                key="chapter_two_reflection_choice",
            )

            if st.button(
                "검증 우선순위 기록하기",
                type="primary",
                disabled=selected_label is None,
                use_container_width=True,
            ):
                selected_key = next(
                    key
                    for key, label in reflection_options.items()
                    if label == selected_label
                )
                if set_chapter_two_reflection(selected_key):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": (
                            "**진술 비교 기록**\n\n"
                            f"> {reflection_options[selected_key]}\n\n"
                            f"{reflection_responses[selected_key]}"
                        ),
                        "icon": "🧭",
                    })
                    st.rerun()
        else:
            st.caption(
                "네 사람의 진술 검토 및 검증 우선순위 기록 완료"
            )
            st.markdown(
                f"**먼저 검증할 진술:** "
                f"{reflection_options[reflection]}"
            )

        if reflection is not None:
            if st.button(
                "2장 정리하기",
                type="primary",
                use_container_width=True,
            ):
                if complete_chapter_two():
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": get_chapter_transition_message(3),
                        "icon": "📖",
                        "image": str(CHAPTER_IMAGES[3]),
                        "layout": "chapter_card",
                    })
                    st.session_state.main_view = "chat"
                    st.rerun()

# 현재 화면을 기억하는 상태
if "screen" not in st.session_state:
    st.session_state.screen = "start"

# 이 브라우저 세션의 조사 상태를 game_state와 연결
bind_session_state(st.session_state)

# 시작 화면
if st.session_state.screen == "start":
    st.markdown(
        """
        <div class="title-screen">
            <div class="title-screen-kicker">
                CASE ARCHIVE 07-20 · INTERACTIVE MYSTERY
            </div>
            <div class="title-screen-name">해성호의 마지막 기록</div>
            <div class="title-screen-subtitle">
                폭풍 속에서 열린 객실 · 8년 동안 닫혀 있던 기록
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    st.image(
        TITLE_HERO_IMAGE,
        use_container_width=True,
    )
    st.markdown(
        """
        <div class="title-screen-status">
            NATURAL LANGUAGE INVESTIGATION · CASE NOTEBOOK · 6 CHAPTERS
        </div>
        """,
        unsafe_allow_html=True,
    )

    left, center, right = st.columns([1, 1.5, 1])
    with center:
        if st.button(
            "새 사건 기록 열기",
            type="primary",
            use_container_width=True
        ):
            reset_game_state(st.session_state)
            st.session_state.messages = []
            st.session_state.intro_played = False
            st.session_state.game_phase = "investigation"
            st.session_state.selected_suspect = None
            st.session_state.final_theory = {}
            st.session_state.confirm_hint = False
            st.session_state.main_view = "chat"
            st.session_state.notebook_seen_count = 0
            st.session_state.notebook_previous_seen_count = 0
            st.session_state.notebook_acknowledged_count = 0
            st.session_state.tutorial_stage = "not_started"
            st.session_state.screen = "prologue"
            st.rerun()

        with st.expander("조사 방식"):
            st.markdown(
                """
                - 기록관 에코에게 자연어로 조사와 질문을 요청합니다.
                - 확보한 증거와 진술은 사건 수첩에 보관됩니다.
                - 6개의 장을 거치며 시간·동선·과거 기록을 연결합니다.
                - 충분한 근거를 모은 뒤 직접 최종 추리를 제출합니다.
                """
            )

    st.stop()

# 프롤로그 화면
if st.session_state.screen == "prologue":
    st.markdown(
        """
        <div class="case-header">
            <div class="case-kicker">PROLOGUE · JULY 20</div>
            <div class="case-title">객실이 열린 밤</div>
            <div class="case-subtitle">
                폭풍 속 크루즈 · 외부 지원 도착 전
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="prologue-log">
            <div class="prologue-log-time">22:30 · MISSED APPOINTMENT</div>
            <div class="prologue-log-text">
                최종인은 예정된 업무 장소에 나타나지 않았습니다.
                몇 번의 호출에도 응답은 없었습니다.
            </div>
            <div class="prologue-log-time">23:05 · CABIN CHECK</div>
            <div class="prologue-log-text">
                선내 직원과 보안 담당자가 객실 앞에 도착했습니다.
                문은 외부에서 부서진 흔적 없이 닫혀 있었습니다.
            </div>
            <div class="prologue-log-time">23:20 · EMERGENCY OPEN</div>
            <div class="prologue-log-text">
                비상 개방된 문 안쪽에서 최종인이 발견됐습니다.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    st.info(
        "폭풍으로 외부 지원이 지연되고 있습니다. 피해자의 이름은 "
        "8년 전 인명피해를 남긴 해성호 좌초 사고 기록에도 남아 "
        "있습니다. 선내 보안팀이 초기 기록 재구성을 요청했습니다."
    )

    back_column, start_column = st.columns(2)

    with back_column:
        if st.button("처음으로", use_container_width=True):
            st.session_state.screen = "start"
            st.rerun()

    with start_column:
        if st.button(
            "기록관 에코 접속",
            type="primary",
            use_container_width=True
        ):
            st.session_state.screen = "game"
            st.session_state.tutorial_stage = "awaiting_briefing"
            st.rerun()

    st.stop()

current_chapter = get_story_chapter()

# 사이드바의 튜토리얼 클릭도 대화 기록을 추가할 수 있도록
# 본문과 사이드바를 그리기 전에 필요한 세션 값을 준비한다.
if "messages" not in st.session_state:
    st.session_state.messages = []
if "tutorial_stage" not in st.session_state:
    st.session_state.tutorial_stage = "not_started"
if "main_view" not in st.session_state:
    st.session_state.main_view = "chat"
if "notebook_seen_count" not in st.session_state:
    st.session_state.notebook_seen_count = 0
if "is_processing_chat" not in st.session_state:
    st.session_state.is_processing_chat = False
if (
    st.session_state.is_processing_chat
    and "pending_chat_input" not in st.session_state
):
    # 처리 중 예외나 새로고침이 발생해도 입력창이 영구 잠기지 않는다.
    st.session_state.is_processing_chat = False

st.markdown(
    f"""
    <div class="case-header">
        <div class="case-kicker">
            CASE ARCHIVE · CHAPTER {current_chapter['number']:02d}
        </div>
        <div class="case-title">해성호의 마지막 기록</div>
        <div class="case-subtitle">
            {current_chapter['label']} · 기록관 에코 접속 중
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
sidebar_summary = render_investigation_sidebar()

if st.session_state.main_view == "notebook":
    render_case_notebook_main(sidebar_summary)
    st.stop()

# 시작 메시지를 이미 출력했는지 확인
if "intro_played" not in st.session_state:
    st.session_state.intro_played = False
if "game_phase" not in st.session_state:
    st.session_state.game_phase = "investigation"

if "selected_suspect" not in st.session_state:
    st.session_state.selected_suspect = None

if "final_theory" not in st.session_state:
    st.session_state.final_theory = {}

def _character_message_content(content, speaker):
    """캐릭터 이름이 채팅 제목과 본문에 중복되지 않게 정리한다."""
    if not speaker:
        return content

    lines = content.lstrip().splitlines()
    if (
        lines
        and lines[0].startswith("## ")
        and speaker in lines[0]
    ):
        lines = lines[1:]
        while lines and not lines[0].strip():
            lines.pop(0)
        return "\n".join(lines)

    return content


def _detect_character_speaker(
    content,
    interview_before,
    interview_after,
):
    """응답 본문이 실제 캐릭터 발화일 때만 인물 이름을 반환한다."""
    stripped = content.lstrip()
    candidates = [
        interview_after,
        interview_before,
    ]
    for person in candidates:
        if (
            person
            and stripped.startswith("## ")
            and person in stripped.splitlines()[0]
        ):
            return person
    return None


def render_saved_chat_message(message):
    """저장된 대화를 재생하되 지난 증거 카드는 작게 표시한다."""
    if message["role"] == "user":
        with st.chat_message("user", avatar="🕵️"):
            st.write(message["content"])
    else:
        speaker = message.get("speaker")
        avatar = "🗣️" if speaker else "🤖"
        with st.chat_message("assistant", avatar=avatar):
            icon = message.get("icon", "📁")
            if speaker:
                st.markdown(f"### {speaker}")
            else:
                st.markdown(f"### {icon} 기록관 에코")
            if message.get("layout") == "opening_card":
                render_opening_briefing(
                    message["image"]
                )
            elif (
                message.get("image")
                and message.get("layout")
                == "chapter_card"
            ):
                render_illustrated_message(
                    message["image"],
                    message["content"],
                )
            elif message.get("layout") == "evidence_card":
                render_evidence_card(
                    message["evidence_card"],
                    message["content"],
                    animate=False,
                    compact=True,
                )
            else:
                if message.get("image"):
                    st.image(
                        message["image"],
                        use_container_width=True,
                    )
                stream_text(
                    _character_message_content(
                        message["content"],
                        speaker,
                    ),
                    animate=False,
                )


# 현재 장보다 앞선 대화는 접어서 스크롤 길이를 줄인다.
messages = st.session_state.messages
current_transition_index = None
if current_chapter["number"] > 1:
    expected_image = str(
        CHAPTER_IMAGES[current_chapter["number"]]
    )
    for index, message in enumerate(messages):
        if (
            message.get("layout") == "chapter_card"
            and message.get("image") == expected_image
        ):
            current_transition_index = index
            break

if current_transition_index:
    with st.expander(
        f"이전 장 대화 {current_transition_index}개 펼쳐보기",
        expanded=False,
    ):
        for message in messages[:current_transition_index]:
            render_saved_chat_message(message)
    visible_messages = messages[current_transition_index:]
else:
    visible_messages = messages

for message in visible_messages:
    render_saved_chat_message(message)
            
# 최초 실행 시 시작 메시지를 스트리밍으로 출력
if not st.session_state.intro_played:
    intro = get_start_message()

    with st.chat_message("assistant", avatar="🤖"):
        st.markdown("### 📖 기록관 에코")
        render_opening_briefing(
            CHAPTER_IMAGES[1]
        )

    st.session_state.messages.append({
        "role": "assistant",
        "content": intro,
        "icon": "📖",
        "image": str(CHAPTER_IMAGES[1]),
        "layout": "opening_card",
    })

    st.session_state.intro_played = True
    if (
        st.session_state.get("tutorial_stage")
        == "awaiting_briefing"
    ):
        st.session_state.tutorial_stage = "awaiting_echo"
    st.rerun()

# 사건 브리핑을 먼저 읽을 시간을 준 뒤 에코가 말을 건다.
if st.session_state.tutorial_stage == "awaiting_echo":
    time.sleep(1.2)
    st.session_state.messages.append({
        "role": "assistant",
        "content": (
            "기록관 에코 접속 완료.\n\n"
            "탐정님이 직접 확인한 자료만 왼쪽 **수사 기록**에 "
            "동기화하겠습니다. 발견하지 않은 정보는 표시하지 "
            "않으며, 새 기록은 **사건 수첩**에 보관됩니다.\n\n"
            "먼저 왼쪽의 **📓 사건 수첩 보기**를 열어 초기 기록 "
            "보관 상태를 확인해 주십시오. 작은 화면에서 패널이 "
            "접혀 있다면 왼쪽 위 화살표로 열 수 있습니다."
        ),
        "icon": "💬",
    })
    st.session_state.tutorial_stage = "notebook_prompt"
    st.rerun()

render_chapter_one_completion(
    get_sidebar_summary()
)
render_chapter_two_completion(
    get_sidebar_summary()
)

required_action_labels = {
    "cabin": "객실의 출입문과 잠금장치 확인",
    "cabin_table": "객실 테이블과 물품 확인",
    "cabin_floor": "객실 바닥과 가구 주변 확인",
    "forensic": "피해자의 상태와 사망 원인 확인",
    "discovery": "신고부터 객실 개방까지의 시신 발견 과정 확인",
}
required_action = get_required_next_action()
if required_action:
    st.caption(
        "현재 조사 · "
        f"{required_action_labels[required_action]}"
    )
elif (
    current_chapter["number"] == 1
    and is_chapter_one_ready()
):
    if get_chapter_one_reflection() is None:
        st.caption(
            "현재 조사 · 사건 수첩을 검토하고 탐정의 첫 판단 기록"
        )
    else:
        st.caption("현재 조사 · 제1장 기록 정리")

# 사용자 입력
def _queue_chat_input():
    """제출 즉시 입력을 잠그고 다음 실행에서 한 번만 처리한다."""
    submitted = st.session_state.get(
        "main_chat_input",
        "",
    ).strip()
    if submitted and not st.session_state.is_processing_chat:
        st.session_state.pending_chat_input = submitted
        st.session_state.is_processing_chat = True


st.chat_input(
    (
        "답변을 처리하고 있습니다..."
        if st.session_state.is_processing_chat
        else "조사 내용이나 질문을 입력하세요."
    ),
    key="main_chat_input",
    disabled=st.session_state.is_processing_chat,
    on_submit=_queue_chat_input,
)

if st.session_state.is_processing_chat:
    st.caption(
        "기록관 또는 인터뷰 인물이 응답을 마칠 때까지 "
        "새 메시지를 입력할 수 없습니다."
    )

user_input = st.session_state.pop(
    "pending_chat_input",
    None,
)

if user_input:
    chapter_before = get_story_chapter()["number"]
    interview_before = get_active_interview()
    investigated_before = get_investigated()
    observations_before = get_cabin_observations()

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
            active_interview_person = get_active_interview()
            interview_loading_labels = {
                "김동율": "💬 김동율이 답변을 고르고 있습니다...",
                "김현준": "💬 김현준이 답변을 정리하고 있습니다...",
                "강원모": "💬 강원모가 답변을 준비하고 있습니다...",
                "박소영": "💬 박소영이 기억을 되짚고 있습니다...",
            }
            loading_text = interview_loading_labels.get(
                active_interview_person,
                "🔎 에코가 기록을 확인하고 답변을 준비하고 있습니다...",
            )
            with st.spinner(
                loading_text
            ):
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
            st.session_state.final_theory = {
                "suspect": accused
            }
            st.session_state.game_phase = "entering_time"

            answer = f"""
━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ 최종 추리

지목한 인물: **{accused}**

이제 실제 범행이 가능했던 시간대를 입력하십시오.

정확한 분 단위가 아니어도 됩니다.
확보한 목격·메시지·출입기록을 바탕으로
시간 범위를 설명할 수 있습니다.

중단하려면 **지목 취소**라고 입력하십시오.

━━━━━━━━━━━━━━━━━━━━━━
"""

        else:
            answer = """
등록되지 않은 인물입니다.

김동율, 김현준, 강원모, 박소영 중 한 명을 입력하십시오.
"""

    # 3. 범행 가능시간 입력
    elif st.session_state.game_phase == "entering_time":

        if user_input.strip() in ["취소", "지목 취소"]:
            answer = "최종 추리를 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.selected_suspect = None
            st.session_state.final_theory = {}
            st.session_state.game_phase = "investigation"
        else:
            st.session_state.final_theory["crime_time"] = (
                user_input.strip()
            )
            st.session_state.game_phase = "entering_motive"
            answer = """
범행 가능시간을 기록했습니다.

이제 지목한 인물이 최종인을 살해할 이유가 무엇인지 입력하십시오.

현재 사건과 8년 전 기록의 관계를 포함해 설명할 수 있습니다.

중단하려면 **지목 취소**라고 입력하십시오.
"""

    # 4. 동기 입력
    elif st.session_state.game_phase == "entering_motive":

        if user_input.strip() in ["취소", "지목 취소"]:
            answer = "최종 추리를 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.selected_suspect = None
            st.session_state.final_theory = {}
            st.session_state.game_phase = "investigation"
        else:
            st.session_state.final_theory["motive"] = (
                user_input.strip()
            )
            st.session_state.game_phase = "entering_evidence"
            answer = """
범행 동기를 기록했습니다.

마지막으로 이 추리를 뒷받침하는 핵심 증거들을 입력하십시오.

서로 다른 종류의 기록을 연결해서 설명해야 합니다.
문장이나 목록 형식 모두 사용할 수 있습니다.

중단하려면 **지목 취소**라고 입력하십시오.
"""

    # 5. 핵심 증거 입력
    elif st.session_state.game_phase == "entering_evidence":

        if user_input.strip() in ["취소", "지목 취소"]:
            answer = "최종 추리를 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.selected_suspect = None
            st.session_state.final_theory = {}
            st.session_state.game_phase = "investigation"
        else:
            st.session_state.final_theory["evidence"] = (
                user_input.strip()
            )
            st.session_state.game_phase = "confirming"
            theory = st.session_state.final_theory

            answer = f"""
━━━━━━━━━━━━━━━━━━━━━━

## ⚠️ 최종 추리 확인

- **지목 인물:** {theory['suspect']}
- **범행 가능시간:** {theory['crime_time']}
- **동기:** {theory['motive']}
- **핵심 증거:** {theory['evidence']}

이 내용으로 최종 판정을 진행하면
이후에는 추가 조사를 진행할 수 없습니다.

확정하려면 **예**
취소하려면 **아니오**

━━━━━━━━━━━━━━━━━━━━━━
"""

    # 6. 최종 확인 상태
    elif st.session_state.game_phase == "confirming":

        if user_input.strip().lower() in ["예", "네", "ㅇ", "yes", "y"]:

            with st.spinner("🔎 확보된 증거를 최종 분석하는 중입니다..."):
                time.sleep(2)

            theory = st.session_state.final_theory
            answer = judge_accusation(
                theory["suspect"],
                theory["crime_time"],
                theory["motive"],
                theory["evidence"],
            )
            st.session_state.game_phase = "finished"

        elif user_input.strip() in ["아니오", "아니요", "취소", "ㄴ"]:
            answer = "범인 지목을 취소했습니다. 조사를 계속할 수 있습니다."
            st.session_state.selected_suspect = None
            st.session_state.final_theory = {}
            st.session_state.game_phase = "investigation"

        else:
            answer = "최종 지목하려면 **예**, 취소하려면 **아니오**라고 입력하십시오."

    # 7. 게임 종료 상태
    else:
        answer = """
이미 사건의 최종 판정이 완료되었습니다.

새로운 게임을 시작하려면 앱을 다시 실행하십시오.
"""
    chapter_after = get_story_chapter()["number"]
    chapter_image = None
    if chapter_after > chapter_before:
        answer += get_chapter_transition_message(chapter_after)
        chapter_image = str(
            CHAPTER_IMAGES[chapter_after]
        )

    coach_message = None
    if st.session_state.game_phase == "investigation":
        coach_message = get_chapter_one_coach_message()
        if not coach_message:
            coach_message = get_pending_tutorial_reminder()

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

    evidence_card = detect_new_evidence_card(
        investigated_before,
        observations_before,
    )

    interview_after = get_active_interview()
    character_speaker = _detect_character_speaker(
        answer,
        interview_before,
        interview_after,
    )
    answer_avatar = "🗣️" if character_speaker else "🤖"
    with st.chat_message("assistant", avatar=answer_avatar):
        if character_speaker:
            st.markdown(f"### {character_speaker}")
        else:
            st.markdown(f"### {answer_icon} 기록관 에코")
        if chapter_image:
            render_illustrated_message(
                chapter_image,
                answer,
                animate=True,
            )
        elif evidence_card:
            render_evidence_card(
                evidence_card,
                answer,
                animate=True,
            )
        else:
            stream_text(
                _character_message_content(
                    answer,
                    character_speaker,
                ),
                animate=True,
            )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer,
        "icon": answer_icon,
        "image": chapter_image,
        "layout": (
            "chapter_card"
            if chapter_image
            else (
                "evidence_card"
                if evidence_card
                else None
            )
        ),
        "evidence_card": evidence_card,
        "speaker": character_speaker,
    })

    if coach_message:
        time.sleep(0.6)
        with st.chat_message("assistant", avatar="🤖"):
            st.markdown("### 💬 기록관 에코")
            stream_text(
                coach_message,
                animate=True,
                delay=0.01,
            )

        st.session_state.messages.append({
            "role": "assistant",
            "content": coach_message,
            "icon": "💬",
        })

    st.session_state.is_processing_chat = False
    st.rerun()
