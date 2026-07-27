from unlock_manager import unlock_document


# 지금까지 완료한 조사 ID 저장
investigated = set()
investigation_log = []
INVESTIGATION_TITLES = {
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

    title = INVESTIGATION_TITLES.get(
        investigation_id,
        investigation_id
    )

    if title not in investigation_log:
        investigation_log.append(title)

# 조사 완료 처리
def add_investigation(investigation_id):

    # 이미 완료한 조사는 다시 기록하지 않음
    if investigation_id in investigated:
        return

    investigated.add(investigation_id)
    add_investigation_log(investigation_id)

    check_unlocks(investigation_id)


# 조사 ID와 해금할 문서를 연결
UNLOCK_RULES = {
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


# 완료된 조사에 대응하는 문서 해금
def check_unlocks(investigation_id):

    if investigation_id in UNLOCK_RULES:
        unlock_document(
            UNLOCK_RULES[investigation_id]
        )
            
    # 최종인이 왜 8년 뒤 다시 조사했는지 해금
    if (
        "DIGITAL_VICTIM_DEVICE_ACTIVITY" in investigated
        and "ARCHIVE_HAESUNG_BASIC" in investigated
        and "EVIDENCE_RESEARCH_TRIGGER" not in investigated
    ):
        investigated.add("EVIDENCE_RESEARCH_TRIGGER")
        unlock_document(
            "EVID_002_VICTIM_RESEARCH_TRIGGER.md"
        )

    # 사라진 USB의 진짜 의미 해금
    if (
        "DIGITAL_USB_TRACE" in investigated
        and "ARCHIVE_RESPONSIBILITY" in investigated
        and "EVIDENCE_USB_CONTEXT" not in investigated
    ):
        investigated.add("EVIDENCE_USB_CONTEXT")
        unlock_document(
            "EVID_001_MISSING_USB_CONTEXT.md"
        )

# 현재 조사 상태 복사본 반환
def get_investigated():
    return investigated.copy()

# 현재까지 완료한 조사 기록 출력
# 현재까지 완료한 조사 기록 출력
def show_investigation_log():

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