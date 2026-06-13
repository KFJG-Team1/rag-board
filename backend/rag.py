import os
from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document

import hashlib

from backend.db import (
    RagDocument,
    delete_rag_document,
    insert_rag_document,
    select_board,
    select_comment,
    select_post,
    select_rag_document,
    select_team,
    select_team_member,
    select_user,
)
from sqlalchemy.orm import Session


def user_to_document(user):
    profile = user.profile

    profile_lines = []
    metadata = {
        "source_type": "student_profile",
        "user_id": user.id,
        "classroom": user.classroom,
    }

    if profile is not None:
        metadata["profile_id"] = profile.id
        profile_lines = [
            f"실력 점수: {profile.score}",
            f"프로젝트 경험 수: {profile.project_count}",
            f"관심 분야: {profile.interests or '미입력'}",
            f"자기소개: {profile.self_intro or '미입력'}",
            f"피하고 싶은 조건: {profile.avoid_condition or '미입력'}",
        ]

    page_content = "\n".join(
        [
            f"학생 이름: {user.name}",
            f"반: {user.classroom}",
            f"전화번호: {user.phone_num or '미입력'}",
            *profile_lines,
        ]
    )

    return Document(page_content=page_content, metadata=metadata)


def post_to_document(post):
    return Document(
        page_content="\n".join(
            [
                f"게시글 제목: {post.post_title}",
                f"카테고리: {post.category}",
                f"내용: {post.content}",
            ]
        ),
        metadata={
            "source_type": "post",
            "post_id": post.id,
            "board_id": post.board_id,
            "user_id": post.user_id,
            "category": post.category,
        },
    )


def comment_to_document(comment):
    return Document(
        page_content=f"댓글 내용: {comment.content}",
        metadata={
            "source_type": "comment",
            "comment_id": comment.id,
            "board_id": comment.board_id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
        },
    )


load_dotenv()
def get_llm() -> ChatOpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI 키 없다")
    return ChatOpenAI(model="gpt-4o-mini")


# OpenAI 임베딩 모델 객체 생성. 학생 프로필, 게시글, 댓글을 벡터로 바꿀 때 사용
def get_embeddings() -> OpenAIEmbeddings:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OpenAI 키 없다")

    return OpenAIEmbeddings(model="text-embedding-3-small")


# Chroma vector DB 연결 객체를 만든다. 문서 저장, 검색, 삭제에 사용한다. embeddings를 외부에서 주입할 수 있게 하면 테스트가 쉬워진다.
def get_vector_store(embeddings: OpenAIEmbeddings | None=None) -> Chroma:

    return Chroma(collection_name="jungle_board",
                  embedding_function=embeddings or get_embeddings(),
                  persist_directory="./chroma")


# 문서 내용의 SHA-256 해시를 만든다. 내용이 바뀌었는지 확인해서 불필요한 재색인을 막는 데 사용한다.
def make_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# Chroma에 저장할 문서 ID를 규칙적으로 만든다. 예: post:42:chunk:0. 수정/삭제/재색인할 때 같은 ID를 다시 찾기 위해 필요하다.
def make_vector_doc_id(source_type: str, source_id: int, chunk_idx: int) -> str:
    return f"{source_type}:{source_id}:chunk:{chunk_idx}"


# 긴 문서를 여러 chunk로 나눈다. 게시글이나 회고가 길어도 검색 품질이 떨어지지 않게 하기 위한 함수다.
def split_document(document: Document) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=120,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    return splitter.split_documents([document])


def index_student_profile(db: Session, user_id: int) -> list[RagDocument]:
    """ DB에서 user_id에 해당하는 유저 정보를 가져와서
        그 유저 프로필을 RAG 검색용 문서로 만들고,
        Chroma 벡터DB에 저장한 뒤,
        “무엇을 저장했는지”에 대한 기록인 RagDocument 목록을 반환하는 함수 """
    user_db_data = select_user(db=db, user_id=user_id)
    if not user_db_data:
        raise ValueError(f"user_id={user_id} 유저를 찾을 수 없습니다.")

    user = user_db_data[0]
    document = user_to_document(user)
    chunks = split_document(document)

    if not is_chunks_diff(db=db, source_type="student_profile", source_id=user_id, chunks=chunks):
        return select_rag_document(db=db, source_type="student_profile", source_id=user_id)

    delete_indexed_source(db=db, source_type="student_profile", source_id=user_id)

    doc_ids = [ make_vector_doc_id("student_profile", user_id, idx) for idx, _ in enumerate(chunks)]

    vector_store = get_vector_store()
    vector_store.add_documents(documents=chunks, ids=doc_ids)
    rag_documents = [
        insert_rag_document(
            db=db,
            source_type="student_profile",
            source_id=user_id,
            chunk_index=idx,
            vector_doc_id=doc_ids[idx],
            content=chunk.page_content,
            content_hash=make_content_hash(chunk.page_content),
            metadata_json=chunk.metadata,
        )
        for idx, chunk in enumerate(chunks)
    ]
    return rag_documents

