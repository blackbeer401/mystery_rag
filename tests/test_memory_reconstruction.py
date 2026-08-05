import json
import unittest

from memory_echo import SAFE_RESPONSE, analyze_hypothesis, validate_echo_response
from memory_story import (
    CASE_TITLE, ECHO_PROFILE, GAME_TITLE, INITIAL_HYPOTHESIS_RESPONSES,
    NEXT_RECORD_TEASER, PLAYER_GUIDES,
    PROLOGUE_BEATS, STORY_BEATS,
)
from memory_reconstruction import (
    FORENSIC_REQUESTS, INITIAL_EVIDENCE_IDS, MemoryState, can_submit_reconstruction,
    connect_workspace, create_memory_state, run_message_forensics,
    set_workspace, start_memory_scene, submit_reconstruction,
    get_adaptive_hint, get_memory_phase, record_initial_hypothesis,
    request_message_forensics,
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
        self.assertEqual(NEXT_RECORD_TEASER["time"], "20:50대")
        self.assertNotIn("김동율", NEXT_RECORD_TEASER["body"])
        self.assertIn("미검증", NEXT_RECORD_TEASER["status"])
        self.assertEqual(
            set(INITIAL_HYPOTHESIS_RESPONSES),
            {"ALIVE_AT_2115", "DELIVERY_ONLY", "SOMEONE_ELSE_SENT", "UNDECIDED"},
        )
        self.assertEqual(
            set(PLAYER_GUIDES),
            {"briefing", "initial_hypothesis", "inspect_message", "connect_message"},
        )
        self.assertTrue(all(
            set(guide) == {"step", "action", "reason", "rule"}
            for guide in PLAYER_GUIDES.values()
        ))
        guide_text = " ".join(
            text for guide in PLAYER_GUIDES.values() for text in guide.values()
        )
        self.assertNotIn("예약", guide_text)
        self.assertNotIn("범인", guide_text)

    def test_initial_unlocks_are_exact(self):
        state = create_memory_state()
        self.assertEqual(tuple(state.unlocked_evidence_ids), INITIAL_EVIDENCE_IDS)
        self.assertNotIn("MESSAGE_METADATA", state.unlocked_evidence_ids)
        self.assertNotIn("예약", FORENSIC_REQUESTS["CREATION_METADATA"]["label"])

    def test_story_phase_follows_validated_progress(self):
        state = create_memory_state()
        self.assertEqual(get_memory_phase(state), "briefing")
        start_memory_scene(state)
        self.assertEqual(get_memory_phase(state), "initial_hypothesis")
        record_initial_hypothesis(state, "UNDECIDED")
        self.assertEqual(get_memory_phase(state), "inspect_message")
        set_workspace(state, ["MESSAGE_2115"])
        request_message_forensics(state, "CREATION_METADATA")
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
        with self.assertRaisesRegex(ValueError, "작업대"):
            run_message_forensics(state)
        with self.assertRaisesRegex(ValueError, "먼저 선택"):
            request_message_forensics(state, "CREATION_METADATA")
        set_workspace(state, ["MESSAGE_2115"])
        with self.assertRaisesRegex(ValueError, "생성·예약"):
            run_message_forensics(state)
        wrong = request_message_forensics(state, "DELIVERY_RECEIPT")
        self.assertFalse(wrong["success"])
        self.assertFalse(state.forensic_complete)
        right = request_message_forensics(state, "CREATION_METADATA")
        self.assertTrue(right["success"])
        self.assertIn("MESSAGE_METADATA", state.unlocked_evidence_ids)
        with self.assertRaisesRegex(ValueError, "이미 완료"):
            run_message_forensics(state)

    def test_workspace_limit(self):
        with self.assertRaises(ValueError):
            set_workspace(create_memory_state(), [*INITIAL_EVIDENCE_IDS])

    def test_wrong_connection_does_not_progress(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115", "ABSENCE_2230"])
        result = connect_workspace(state, "SAME_EVENT")
        self.assertFalse(result["success"])
        self.assertEqual(state.unlocked_claim_ids, [])
        self.assertIn("현재 기록", result["message"])

    def test_wrong_relations_explain_different_reasoning_gaps(self):
        state = create_memory_state()
        set_workspace(state, ["WITNESS_1955", "DISCOVERY_2320"])
        messages = {
            connect_workspace(state, relation)["message"]
            for relation in ("SAME_EVENT", "ONE_PROVES_OTHER", "RECEIPT_VS_SURVIVAL")
        }
        self.assertEqual(len(messages), 3)
        self.assertEqual(state.unlocked_claim_ids, [])
        self.assertEqual(len(state.connection_attempt_log), 3)
        self.assertIn("공백", get_adaptive_hint(state, "connect_window"))

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
        self.assertEqual(len(wrong["feedback"]), 3)
        self.assertFalse(state.completed)
        right = submit_reconstruction(state, {
            "last_confirmed_alive": "19:55",
            "message_proves": "AUTO_SENT_AT_2115",
            "possible_conclusion": "DEATH_TIME_REQUIRES_MORE_RECORDS",
        })
        self.assertTrue(right["solved"])
        self.assertTrue(state.completed)
        self.assertEqual(state.attempts, 2)

    def test_connection_scene_does_not_state_the_answer_first(self):
        scene = " ".join(line for _, line in STORY_BEATS["connect_message"]["lines"])
        self.assertNotIn("예약 메시지였다고요", scene)
        self.assertNotIn("생존 확인이 아니", scene)

    def test_pre_forensic_guidance_does_not_reveal_scheduled_delivery(self):
        guidance = " ".join(INITIAL_HYPOTHESIS_RESPONSES.values())
        wrong_feedback = " ".join(
            item["feedback"] for item in FORENSIC_REQUESTS.values() if not item["success"]
        )
        self.assertNotIn("예약", guidance)
        self.assertNotIn("자동", guidance)
        self.assertNotIn("예약", wrong_feedback)

    def test_json_round_trip(self):
        state = self._state_with_claims()
        restored = MemoryState.from_json(state.to_json())
        self.assertEqual(json.loads(restored.to_json()), json.loads(state.to_json()))
        self.assertEqual(restored.schema_version, 1)
        self.assertEqual(restored.episode_id, "MESSAGE_2115")

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

    def test_saved_progress_keeps_initial_player_judgment(self):
        state = create_memory_state()
        start_memory_scene(state)
        record_initial_hypothesis(state, "ALIVE_AT_2115")
        restored = MemoryState.from_json(state.to_json())
        self.assertEqual(restored.initial_hypothesis_id, "ALIVE_AT_2115")
        self.assertEqual(get_memory_phase(restored), "inspect_message")

    def _state_with_claims(self):
        state = create_memory_state()
        set_workspace(state, ["MESSAGE_2115"])
        request_message_forensics(state, "CREATION_METADATA")
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
        self.assertNotIn("does_not_prove", client.responses.kwargs["input"])
        self.assertEqual(prompt["allowed_claim_ids"], [])
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
        before_unlock = analyze_hypothesis(state, variations[0])
        self.assertEqual(before_unlock["supported_claim_ids"], [])
        request_message_forensics(state, "CREATION_METADATA")
        set_workspace(state, ["MESSAGE_2115", "MESSAGE_METADATA"])
        connect_workspace(state, "RECEIPT_VS_SURVIVAL")
        structured = [analyze_hypothesis(state, text)["supported_claim_ids"] for text in variations]
        self.assertEqual(structured, [["CLAIM_MESSAGE_NOT_SURVIVAL"]] * 3)


if __name__ == "__main__":
    unittest.main()
