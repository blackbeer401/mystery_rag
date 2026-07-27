from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()


# 저장된 Vector DB 불러오기
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

vectorstore = Chroma(
    persist_directory="./chroma_db",
    embedding_function=embeddings
)


def unlock_document(file_name):

    # 1. 해금할 문서 경로
    file_path = Path("./data/locked") / file_name

    # 문서가 실제로 존재하는지 확인
    if not file_path.exists():
        print("해당 locked 문서를 찾을 수 없습니다.")
        return

    # 2. 이미 DB에 들어있는 문서인지 확인
    existing = vectorstore.get(
        where={"source_file": file_name}
    )

    if existing["ids"]:
        return

    # 3. locked 문서 로드
    loader = TextLoader(
        str(file_path),
        encoding="utf-8"
    )

    documents = loader.load()

    # 4. Markdown 기준 청킹
    headers_to_split_on = [
        ("#", "대제목"),
        ("##", "소제목"),
    ]

    markdown_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=headers_to_split_on
    )

    chunks = markdown_splitter.split_text(
        documents[0].page_content
    )

    # 5. Markdown 제목을 검색용 본문에도 포함
    for chunk in chunks:

        title_parts = []

        if "대제목" in chunk.metadata:
            title_parts.append(
                chunk.metadata["대제목"]
            )

        if "소제목" in chunk.metadata:
            title_parts.append(
                chunk.metadata["소제목"]
            )

        if title_parts:
            title_text = " / ".join(title_parts)

            chunk.page_content = (
                title_text
                + "\n"
                + chunk.page_content
            )

        # 원본 파일명 metadata 추가
        chunk.metadata["source_file"] = file_name

    # 6. 새 문서의 Chunk만 기존 DB에 추가
    vectorstore.add_documents(chunks)

