#  해성호의 마지막 기록

LLM, RAG, LangChain, Tool Calling을 활용한 AI 추리 사건 분석 게임

---

## 📖 프로젝트 소개

**해성호의 마지막 기록**은 사용자가 탐정이 되어 크루즈에서 발생한 살인 사건을 조사하는 AI 기반 추리 게임입니다.

단순한 챗봇이 아니라 RAG를 활용한 문서 검색과 Tool Calling을 결합하여,
조사 결과에 따라 새로운 문서가 해금되고 게임의 진행 상태가 변화하는 구조로 설계하였습니다.

---

##  프로젝트 목표

- RAG 기반 문서 검색 구현
- Tool Calling을 활용한 조사 시스템 구현
- LangChain을 활용한 AI 파이프라인 구축
- 게임 상태(State)를 활용한 추리 진행 시스템 구현

---

## 🛠 사용 기술

- Python
- OpenAI API
- LangChain
- ChromaDB
- Streamlit
- Git / GitHub

---

##  주요 기능

- 사건 관련 문서 검색(RAG)
- Tool Calling 기반 조사
- 조사 결과에 따른 문서 해금
- 게임 상태 관리
- 최종 범인 추리

---

##  프로젝트 구조

```
app.py            # Streamlit UI
game.py           # 게임 로직 및 LLM
game_state.py     # 조사 상태 관리
build_vector_db.py# Vector DB 생성
documents/        # 사건 문서
```

---

##  실행 방법

```bash
pip install -r requirements.txt
streamlit run app.py
```

---

##  AI 활용

프로젝트 구현 과정에서 ChatGPT를 활용하여 코드 리뷰, 오류 분석, 구조 설계 검토 및 문서 작성에 도움을 받았습니다.

프로젝트의 설계 이해, 기능 구현, 테스트 및 수정은 직접 수행하였습니다.
