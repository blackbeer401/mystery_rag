# RAG DOCUMENT SPEC v1

> 제작자 전용 문서. Vector DB에 넣지 않는다.

## 1. 기준

- 사건의 유일한 정답 기준은 `CASE_MASTER_v2.md`다.
- 플레이어용 RAG 문서는 `data/available`과 `data/locked`의 32개 문서로 고정한다.
- `CASE_MASTER_v1.md`, `CASE_MASTER_v2.md`, 이 문서는 RAG에서 제외한다.
- 한 문서는 하나의 조사 결과 또는 하나의 증거 해석만 담당한다.
- 문서는 범인을 직접 선언하지 않고, 증명하는 사실과 증명하지 못하는 사실을 함께 제시한다.
- TRUE END 뒤에 확인되는 USB 압수 결과는 RAG 문서에 넣지 않는다.

## 2. 최초 공개 문서 — 5개

| 파일 | 역할 | 공개 범위 |
|---|---|---|
| `CUR_001_CASE_OVERVIEW.md` | 사건·발견 개요 | 피해자, 장소, 발견시각 |
| `CUR_002_CHARACTER_OVERVIEW.md` | 주요 인물 소개 | 관계와 표면적 이해관계 |
| `CUR_003_INITIAL_TIMELINE.md` | 초기 시간표 | 21:15 메시지와 발견 흐름 |
| `CUR_004_INITIAL_STATEMENTS.md` | 초기 진술 요약 | 검증 전 주장 |
| `CUR_005_HAESUNG_OFFICIAL_SUMMARY.md` | 해성호 공식 설명 | 공식 책임구조와 한계 |

## 3. 조사 후 공개 문서 — 27개

### 1장: 객실에 남은 흔적

- `SCENE_001_CABIN_INSPECTION.md`: 객실 출입문과 실내 흔적, 해석의 한계
- `FORENSIC_001_POSTMORTEM.md`: 경부 압박 사망과 법의학적 한계
- `SCENE_002_DISCOVERY_RECONSTRUCTION.md`: 신고부터 객실 개방까지의 발견 흐름

### 2장: 네 사람의 진술

- `INT_001_KIMDONGYUL_BASIC.md`
- `INT_002_KIMDONGYUL_DEEP.md`
- `INT_003_KIMHYUNJUN_BASIC.md`
- `INT_004_KIMHYUNJUN_DEEP.md`
- `INT_005_KANGWONMO_BASIC.md`
- `INT_006_KANGWONMO_FOLLOWUP.md`
- `INT_007_PARKSOYOUNG.md`
- `WIT_001_KIMDONGYUL_CORRIDOR.md`
- `WIT_002_KIMHYUNJUN_ARGUMENT.md`
- `WIT_004_KIMHYUNJUN_MOVEMENT.md`

### 3장: 존재하지 않는 21시 15분

- `WIT_003_LAST_CONFIRMED_ALIVE.md`: 약 19:55 마지막 생존 확인
- `DIGITAL_001_MESSAGE_FORENSICS.md`: 피해자가 생전에 설정한 예약발송

### 4장: 객실 밖의 76분

- `ACCESS_001_KANGWONMO_RAW.md`: 19:20·20:36 ENTRY
- `ACCESS_002_CABIN_SYSTEM.md`: 퇴실기록이 남지 않는 구조
- `TIMELINE_001_ALIBI_ANALYSIS.md`: 용의자별 가능시간 종합

### 5장: 8년 전의 침묵

- `ARC_001_HAESUNG_TECHNICAL_RECORD.md`
- `DEEP_001_TECHNICAL_RISK.md`
- `DEEP_002_INFORMATION_FLOW.md`
- `DEEP_003_RESPONSIBILITY_RECONSTRUCTION.md`
- `DEEP_004_VICTIM_ANALYSIS.md`
- `DIGITAL_002_USB_TRACE.md`
- `DIGITAL_003_VICTIM_DEVICE_ACTIVITY.md`
- `EVID_001_MISSING_USB_CONTEXT.md`
- `EVID_002_VICTIM_RESEARCH_TRIGGER.md`

### 6장: 마지막 기록

- 신규 사실 문서를 추가하지 않는다.
- 앞서 해금된 기록을 결합해 범인, 범행 가능시간, 동기, USB 의미를 추리한다.
- USB 실물 발견은 TRUE END 에필로그에서만 공개한다.

## 4. 확정된 누설 방지선

- 1~2장: 예약발송의 포렌식 결론, 강원모 출입 공백, 해성호 왜곡 구조를 확정하지 않는다.
- 3장: 21:15 생존 가설만 제거하며 범인이나 정확한 사망시각을 확정하지 않는다.
- 4장: 강원모의 알리바이가 성립하지 않음을 밝히되 피해자 객실 방문을 직접 증명하지 않는다.
- 5장: 동기와 USB 의미를 밝히되 강원모의 살인을 단일 문서로 선언하지 않는다.
- 6장: 여러 독립 단서를 플레이어가 결합해야만 정답에 도달한다.

## 5. 검색 비용 원칙

- Markdown 제목 단위로 청킹한다.
- 벡터 검색 폭은 50개로 유지해 공용 DB의 잠긴 문서 사이에서도 허용 문서를 찾는다.
- 권한 필터 후 재정렬 프롬프트에는 최대 12개 후보만 전달한다.
- 최종 답변 컨텍스트에는 최대 3개 조각만 전달한다.
- 동일 사실을 설명하기 위한 신규 중복 문서를 만들지 않는다.