def index_post(db: Session, post_id: int) -> list[RagDocument]:
    post_db_data = select_post(db=db, post_id=post_id)
    if not post_db_data:
        raise ValueError(f"post_id={post_id} 게시글을 찾을 수 없습니다.")

    post = post_db_data[0]
    document = post_to_document(post)
    chunks = split_document(document)

    if not is_chunks_diff(db=db, source_type="post", source_id=post_id, chunks=chunks):
        return select_rag_document(db=db, source_type="post", source_id=post_id)

    delete_indexed_source(db=db, source_type="post", source_id=post_id)

    post_ids = [make_vector_doc_id("post", post_id, idx) for idx, _ in enumerate(chunks)]

    vector_store = get_vector_store()
    vector_store.add_documents(documents=chunks, ids=post_ids)
    rag_documents = [
        insert_rag_document(
            db=db,
            source_type="post",
            source_id=post_id,
            chunk_index=idx,
            vector_doc_id=post_ids[idx],
            content=chunk.page_content,
            content_hash=make_content_hash(chunk.page_content),
            metadata_json=chunk.metadata,
        )
        for idx, chunk in enumerate(chunks)
    ]
    return rag_documents

def index_comment(db: Session, comment_id:int) -> list[RagDocument]:
    comment_db_data = select_comment(db=db, comment_id=comment_id)
    if not comment_db_data:
        raise ValueError(f"comment_id={comment_id} 게시글을 찾을 수 없습니다.")

    comment = comment_db_data[0]
    document = comment_to_document(comment)
    chunks = split_document(document)

    if not is_chunks_diff(db=db, source_type="comment", source_id=comment_id, chunks=chunks):
        return select_rag_document(db=db, source_type="comment", source_id=comment_id)

    delete_indexed_source(db=db, source_type="comment", source_id=comment_id)

    comment_ids = [make_vector_doc_id("comment", comment_id, idx) for idx, _ in enumerate(chunks)]

    vector_store = get_vector_store()
    vector_store.add_documents(documents=chunks, ids=comment_ids)
    rag_documents = [
        insert_rag_document(
            db=db,
            source_type="comment",
            source_id=comment_id,
            chunk_index=idx,
            vector_doc_id=comment_ids[idx],
            content=chunk.page_content,
            content_hash=make_content_hash(chunk.page_content),
            metadata_json=chunk.metadata,
        )
        for idx, chunk in enumerate(chunks)
    ]
    return rag_documents


def delete_indexed_source(db: Session, source_type: str, source_id: int):
    indexed_docs = select_rag_document(db=db, source_type=source_type, source_id=source_id)

    vector_doc_id = [
        doc.vector_doc_id
        for doc in indexed_docs
    ]

    if vector_doc_id:
        vector_store = get_vector_store()
        vector_store.delete(ids=vector_doc_id)

    for doc in indexed_docs:
        delete_rag_document(db, doc.id)


def reindex_all_users(db: Session):
    users = select_user(db=db)
    for user in users:
        index_student_profile(db=db, user_id=user.id)


def reindex_all_board_documents(db: Session):
    posts = select_post(db=db)
    for post in posts:
        index_post(db=db, post_id=post.id)


def search_user_docs(query: str, classroom: int, user_ids: list[int] | None = None, k: int=5) -> list[Document]:
    vector_store = get_vector_store()

    # 학생 프로필 청크만 검색
    search_filter = {
        "$and": [
            {"source_type": "student_profile"},
            {"classroom": classroom},
        ]
    }

    documents = vector_store.similarity_search(
        query=query,
        k=k,
        filter=search_filter,
    )

    if user_ids is not None:
        documents = [
            document for document in documents
            if document.metadata.get("user_id") in user_ids
        ]

    return documents

# 최소구현 완료 후 작성 예정
def search_board_docs():
    pass


# 중복 인덱싱 방지용
def is_chunks_diff(db: Session, source_type: str,
                   source_id: int, chunks: list[Document]) -> bool:
    rag_docs = select_rag_document(db=db, source_type=source_type, source_id=source_id)
    if len(rag_docs) != len(chunks):
        return True

    hash_by_chunk_index = {
        doc.chunk_index: doc.content_hash for doc in rag_docs
    }

    for idx, chunk in enumerate(chunks):
        new_hash = make_content_hash(chunk.page_content)
        old_hash = hash_by_chunk_index.get(idx)
        if old_hash != new_hash:
            return True

    return False
