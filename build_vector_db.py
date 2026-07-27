from pathlib import Path
from dotenv import load_dotenv

from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import MarkdownHeaderTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma

load_dotenv()

# 1. available 폴더 안의 모든 .md 찾기
available_dir = Path("./data/available")
md_files = list(available_dir.glob("*.md"))

print("찾은 문서 개수:", len(md_files))

# 2. 모든 문서 로드
documents = []

for file_path in md_files:
    loader = TextLoader(
        str(file_path),
        encoding="utf-8"
    )

    loaded_docs = loader.load()

    for doc in loaded_docs:
        doc.metadata["source_file"] = file_path.name

    documents.extend(loaded_docs)

# 3. Markdown 구조 기준 청킹
headers_to_split_on = [
    ("#", "대제목"),
    ("##", "소제목"),
]

markdown_splitter = MarkdownHeaderTextSplitter(
    headers_to_split_on=headers_to_split_on
)

all_chunks = []

for doc in documents:
    chunks = markdown_splitter.split_text(doc.page_content)

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

        chunk.metadata["source_file"] = doc.metadata["source_file"]

    all_chunks.extend(chunks)

print("전체 Chunk 개수:", len(all_chunks))

# 4. Embedding 객체 생성
embeddings = OpenAIEmbeddings(
    model="text-embedding-3-small"
)

# 5. Vector DB 생성 + 디스크 저장
vectorstore = Chroma.from_documents(
    documents=all_chunks,
    embedding=embeddings,
    persist_directory="./chroma_db"
)

print("Vector DB 생성 및 저장 완료")