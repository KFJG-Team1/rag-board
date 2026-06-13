import os

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend import rag
from backend.db import (
    Base,
    Board,
    Comment,
    Post,
    StudentProfile,
    Team,
    User,
    insert_rag_document,
    select_rag_document,
)
from langchain_core.documents import Document


class FakeVectorStore:
    def __init__(self, search_results=None):
        self.added_documents = []
        self.added_ids = []
        self.deleted_ids = []
        self.search_calls = []
        self.search_results = [] if search_results is None else search_results

    def add_documents(self, documents, ids):
        self.added_documents.extend(documents)
        self.added_ids.extend(ids)

    def delete(self, ids):
        self.deleted_ids.extend(ids)

    def similarity_search(self, query, k, filter):
        self.search_calls.append({"query": query, "k": k, "filter": filter})
        return self.search_results[:k]


def make_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def seed_board_post_comment(db):
    user = User(name="게시글작성자", phone_num="010-2222-3333", classroom=301)
    team = Team(week=1, classroom=301, team_num=1, name="301반 1팀")
    board = Board(team=team, board_name="301반 1팀 게시판")
    post = Post(
        board=board,
        user=user,
        category="질문",
        post_title="RAG 검색 질문",
        content="Chroma에 저장한 게시글을 어떻게 다시 찾나요?",
    )
    comment = Comment(
        board=board,
        post=post,
        user=user,
        content="metadata filter를 같이 확인하면 됩니다.",
    )
    db.add_all([user, team, board, post, comment])
    db.commit()
    return user, post, comment


def test_user_to_document_includes_profile_fields():
    user = User(id=7, name="김정글", phone_num=None, classroom=305)
    user.profile = StudentProfile(
        id=11,
        score=88,
        project_count=3,
        interests="FastAPI, RAG",
        self_intro="검색 기반 게시판을 만들고 싶습니다.",
        avoid_condition=None,
    )

    document = rag.user_to_document(user)

    assert "학생 이름: 김정글" in document.page_content
    assert "전화번호: 미입력" in document.page_content
    assert "실력 점수: 88" in document.page_content
    assert "피하고 싶은 조건: 미입력" in document.page_content
    assert document.metadata == {
        "source_type": "user_profile",
        "user_id": 7,
        "classroom": 305,
        "profile_id": 11,
    }


def test_post_and_comment_to_document_metadata():
    Session = make_test_session()

    with Session() as db:
        _, post, comment = seed_board_post_comment(db)

        post_document = rag.post_to_document(post)
        comment_document = rag.comment_to_document(comment)

        assert "게시글 제목: RAG 검색 질문" in post_document.page_content
        assert "카테고리: 질문" in post_document.page_content
        assert post_document.metadata == {
            "source_type": "post",
            "post_id": post.id,
            "board_id": post.board_id,
            "user_id": post.user_id,
            "category": "질문",
        }
        assert comment_document.page_content == "댓글 내용: metadata filter를 같이 확인하면 됩니다."
        assert comment_document.metadata == {
            "source_type": "comment",
            "comment_id": comment.id,
            "board_id": comment.board_id,
            "post_id": comment.post_id,
            "user_id": comment.user_id,
        }


def test_hash_and_vector_doc_id_are_deterministic():
    assert rag.make_content_hash("같은 내용") == rag.make_content_hash("같은 내용")
    assert rag.make_content_hash("같은 내용") != rag.make_content_hash("다른 내용")
    assert rag.make_vector_doc_id("post", 42, 3) == "post:42:chunk:3"


def test_split_document_preserves_metadata_and_splits_long_text():
    document = Document(
        page_content="문장입니다. " * 300,
        metadata={"source_type": "post", "post_id": 1},
    )

    chunks = rag.split_document(document)

    assert len(chunks) > 1
    assert all(chunk.metadata == document.metadata for chunk in chunks)
    assert all(chunk.page_content for chunk in chunks)


def test_is_chunks_diff_compares_chunk_count_and_hashes():
    Session = make_test_session()

    with Session() as db:
        chunk = Document(page_content="원본 내용")
        insert_rag_document(
            db=db,
            source_type="post",
            source_id=1,
            chunk_index=0,
            vector_doc_id="post:1:chunk:0",
            content=chunk.page_content,
            content_hash=rag.make_content_hash(chunk.page_content),
            metadata_json={},
        )

        assert rag.is_chunks_diff(db, "post", 1, [chunk]) is False
        assert rag.is_chunks_diff(db, "post", 1, [Document(page_content="수정된 내용")]) is True
        assert rag.is_chunks_diff(db, "post", 1, [chunk, Document(page_content="추가")]) is True


