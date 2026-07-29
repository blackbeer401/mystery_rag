"""CASE MASTER와 플레이어용 RAG 문서 세트의 정적 안전검사."""

from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parent
AVAILABLE_DIR = ROOT / "data" / "available"
LOCKED_DIR = ROOT / "data" / "locked"

EXPECTED_AVAILABLE = {
    "CUR_001_CASE_OVERVIEW.md",
    "CUR_002_CHARACTER_OVERVIEW.md",
    "CUR_003_INITIAL_TIMELINE.md",
    "CUR_004_INITIAL_STATEMENTS.md",
    "CUR_005_HAESUNG_OFFICIAL_SUMMARY.md",
}

EXPECTED_LOCKED = {
    "ACCESS_001_KANGWONMO_RAW.md",
    "ACCESS_002_CABIN_SYSTEM.md",
    "ARC_001_HAESUNG_TECHNICAL_RECORD.md",
    "DEEP_001_TECHNICAL_RISK.md",
    "DEEP_002_INFORMATION_FLOW.md",
    "DEEP_003_RESPONSIBILITY_RECONSTRUCTION.md",
    "DEEP_004_VICTIM_ANALYSIS.md",
    "DIGITAL_001_MESSAGE_FORENSICS.md",
    "DIGITAL_002_USB_TRACE.md",
    "DIGITAL_003_VICTIM_DEVICE_ACTIVITY.md",
    "EVID_001_MISSING_USB_CONTEXT.md",
    "EVID_002_VICTIM_RESEARCH_TRIGGER.md",
    "FORENSIC_001_POSTMORTEM.md",
    "SCENE_001_CABIN_INSPECTION.md",
    "SCENE_002_DISCOVERY_RECONSTRUCTION.md",
    "INT_001_KIMDONGYUL_BASIC.md",
    "INT_002_KIMDONGYUL_DEEP.md",
    "INT_003_KIMHYUNJUN_BASIC.md",
    "INT_004_KIMHYUNJUN_DEEP.md",
    "INT_005_KANGWONMO_BASIC.md",
    "INT_006_KANGWONMO_FOLLOWUP.md",
    "INT_007_PARKSOYOUNG.md",
    "TIMELINE_001_ALIBI_ANALYSIS.md",
    "WIT_001_KIMDONGYUL_CORRIDOR.md",
    "WIT_002_KIMHYUNJUN_ARGUMENT.md",
    "WIT_003_LAST_CONFIRMED_ALIVE.md",
    "WIT_004_KIMHYUNJUN_MOVEMENT.md",
}

REJECTED_NAMES = {
    "윤태성",
    "강민혁",
    "한동욱",
    "한서진",
    "최도윤",
}


def markdown_names(directory):
    return {
        path.name
        for path in directory.glob("*.md")
    }


def fail(errors, message):
    errors.append(message)


def main():
    errors = []
    actual_available = markdown_names(AVAILABLE_DIR)
    actual_locked = markdown_names(LOCKED_DIR)

    if actual_available != EXPECTED_AVAILABLE:
        fail(
            errors,
            "available 문서 세트 불일치: "
            f"누락={sorted(EXPECTED_AVAILABLE - actual_available)}, "
            f"추가={sorted(actual_available - EXPECTED_AVAILABLE)}",
        )

    if actual_locked != EXPECTED_LOCKED:
        fail(
            errors,
            "locked 문서 세트 불일치: "
            f"누락={sorted(EXPECTED_LOCKED - actual_locked)}, "
            f"추가={sorted(actual_locked - EXPECTED_LOCKED)}",
        )

    game_state_text = (
        ROOT / "game_state.py"
    ).read_text(encoding="utf-8")
    referenced_locked = set(
        re.findall(
            r'"([A-Z0-9_]+\.md)"',
            game_state_text,
        )
    )
    if referenced_locked != EXPECTED_LOCKED:
        fail(
            errors,
            "코드의 문서 해금 연결 불일치: "
            f"연결 누락={sorted(EXPECTED_LOCKED - referenced_locked)}, "
            f"존재하지 않는 연결={sorted(referenced_locked - EXPECTED_LOCKED)}",
        )

    all_documents = sorted(
        list(AVAILABLE_DIR.glob("*.md"))
        + list(LOCKED_DIR.glob("*.md"))
    )
    combined_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in all_documents
    )

    for rejected_name in REJECTED_NAMES:
        if rejected_name in combined_text:
            fail(errors, f"폐기 인물명이 RAG 문서에 존재: {rejected_name}")

    forbidden_epilogue_patterns = {
        "개인 수하물": r"개인\s*수하물",
        "별도 파우치": r"별도\s*파우치",
        "압수수색 USB 발견": r"압수수색.{0,40}USB|USB.{0,40}압수수색",
    }
    for label, pattern in forbidden_epilogue_patterns.items():
        if re.search(pattern, combined_text, flags=re.IGNORECASE | re.DOTALL):
            fail(errors, f"TRUE END 전용 정보가 RAG 문서에 존재: {label}")

    message_text = (
        LOCKED_DIR / "DIGITAL_001_MESSAGE_FORENSICS.md"
    ).read_text(encoding="utf-8")
    if "최종인이 생전에 미리 작성" not in message_text:
        fail(errors, "21:15 메시지의 작성 주체가 확정 문구와 다름")

    access_text = (
        LOCKED_DIR / "ACCESS_002_CABIN_SYSTEM.md"
    ).read_text(encoding="utf-8")
    if "피해자 객실을 방문했다고 판단할 수도 없다" not in access_text:
        fail(errors, "출입기록의 증명 한계 문구 누락")

    usb_text = (
        LOCKED_DIR / "EVID_001_MISSING_USB_CONTEXT.md"
    ).read_text(encoding="utf-8")
    if "유일한 원본이라기보다" not in usb_text:
        fail(errors, "USB가 유일 원본이 아니라는 확정 문구 누락")

    total_chars = sum(
        len(path.read_text(encoding="utf-8"))
        for path in all_documents
    )

    if errors:
        print("RAG 문서 검사 실패")
        for error in errors:
            print(f"- {error}")
        return 1

    print("RAG 문서 검사 통과")
    print(f"- 최초 공개: {len(actual_available)}개")
    print(f"- 조사 해금: {len(actual_locked)}개")
    print(f"- 전체 문자 수: {total_chars:,}자")
    print(f"- 대략적 전체 토큰 상한: {total_chars // 2:,} 토큰")
    print("- CASE MASTER 및 TRUE END 정보 누설: 없음")
    return 0


if __name__ == "__main__":
    sys.exit(main())
