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
    schema_version: int = 1
    episode_id: str = "MESSAGE_2115"
    scene_started: bool = False
    initial_hypothesis_id: str | None = None
    forensic_request_attempt_ids: list[str] = field(default_factory=list)
    unlocked_evidence_ids: list[str] = field(default_factory=lambda: list(INITIAL_EVIDENCE_IDS))
    workspace_ids: list[str] = field(default_factory=list)
    unlocked_claim_ids: list[str] = field(default_factory=list)
    completed_connection_ids: list[str] = field(default_factory=list)
    connection_attempt_log: list[str] = field(default_factory=list)
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
        "MESSAGE_METADATA", "메시지 작업 이력 및 실행 로그",
        "작성 이벤트와 예약 등록은 최종인의 정상 기기 세션에서 21시 15분 이전에 완료됐다. 21시 15분 실행 주체는 사용자 계정이 아니라 예약발송 시스템이며, 등록 이후 본문 수정이나 외부 접속 흔적은 없다.",
        "객관 기록", ("최종인", "박소영"), "작성·예약 시각 별도 / 전송 21:15",
        "작성·예약과 자동 전송이 별개의 이벤트로 기록됐다.",
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

CONNECTION_FEEDBACK = {
    frozenset(("MESSAGE_2115", "MESSAGE_METADATA")): {
        "SAME_EVENT": "두 자료는 같은 메시지를 다루지만, 그것만으로 수신 시각이 생존 시각인지 설명되지는 않습니다.",
        "ONE_PROVES_OTHER": "메타데이터는 메시지의 존재가 아니라 생성과 전송 방식의 차이를 보여줍니다.",
        "LAST_SEEN_VS_DISCOVERY": "이 두 자료는 목격과 발견 기록이 아닙니다. 각 자료에 기록된 시각의 성격을 다시 비교하십시오.",
    },
    frozenset(("WITNESS_1955", "DISCOVERY_2320")): {
        "SAME_EVENT": "두 기록은 서로 다른 시점의 사건입니다. 하나는 대화이고 다른 하나는 시신 발견입니다.",
        "ONE_PROVES_OTHER": "19시 55분의 목격은 23시 20분 발견 전까지 계속 살아 있었다는 사실을 증명하지 않습니다.",
        "RECEIPT_VS_SURVIVAL": "이 자료에는 메시지 수신 기록이 없습니다. 마지막 생존 확인과 발견의 차이에 집중하십시오.",
    },
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
    "DELIVERY_ONLY": "확실한 것은 메시지가 21시 15분에 도착했다는 사실뿐이다",
    "SOMEONE_ELSE_SENT": "다른 사람이 피해자의 기기로 메시지를 보냈다",
    "UNDECIDED": "현재 정보만으로는 작성 방식과 시점을 판단할 수 없다",
}

FORENSIC_REQUESTS = {
    "CREATION_METADATA": {
        "label": "메시지 작업 이력 및 실행 로그",
        "success": True,
        "feedback": "작성, 예약 등록, 실제 전송이 각각 언제·어떤 주체로 실행됐는지 비교합니다.",
    },
    "DELIVERY_RECEIPT": {
        "label": "박소영 기기의 수신 확인서",
        "success": False,
        "feedback": "수신 확인서는 메시지가 도착했다는 사실만 반복합니다. 작성 시점과 조작 주체를 구분하지 못합니다.",
    },
    "WRITING_STYLE": {
        "label": "과거 업무 메시지와 문체 비교",
        "success": False,
        "feedback": "문체는 작성자를 추정하는 참고자료지만, 작성 시점이나 21시 15분의 실행 주체를 판별하는 기계 기록은 아닙니다.",
    },
    "CALL_HISTORY": {
        "label": "21시 전후 통화 내역",
        "success": False,
        "feedback": "통화 여부는 메시지가 생성되고 전송된 방식을 직접 설명하지 못합니다.",
    },
}


def record_initial_hypothesis(state: MemoryState, hypothesis_id: str) -> None:
    if state.initial_hypothesis_id is not None:
        raise ValueError("초기 판단은 이미 기록됐습니다.")
    if hypothesis_id not in INITIAL_HYPOTHESES:
        raise ValueError("등록되지 않은 초기 판단입니다.")
    state.initial_hypothesis_id = hypothesis_id


def request_message_forensics(
    state: MemoryState,
    request_id: str,
) -> dict[str, object]:
    if request_id not in FORENSIC_REQUESTS:
        raise ValueError("등록되지 않은 포렌식 요청입니다.")
    if "MESSAGE_2115" not in state.workspace_ids:
        raise ValueError("메시지 기록을 먼저 선택해야 합니다.")
    if request_id not in state.forensic_request_attempt_ids:
        state.forensic_request_attempt_ids.append(request_id)
    request = FORENSIC_REQUESTS[request_id]
    if not request["success"]:
        return {"success": False, "message": request["feedback"]}
    evidence = run_message_forensics(state)
    return {
        "success": True,
        "message": request["feedback"],
        "evidence_id": evidence.id,
    }


def set_workspace(state: MemoryState, evidence_ids: Iterable[str]) -> None:
    ids = list(dict.fromkeys(evidence_ids))
    if len(ids) > MAX_WORKSPACE_ITEMS:
        raise ValueError(f"작업대에는 최대 {MAX_WORKSPACE_ITEMS}개 자료만 놓을 수 있습니다.")
    if not set(ids).issubset(state.unlocked_evidence_ids):
        raise ValueError("잠겨 있거나 존재하지 않는 자료는 선택할 수 없습니다.")
    state.workspace_ids = ids


