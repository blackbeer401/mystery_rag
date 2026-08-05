"""'21시 15분 — 죽은 사람이 보낸 메시지' 결정론적 게임 엔진.

이 모듈은 Streamlit과 OpenAI에 의존하지 않는다. 게임 진행과 판정에
사용되는 값은 제작자가 정의한 자료/주장 ID뿐이며 자유 텍스트는 상태를
변경하지 않는다.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from typing import Iterable


@dataclass(frozen=True)
class Evidence:
    id: str
    title: str
    body: str
    source_type: str
    people: tuple[str, ...]
    time: str
    proves: str
    does_not_prove: str
    unlock_condition: str
    claim_ids: tuple[str, ...]


@dataclass(frozen=True)
class Claim:
    id: str
    title: str
    explanation: str


@dataclass
class MemoryState:
    scene_started: bool = False
    initial_hypothesis_id: str | None = None
    unlocked_evidence_ids: list[str] = field(default_factory=lambda: list(INITIAL_EVIDENCE_IDS))
    workspace_ids: list[str] = field(default_factory=list)
    unlocked_claim_ids: list[str] = field(default_factory=list)
    completed_connection_ids: list[str] = field(default_factory=list)
    forensic_complete: bool = False
    attempts: int = 0
    completed: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)

    @classmethod
    def from_json(cls, payload: str) -> "MemoryState":
        data = json.loads(payload)
        if not isinstance(data, dict):
            raise ValueError("기억 복원 상태는 객체여야 합니다.")
        state = cls(**{
            name: data[name]
            for name in cls.__dataclass_fields__
            if name in data
        })
        _validate_state(state)
        return state


INITIAL_EVIDENCE_IDS = (
    "WITNESS_1955",
    "MESSAGE_2115",
    "ABSENCE_2230",
    "DISCOVERY_2320",
)
METADATA_ID = "MESSAGE_METADATA"
MAX_WORKSPACE_ITEMS = 3

EVIDENCE = {
    "WITNESS_1955": Evidence(
        "WITNESS_1955", "19:55 · 마지막 직접 대화",
        "서민재는 약 19시 55분 객실구역에서 최종인과 직접 대화했다. 당시 최종인은 질문에 정상적으로 답했다.",
        "타인 목격", ("서민재", "최종인"), "약 19:55",
        "최종인이 약 19시 55분까지 살아 있었다.",
        "그 이후의 생존 여부, 정확한 사망시각과 범인은 알 수 없다.",
        "처음부터 공개", ("CLAIM_CONFIRMED_WINDOW",),
    ),
    "MESSAGE_2115": Evidence(
        "MESSAGE_2115", "21:15 · 최종인 명의 메시지",
        "박소영은 21시 15분 최종인 명의의 정상적인 업무 메시지를 받았다. 내용은 22시 30분 예정된 업무 일정을 확인하는 문구였다.",
        "객관 기록", ("박소영", "최종인"), "21:15",
        "최종인 명의 메시지가 박소영에게 21시 15분 수신됐다.",
        "누가 언제 작성했는지, 최종인이 21시 15분에 살아 있었는지는 알 수 없다.",
        "처음부터 공개", ("CLAIM_MESSAGE_NOT_SURVIVAL",),
    ),
    "ABSENCE_2230": Evidence(
        "ABSENCE_2230", "22:30 · 예정 업무 불참",
        "최종인은 박소영과 예정된 22시 30분 업무 일정에 나타나지 않았다. 박소영은 이후 연락과 객실 확인을 요청했다.",
        "자기 진술", ("박소영", "최종인"), "22:30",
        "최종인이 22시 30분 약속에 나타나지 않았다.",
        "불참 이유와 그 시점의 생사 여부는 알 수 없다.",
        "처음부터 공개", (),
    ),
    "DISCOVERY_2320": Evidence(
        "DISCOVERY_2320", "23:20 · 사망 공식 확인",
        "선내 직원과 보안 담당자는 약 23시 20분 객실을 비상 개방했다. 객실 안에서 최종인의 사망이 공식 확인됐다.",
        "객관 기록", ("최종인",), "약 23:20",
        "최종인이 약 23시 20분에는 사망한 상태였다.",
        "정확한 사망시각과 범인은 알 수 없다.",
        "처음부터 공개", ("CLAIM_CONFIRMED_WINDOW",),
    ),
    "MESSAGE_METADATA": Evidence(
        "MESSAGE_METADATA", "메시지 예약발송 메타데이터",
        "메시지는 최종인이 생전에 정상 업무 목적으로 작성하고 21시 15분 자동 발송을 설정했다. 해당 시각에는 예약된 전송만 실행됐다.",
        "객관 기록", ("최종인", "박소영"), "작성·예약 시각 별도 / 전송 21:15",
        "작성·예약과 자동 전송이 서로 다른 시점의 사건이다.",
        "정확한 사망시각과 범인은 알 수 없다.",
        "MESSAGE_2115를 작업대에 놓고 포렌식 분석", ("CLAIM_MESSAGE_NOT_SURVIVAL",),
    ),
}

CLAIMS = {
    "CLAIM_MESSAGE_NOT_SURVIVAL": Claim(
        "CLAIM_MESSAGE_NOT_SURVIVAL", "수신 시각은 생존 시각이 아니다",
        "21시 15분 메시지는 예약 메시지의 수신 기록이며, 최종인의 21시 15분 생존을 증명하지 않는다.",
    ),
    "CLAIM_CONFIRMED_WINDOW": Claim(
        "CLAIM_CONFIRMED_WINDOW", "확인 시각과 사망시각을 구분한다",
        "19시 55분은 마지막 확실한 생존 확인이고 23시 20분은 발견시각이다. 두 기록만으로 정확한 사망시각은 확정되지 않는다.",
    ),
}

RELATIONS = {
    "RECEIPT_VS_SURVIVAL": "수신 시각과 생존 시각은 다르다",
    "LAST_SEEN_VS_DISCOVERY": "마지막 생존 확인과 발견 시각은 다르다",
    "SAME_EVENT": "두 자료는 같은 사건을 기록한다",
    "ONE_PROVES_OTHER": "앞 자료가 뒤 자료를 직접 증명한다",
}

CONNECTION_RULES = {
    (frozenset(("MESSAGE_2115", "MESSAGE_METADATA")), "RECEIPT_VS_SURVIVAL"): (
        "CONNECTION_MESSAGE_TIMING", "CLAIM_MESSAGE_NOT_SURVIVAL"
    ),
    (frozenset(("WITNESS_1955", "DISCOVERY_2320")), "LAST_SEEN_VS_DISCOVERY"): (
        "CONNECTION_CONFIRMED_WINDOW", "CLAIM_CONFIRMED_WINDOW"
    ),
}

FINAL_ANSWERS = {
    "last_confirmed_alive": "19:55",
    "message_proves": "AUTO_SENT_AT_2115",
    "possible_conclusion": "DEATH_TIME_REQUIRES_MORE_RECORDS",
}

PHASES = (
    "briefing",
    "initial_hypothesis",
    "inspect_message",
    "connect_message",
    "connect_window",
    "final_reconstruction",
    "complete",
)


def create_memory_state() -> MemoryState:
    return MemoryState()


def start_memory_scene(state: MemoryState) -> None:
    state.scene_started = True


def get_memory_phase(state: MemoryState) -> str:
    """저장된 검증 ID만으로 현재 장면 단계를 계산한다."""
    if state.completed:
        return "complete"
    if not state.scene_started:
        return "briefing"
    if state.initial_hypothesis_id is None:
        return "initial_hypothesis"
    if not state.forensic_complete:
        return "inspect_message"
    if "CLAIM_MESSAGE_NOT_SURVIVAL" not in state.unlocked_claim_ids:
        return "connect_message"
    if "CLAIM_CONFIRMED_WINDOW" not in state.unlocked_claim_ids:
        return "connect_window"
    return "final_reconstruction"


INITIAL_HYPOTHESES = {
    "ALIVE_AT_2115": "메시지를 직접 보냈으므로 21시 15분까지 살아 있었다",
    "DELIVERY_ONLY": "메시지가 21시 15분에 도착했다는 사실만 확실하다",
    "SOMEONE_ELSE_SENT": "다른 사람이 피해자의 기기로 메시지를 보냈다",
    "UNDECIDED": "작성·전송 기록을 보기 전에는 판단을 보류한다",
}


def record_initial_hypothesis(state: MemoryState, hypothesis_id: str) -> None:
    if state.initial_hypothesis_id is not None:
        raise ValueError("초기 판단은 이미 기록됐습니다.")
    if hypothesis_id not in INITIAL_HYPOTHESES:
        raise ValueError("등록되지 않은 초기 판단입니다.")
    state.initial_hypothesis_id = hypothesis_id


def set_workspace(state: MemoryState, evidence_ids: Iterable[str]) -> None:
    ids = list(dict.fromkeys(evidence_ids))
    if len(ids) > MAX_WORKSPACE_ITEMS:
        raise ValueError(f"작업대에는 최대 {MAX_WORKSPACE_ITEMS}개 자료만 놓을 수 있습니다.")
    if not set(ids).issubset(state.unlocked_evidence_ids):
        raise ValueError("잠겨 있거나 존재하지 않는 자료는 선택할 수 없습니다.")
    state.workspace_ids = ids


def can_run_message_forensics(state: MemoryState) -> bool:
    return "MESSAGE_2115" in state.workspace_ids and not state.forensic_complete


def run_message_forensics(state: MemoryState) -> Evidence:
    if not can_run_message_forensics(state):
        raise ValueError("MESSAGE_2115를 작업대에 놓아야 포렌식 분석을 실행할 수 있습니다.")
    state.forensic_complete = True
    if METADATA_ID not in state.unlocked_evidence_ids:
        state.unlocked_evidence_ids.append(METADATA_ID)
    return EVIDENCE[METADATA_ID]


def connect_workspace(state: MemoryState, relation_id: str) -> dict[str, object]:
    if relation_id not in RELATIONS:
        raise ValueError("등록되지 않은 관계 ID입니다.")
    if len(state.workspace_ids) != 2:
        return {"success": False, "message": "연결할 자료 두 개를 작업대에 놓아야 합니다."}
    rule = CONNECTION_RULES.get((frozenset(state.workspace_ids), relation_id))
    if rule is None:
        return {"success": False, "message": "이 관계로는 현재 기록의 공백을 해소할 수 없습니다."}
    connection_id, claim_id = rule
    if connection_id not in state.completed_connection_ids:
        state.completed_connection_ids.append(connection_id)
    if claim_id not in state.unlocked_claim_ids:
        state.unlocked_claim_ids.append(claim_id)
    return {"success": True, "message": CLAIMS[claim_id].explanation, "claim_id": claim_id}


def can_submit_reconstruction(state: MemoryState) -> bool:
    return set(CLAIMS).issubset(state.unlocked_claim_ids)


def submit_reconstruction(state: MemoryState, answers: dict[str, str]) -> dict[str, object]:
    if not can_submit_reconstruction(state):
        raise ValueError("두 핵심 주장을 먼저 기록해야 최종 재구성을 제출할 수 있습니다.")
    state.attempts += 1
    checks = {key: answers.get(key) == value for key, value in FINAL_ANSWERS.items()}
    solved = all(checks.values())
    if solved:
        state.completed = True
    return {"solved": solved, "checks": checks, "attempt": state.attempts}


def _validate_state(state: MemoryState) -> None:
    if (
        state.initial_hypothesis_id is not None
        and state.initial_hypothesis_id not in INITIAL_HYPOTHESES
    ):
        raise ValueError("등록되지 않은 초기 판단이 저장되어 있습니다.")
    if not set(state.unlocked_evidence_ids).issubset(EVIDENCE):
        raise ValueError("상태에 존재하지 않는 자료 ID가 있습니다.")
    if not set(state.workspace_ids).issubset(state.unlocked_evidence_ids):
        raise ValueError("작업대에 잠긴 자료가 있습니다.")
    if len(state.workspace_ids) > MAX_WORKSPACE_ITEMS:
        raise ValueError("작업대 선택 수가 제한을 초과했습니다.")
    if not set(state.unlocked_claim_ids).issubset(CLAIMS):
        raise ValueError("상태에 존재하지 않는 주장 ID가 있습니다.")
    allowed_connections = {rule[0] for rule in CONNECTION_RULES.values()}
    if not set(state.completed_connection_ids).issubset(allowed_connections):
        raise ValueError("상태에 존재하지 않는 연결 ID가 있습니다.")
    if state.forensic_complete != (METADATA_ID in state.unlocked_evidence_ids):
        raise ValueError("메시지 포렌식 상태와 메타데이터 해금 상태가 일치하지 않습니다.")
    claim_connections = {
        "CLAIM_MESSAGE_NOT_SURVIVAL": "CONNECTION_MESSAGE_TIMING",
        "CLAIM_CONFIRMED_WINDOW": "CONNECTION_CONFIRMED_WINDOW",
    }
    for claim_id, connection_id in claim_connections.items():
        if (claim_id in state.unlocked_claim_ids) != (
            connection_id in state.completed_connection_ids
        ):
            raise ValueError("핵심 주장과 완료된 연결 상태가 일치하지 않습니다.")
    if state.completed and not set(CLAIMS).issubset(state.unlocked_claim_ids):
        raise ValueError("필수 주장 없이 완료된 상태는 복원할 수 없습니다.")
    if not isinstance(state.attempts, int) or state.attempts < 0:
        raise ValueError("제출 횟수 상태가 올바르지 않습니다.")
