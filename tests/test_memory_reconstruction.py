import json
import unittest

from memory_echo import SAFE_RESPONSE, analyze_hypothesis, validate_echo_response
from memory_story import CASE_TITLE, ECHO_PROFILE, GAME_TITLE, PROLOGUE_BEATS, STORY_BEATS
from memory_reconstruction import (
    INITIAL_EVIDENCE_IDS, MemoryState, can_submit_reconstruction,
    connect_workspace, create_memory_state, run_message_forensics,
    set_workspace, start_memory_scene, submit_reconstruction,
    get_memory_phase, record_initial_hypothesis,
)


class MemoryEngineTests(unittest.TestCase):
    def test_story_foundation_is_complete(self):
        self.assertEqual(GAME_TITLE, "기억의 증언")
        self.assertEqual(CASE_TITLE, "해성호의 마지막 기록")
        self.assertEqual([beat["time"] for beat in PROLOGUE_BEATS], ["22:30", "23:05", "23:20"])
        self.assertEqual(set(STORY_BEATS), {
            "briefing", "initial_hypothesis", "inspect_message", "connect_message",
            "connect_window", "final_reconstruction", "complete",
        })
        self.assertIn("기억은 기록이 아닙니다", ECHO_PROFILE["principle"])

    def test_initial_unlocks_are_exact(self):
        state = create_memory_state()
        self.assertEqual(tuple(state.unlocked_evidence_ids), INITIAL_EVIDENCE_IDS)
        self.assertNotIn("MESSAGE_METADATA", state.unlocked_evidence_ids)

    def test_story_phase_follows_validated_progress(self):
        state = create_memory_state()
        self.assertEqual(get_memory_phase(state), "briefing")
        start_memory_scene(state)
        self.assertEqual(get_memory_phase(state), "initial_hypothesis")
        record_initial_hypothesis(state, "UNDECIDED")
        self.assertEqual(get_memory_phase(state), "inspect_message")
        set_workspace(state, ["MESSAGE_2115"])
        run_message_forensics(state)
        self.assertEqual(get_memory_phase(state), "connect_message")
        set_workspace(state, ["MESSAGE_2115", "MESSAGE_METADATA"])
        connect_workspace(state, "RECEIPT_VS_SURVIVAL")
        self.assertEqual(get_memory_phase(state), "connect_window")
        set_workspace(state, ["WITNESS_1955", "DISCOVERY_2320"])
        connect_workspace(state, "LAST_SEEN_VS_DISCOVERY")
        self.assertEqual(get_memory_phase(state), "final_reconstruction")

    def test_locked_metadata_cannot_be_selected(self):
        with self.assertRaises(ValueError):
            set_workspace(create_memory_state(), ["MESSAGE_METADATA"])

    def test_message_required_for_forensics(self):
        state = create_memory_state()
        set_workspace(state, ["WITNESS_1955"])
        with self.assertRaises(ValueError):
            run_message_forensics(state)
        set_workspace(state, ["MESSAGE_2115"])
        run_message_forensics(state)
        self.assertIn("MESSAGE_METADATA", state.unlocked_evidence_ids)

    def test_workspace_limit(self):
        with self.assertRaises(ValueError):
            set_workspace(create_memory_state(), [*INITIAL_EVIDENCE_IDS])

    def test_wrong_connection_does_not_progress(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115", "ABSENCE_2230"])
        result = connect_workspace(state, "SAME_EVENT")
        self.assertFalse(result["success"])
        self.assertEqual(state.unlocked_claim_ids, [])

    def test_only_two_correct_connections_record_claims(self):
        state = self._state_with_claims()
        self.assertEqual(set(state.unlocked_claim_ids), {
            "CLAIM_MESSAGE_NOT_SURVIVAL", "CLAIM_CONFIRMED_WINDOW"
        })

    def test_final_is_locked_and_wrong_answer_can_retry(self):
        state = create_memory_state()
        self.assertFalse(can_submit_reconstruction(state))
        with self.assertRaises(ValueError):
            submit_reconstruction(state, {})
        state = self._state_with_claims()
        wrong = submit_reconstruction(state, {})
        self.assertFalse(wrong["solved"])
        self.assertFalse(state.completed)
        right = submit_reconstruction(state, {
            "last_confirmed_alive": "19:55",
            "message_proves": "AUTO_SENT_AT_2115",
            "possible_conclusion": "DEATH_TIME_REQUIRES_MORE_RECORDS",
        })
        self.assertTrue(right["solved"])
        self.assertTrue(state.completed)
        self.assertEqual(state.attempts, 2)

    def test_json_round_trip(self):
        state = self._state_with_claims()
        restored = MemoryState.from_json(state.to_json())
        self.assertEqual(json.loads(restored.to_json()), json.loads(state.to_json()))

    def test_inconsistent_serialized_state_is_rejected(self):
        invalid = create_memory_state().to_json()
        data = json.loads(invalid)
        data["forensic_complete"] = True
        with self.assertRaises(ValueError):
            MemoryState.from_json(json.dumps(data))

        data = json.loads(invalid)
        data["completed"] = True
        with self.assertRaises(ValueError):
            MemoryState.from_json(json.dumps(data))

    def _state_with_claims(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        run_message_forensics(state)
        set_workspace(state, ["MESSAGE_2115", "MESSAGE_METADATA"])
        connect_workspace(state, "RECEIPT_VS_SURVIVAL")
        set_workspace(state, ["WITNESS_1955", "DISCOVERY_2320"])
        connect_workspace(state, "LAST_SEEN_VS_DISCOVERY")
        return state


class MemoryEchoSafetyTests(unittest.TestCase):
    def test_locked_or_unknown_source_is_rejected(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        value = {
            **SAFE_RESPONSE,
            "summary": "bad",
            "source_ids": ["MESSAGE_METADATA"],
        }
        self.assertEqual(validate_echo_response(state, value), SAFE_RESPONSE)

    def test_culprit_question_stays_in_scope(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        result = analyze_hypothesis(state, "범인이 누구야?")
        self.assertIn("판단할 수 없습니다", result["summary"])
        self.assertEqual(result["source_ids"], ["MESSAGE_2115"])

    def test_api_failure_is_safe(self):
        class BrokenResponses:
            def create(self, **kwargs):
                raise RuntimeError("offline")
        class BrokenClient:
            responses = BrokenResponses()
        result = analyze_hypothesis(create_memory_state(), "메시지 가설", BrokenClient())
        self.assertEqual(result, SAFE_RESPONSE)

    def test_ai_receives_only_workspace_sources_and_cannot_mutate_state(self):
        class Response:
            output_text = json.dumps({
                **SAFE_RESPONSE,
                "summary": "선택 자료만 검토",
                "source_ids": ["MESSAGE_2115"],
            })

        class CapturingResponses:
            def __init__(self):
                self.kwargs = None

            def create(self, **kwargs):
                self.kwargs = kwargs
                return Response()

        class CapturingClient:
            def __init__(self):
                self.responses = CapturingResponses()

        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        before = state.to_json()
        client = CapturingClient()
        result = analyze_hypothesis(state, "예약 메시지일 수 있다", client)
        prompt = json.loads(client.responses.kwargs["input"])
        self.assertEqual(
            [item["id"] for item in prompt["allowed_sources"]],
            ["MESSAGE_2115"],
        )
        self.assertNotIn("MESSAGE_METADATA", client.responses.kwargs["input"])
        self.assertEqual(result["source_ids"], ["MESSAGE_2115"])
        self.assertEqual(state.to_json(), before)

    def test_message_claim_variations_are_structured_the_same(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        variations = (
            "21:15 메시지는 생존 증거가 아니다",
            "메시지가 왔다고 그때 살아 있었다는 뜻이 아니야",
            "예약 메시지가 21시 15분에 자동 전송됐다",
        )
        structured = [analyze_hypothesis(state, text)["supported_claim_ids"] for text in variations]
        self.assertEqual(structured, [["CLAIM_MESSAGE_NOT_SURVIVAL"]] * 3)


if __name__ == "__main__":
    unittest.main()
