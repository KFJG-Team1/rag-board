from datetime import UTC, datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from backend.db.db import Base


def utc_now() -> datetime:
    """생성/수정 시각을 UTC 기준으로 저장하기 위한 공통 함수."""
    return datetime.now(UTC)


class User(Base):
    """학생을 식별하기 위한 기본 사용자 테이블.

    이 테이블은 "누가 누구인가"를 식별하는 최소 정보만 가진다.
    관심 분야, 자기소개, 피하고 싶은 조건처럼 팀 편성이나 RAG 검색에 쓰이는
    정보는 StudentProfile로 분리한다.

    팀 번호를 User에 직접 넣지 않는 이유:
    - 팀은 주차마다 바뀔 수 있다.
    - 한 학생이 여러 주차에 서로 다른 팀에 속할 수 있다.
    - 따라서 팀 소속은 TeamMember 테이블에서 관리해야 한다.
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 학생 식별 정보
    name = Column(String, nullable=False)
    phone_num = Column(String)
    classroom = Column(Integer, nullable=False)

    # User 1명은 설문/프로필 1개를 가진다.
    profile = relationship(
        "StudentProfile",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )

    # User 1명은 여러 주차의 여러 TeamMember row와 연결될 수 있다.
    team_memberships = relationship("TeamMember", back_populates="user")

    # 작성자 기준 게시글/댓글 조회용 관계.
    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")


class StudentProfile(Base):
    """팀 편성 및 RAG 근거 생성에 사용하는 학생 프로필.

    정형 데이터:
    - score는 전체 역량 점수 기준으로 팀 실력 균형에 사용한다.
    - project_count는 프로젝트 경험 분산 기준으로 사용한다.

    비정형 데이터:
    - interests, self_intro, avoid_condition은 RAG 문서로 변환해서 근거 검색에
      사용한다.

    User와 1:1 관계이므로 user_id에 unique 제약을 건다.
    """

    __tablename__ = "student_profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)

    # 팀 편성에 쓰는 정량 데이터.
    score = Column(Integer, nullable=False, default=0)
    project_count = Column(Integer, nullable=False, default=0)

    # RAG에 넣을 정성 데이터
    interests = Column(Text)
    self_intro = Column(Text)
    avoid_condition = Column(Text)

    user = relationship("User", back_populates="profile")


class Team(Base):
    """특정 주차, 특정 반, 특정 팀 번호로 식별되는 팀.

    Team은 팀 자체만 표현한다.
    팀에 어떤 학생들이 들어가는지는 TeamMember에서 관리한다.

    week + classroom + team_num 조합은 한 번만 존재해야 한다.
    예를 들어 1주차 301반 2팀은 teams 테이블에 row 1개만 존재할 수 있다.
    """

    __tablename__ = "teams"

    __table_args__ = (
        UniqueConstraint(
            "week",
            "classroom",
            "team_num",
            name="uq_teams_week_classroom_team_num",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    week = Column(Integer, nullable=False)
    classroom = Column(Integer, nullable=False)
    team_num = Column(Integer, nullable=False)

    # 화면 표시용 이름. 예: "Team Alpha", "301반 1주차 2팀"
    name = Column(String, nullable=False)

    members = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    board = relationship(
        "Board",
        back_populates="team",
        uselist=False,
        cascade="all, delete-orphan",
    )
    weekly_summaries = relationship(
        "WeeklySummary",
        back_populates="team",
        cascade="all, delete-orphan",
    )


class TeamMember(Base):
    """Team과 User를 연결하는 팀원 테이블.

    한 팀에는 여러 학생이 들어가고, 한 학생은 주차가 달라지면 여러 팀 이력을
    가질 수 있다. 그래서 Team과 User 사이를 직접 연결하지 않고 TeamMember를 둔다.

    team_id + user_id 조합은 unique로 묶어서 같은 팀에 같은 학생이 중복 등록되는
    것을 막는다.
    """

    __tablename__ = "team_members"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "user_id",
            name="uq_team_members_team_id_user_id",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    team = relationship("Team", back_populates="members")
    user = relationship("User", back_populates="team_memberships")


class Board(Base):
    """팀별 학습 게시판.

    게시판은 Team과 1:1로 연결된다.
    week, classroom, team_num은 Team에 이미 있으므로 Board에 중복 저장하지 않는다.
    게시판이 어떤 주차/반/팀인지 알고 싶으면 board.team을 통해 조회한다.
    """

    __tablename__ = "boards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), unique=True, nullable=False)

    board_name = Column(String, nullable=False)

    team = relationship("Team", back_populates="board")
    posts = relationship("Post", back_populates="board", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="board")


class Post(Base):
    """팀 게시판의 게시글.

    category는 README의 게시판 카테고리 역할을 한다.
    예: 공지, 학습 기록, 질문, 자료 공유, 회의록, 회고

    RAG 인덱싱 시 post_title + content를 page_content로 만들고,
    post_id, board_id, user_id, category를 metadata로 넣으면 된다.
    """

    __tablename__ = "posts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_id = Column(Integer, ForeignKey("boards.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    category = Column(String, nullable=False, default="학습 기록")
    post_title = Column(String, nullable=False)
    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    board = relationship("Board", back_populates="posts")
    user = relationship("User", back_populates="posts")
    comments = relationship(
        "Comment",
        back_populates="post",
        cascade="all, delete-orphan",
    )


class Comment(Base):
    """게시글 댓글.

    board_id는 post.board_id로도 알 수 있지만, 특정 게시판의 댓글을 바로 조회할
    일이 많기 때문에 저장한다.

    RAG 인덱싱 시 댓글도 별도 문서로 저장할 수 있다.
    예: source_type='comment', source_id=comment.id
    """

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_id = Column(Integer, ForeignKey("boards.id"), nullable=False)
    post_id = Column(Integer, ForeignKey("posts.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    content = Column(Text, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    board = relationship("Board", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")


class RagDocument(Base):
    """벡터DB에 저장한 문서의 원본 추적 테이블.

    Chroma 같은 벡터DB에는 원문 조각과 임베딩 벡터가 저장된다.
    DB row가 수정/삭제되었을 때 벡터DB의 어떤 문서를 갱신해야 하는지 추적하려면
    별도 매핑 테이블이 필요하다.

    source_type/source_id:
    - 원본이 어떤 테이블의 어떤 row인지 나타낸다.
    - 여러 테이블을 가리키는 구조라 ForeignKey를 직접 걸지 않는다.

    chunk_index:
    - 긴 게시글이나 프로필은 여러 청크로 쪼개질 수 있다.
    - 같은 원본이라도 청크마다 vector_doc_id가 달라야 한다.
    """

    __tablename__ = "rag_documents"

    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            "chunk_index",
            name="uq_rag_documents_source_chunk",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)

    # 예: student_profile, post, comment, weekly_summary
    source_type = Column(String, nullable=False)
    source_id = Column(Integer, nullable=False)
    chunk_index = Column(Integer, nullable=False, default=0)

    # 벡터DB에서 사용하는 문서 ID. 예: post:10:chunk:0
    vector_doc_id = Column(String, unique=True, nullable=False)

    title = Column(String)
    content = Column(Text, nullable=False)
    metadata_json = Column(JSON, nullable=False, default=dict)
    content_hash = Column(String, nullable=False)

    indexed_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)


class WeeklySummary(Base):
    """팀별 주간 학습 요약 결과.

    팀 게시판 글과 댓글을 검색한 뒤 LLM이 생성한 요약을 저장한다.
    같은 팀의 같은 주차 요약은 하나만 존재해야 하므로 team_id + week를 unique로
    묶는다.

    keywords, frequent_questions, blocked_points, recommended_materials는
    리스트 형태로 쓰기 좋으므로 JSON 컬럼으로 저장한다.
    """

    __tablename__ = "weekly_summaries"

    __table_args__ = (
        UniqueConstraint(
            "team_id",
            "week",
            name="uq_weekly_summaries_team_id_week",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey("teams.id"), nullable=False)
    week = Column(Integer, nullable=False)

    summary = Column(Text, nullable=False)
    keywords = Column(JSON, nullable=False, default=list)
    frequent_questions = Column(JSON, nullable=False, default=list)
    blocked_points = Column(JSON, nullable=False, default=list)
    recommended_materials = Column(JSON, nullable=False, default=list)

    team = relationship("Team", back_populates="weekly_summaries")