def test_index_user_profile_adds_vector_documents_and_rag_records(monkeypatch):
    Session = make_test_session()
    fake_vector_store = FakeVectorStore()
    monkeypatch.setattr(rag, "get_vector_store", lambda: fake_vector_store)

    with Session() as db:
        user = User(name="인덱싱학생", phone_num="010-4444-5555", classroom=302)
        user.profile = StudentProfile(
            score=92,
            project_count=4,
            interests="LLM, 검색",
            self_intro="RAG 인덱싱 테스트 대상입니다.",
            avoid_condition="없음",
        )
        db.add(user)
        db.commit()

        indexed_docs = rag.index_user_profile(db, user.id)
        indexed_again = rag.index_user_profile(db, user.id)

        assert len(indexed_docs) == 1
        assert indexed_again[0].id == indexed_docs[0].id
        assert fake_vector_store.added_ids == [f"user_profile:{user.id}:chunk:0"]
        assert fake_vector_store.added_documents[0].metadata["user_id"] == user.id
        assert indexed_docs[0].source_type == "user_profile"
        assert indexed_docs[0].source_id == user.id
        assert indexed_docs[0].content_hash == rag.make_content_hash(indexed_docs[0].content)


def test_index_user_profile_creates_reads_and_deletes_real_chroma_vector_db_when_api_key_exists(
    tmp_path,
    monkeypatch,
):
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY가 있을 때만 실제 Chroma 인덱싱을 테스트합니다.")

    monkeypatch.chdir(tmp_path)
    Session = make_test_session()

    with Session() as db:
        user = User(name="실제벡터학생", phone_num="010-9999-0000", classroom=303)
        user.profile = StudentProfile(
            score=85,
            project_count=2,
            interests="실제 Chroma 벡터DB 테스트",
            self_intro="OpenAI embedding으로 임시 Chroma DB에 저장되는지 확인합니다.",
            avoid_condition="없음",
        )
        db.add(user)
        db.commit()

        indexed_docs = rag.index_user_profile(db, user.id)
        vector_doc_ids = [doc.vector_doc_id for doc in indexed_docs]

        assert (tmp_path / "chroma").is_dir()
        assert (tmp_path / "chroma" / "chroma.sqlite3").is_file()
        assert select_rag_document(db, source_type="user_profile", source_id=user.id) == indexed_docs

        vector_store = rag.get_vector_store()
        stored = vector_store.get(ids=vector_doc_ids)

        assert stored["ids"] == vector_doc_ids
        assert stored["documents"][0] == indexed_docs[0].content
        assert stored["metadatas"][0]["source_type"] == "user_profile"
        assert stored["metadatas"][0]["user_id"] == user.id

        search_results = vector_store.similarity_search(
            "실제 Chroma 벡터DB 테스트",
            k=1,
            filter={"source_type": "user_profile"},
        )

        assert len(search_results) == 1
        assert search_results[0].metadata["user_id"] == user.id

        rag.delete_indexed_source(db, "user_profile", user.id)

        deleted = rag.get_vector_store().get(ids=vector_doc_ids)

        assert deleted["ids"] == []
        assert deleted["documents"] == []
        assert deleted["metadatas"] == []
        assert select_rag_document(db, source_type="user_profile", source_id=user.id) == []


def test_index_post_and_comment_raise_when_source_is_missing():
    Session = make_test_session()

    with Session() as db:
        try:
            rag.index_post(db, 999)
        except ValueError as exc:
            assert "post_id=999" in str(exc)
        else:
            raise AssertionError("index_post should fail for a missing post")

        try:
            rag.index_comment(db, 999)
        except ValueError as exc:
            assert "comment_id=999" in str(exc)
        else:
            raise AssertionError("index_comment should fail for a missing comment")


def test_delete_indexed_source_removes_vector_and_db_records(monkeypatch):
    Session = make_test_session()
    fake_vector_store = FakeVectorStore()
    monkeypatch.setattr(rag, "get_vector_store", lambda: fake_vector_store)

    with Session() as db:
        saved = insert_rag_document(
            db=db,
            source_type="post",
            source_id=10,
            chunk_index=0,
            vector_doc_id="post:10:chunk:0",
            content="삭제할 내용",
            content_hash=rag.make_content_hash("삭제할 내용"),
            metadata_json={},
        )

        rag.delete_indexed_source(db, "post", 10)

        assert fake_vector_store.deleted_ids == [saved.vector_doc_id]
        assert select_rag_document(db, source_type="post", source_id=10) == []


def test_search_user_docs_filters_by_source_type_and_user_ids(monkeypatch):
    matching = Document(
        page_content="검색 결과 A",
        metadata={"source_type": "user_profile", "user_id": 1},
    )
    filtered_out = Document(
        page_content="검색 결과 B",
        metadata={"source_type": "user_profile", "user_id": 2},
    )
    fake_vector_store = FakeVectorStore(search_results=[matching, filtered_out])
    monkeypatch.setattr(rag, "get_vector_store", lambda: fake_vector_store)

    results = rag.search_user_docs("RAG 관심 학생", classroom=301, user_ids=[1], k=5)

    assert results == [matching]
    assert fake_vector_store.search_calls == [
        {
            "query": "RAG 관심 학생",
            "k": 5,
            "filter": {
                "$and": [
                    {"source_type": "user_profile"},
                    {"classroom": 301},
                ]
            },
        }
    ]