def can_run_message_forensics(state: MemoryState) -> bool:
    return (
        "MESSAGE_2115" in state.workspace_ids
        and "CREATION_METADATA" in state.forensic_request_attempt_ids
        and not state.forensic_complete
    )


def run_message_forensics(state: MemoryState) -> Evidence:
    if state.forensic_complete:
        raise ValueError("메시지 포렌식은 이미 완료됐습니다.")
    if "MESSAGE_2115" not in state.workspace_ids:
        raise ValueError("MESSAGE_2115를 작업대에 놓아야 포렌식 분석을 실행할 수 있습니다.")
    if "CREATION_METADATA" not in state.forensic_request_attempt_ids:
        raise ValueError(
            "메시지 생성·예약 작업 기록을 포렌식 대상으로 선택해야 합니다."
        )
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
        current_pair = frozenset(state.workspace_ids)
        if current_pair in CONNECTION_FEEDBACK:
            attempt_key = "+".join(sorted(state.workspace_ids)) + ":" + relation_id
            if attempt_key not in state.connection_attempt_log:
                state.connection_attempt_log.append(attempt_key)
        feedback = CONNECTION_FEEDBACK.get(
            current_pair,
            {},
        ).get(
            relation_id,
            "이 관계로는 현재 기록의 공백을 해소할 수 없습니다.",
        )
        return {"success": False, "message": feedback}
    connection_id, claim_id = rule
    if connection_id not in state.completed_connection_ids:
        state.completed_connection_ids.append(connection_id)
    if claim_id not in state.unlocked_claim_ids:
        state.unlocked_claim_ids.append(claim_id)
    return {"success": True, "message": CLAIMS[claim_id].explanation, "claim_id": claim_id}


def get_adaptive_hint(state: MemoryState, phase: str) -> str | None:
    """반복 실패 때만 정답을 직접 말하지 않는 단계형 힌트를 반환한다."""
    if phase == "inspect_message":
        wrong_count = sum(
            not FORENSIC_REQUESTS[item]["success"]
            for item in state.forensic_request_attempt_ids
        )
        if wrong_count >= 2:
            return "도착 여부를 재확인하기보다 작성·예약·전송을 서로 다른 이벤트로 나눌 수 있는 기록이 필요합니다."
        if wrong_count == 1:
            return "서로 다른 설명이 각기 다른 결과를 남기는 기록이 무엇인지 생각해 보십시오."
        return None
    pair_ids = {
        "connect_message": {"MESSAGE_2115", "MESSAGE_METADATA"},
        "connect_window": {"WITNESS_1955", "DISCOVERY_2320"},
    }
    if phase not in pair_ids:
        return None
    prefix = "+".join(sorted(pair_ids[phase])) + ":"
    wrong_count = sum(item.startswith(prefix) for item in state.connection_attempt_log)
    if wrong_count >= 2 and phase == "connect_message":
        return "21시 15분에 실행된 행위와 그보다 먼저 완료된 행위를 구분하십시오."
    if wrong_count >= 2 and phase == "connect_window":
        return "살아 있음을 확인한 시각과 사망을 발견한 시각 사이의 공백은 그 자체로 채워지지 않습니다."
    if wrong_count == 1:
        return "두 카드가 각각 확정하는 사건의 종류와 시각을 따로 읽어 보십시오."
    return None


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
    feedback = {
        "last_confirmed_alive": "메시지 수신은 직접 목격이 아닙니다. 사람이 최종인을 마지막으로 직접 확인한 기록을 다시 찾으십시오.",
        "message_proves": "이 기록이 확정하는 것은 21시 15분의 실행 방식입니다. 그 시각의 생존이나 전송자의 범행까지 확장할 수 없습니다.",
        "possible_conclusion": "현재 기록은 잘못된 생존 하한선만 제거합니다. 정확한 사망시각과 범인은 다음 기록 없이는 확정할 수 없습니다.",
    }
    return {
        "solved": solved,
        "checks": checks,
        "feedback": [feedback[key] for key, correct in checks.items() if not correct],
        "attempt": state.attempts,
    }


def _validate_state(state: MemoryState) -> None:
    if state.schema_version != 1:
        raise ValueError("지원하지 않는 기억 복원 저장 버전입니다.")
    if state.episode_id != "MESSAGE_2115":
        raise ValueError("다른 에피소드의 저장 상태는 불러올 수 없습니다.")
    if (
        state.initial_hypothesis_id is not None
        and state.initial_hypothesis_id not in INITIAL_HYPOTHESES
    ):
        raise ValueError("등록되지 않은 초기 판단이 저장되어 있습니다.")
    if not set(state.forensic_request_attempt_ids).issubset(FORENSIC_REQUESTS):
        raise ValueError("등록되지 않은 포렌식 요청이 저장되어 있습니다.")
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
    valid_attempts = {
        "+".join(sorted(pair)) + ":" + relation
        for pair in (
            {"MESSAGE_2115", "MESSAGE_METADATA"},
            {"WITNESS_1955", "DISCOVERY_2320"},
        )
        for relation in RELATIONS
    }
    if not set(state.connection_attempt_log).issubset(valid_attempts):
        raise ValueError("등록되지 않은 연결 시도가 저장되어 있습니다.")
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
