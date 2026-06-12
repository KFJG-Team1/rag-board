"""backend.db 패키지의 공개 진입점.

이 파일은 다른 모듈에서 아래처럼 짧게 import할 수 있게 해준다.

    from backend.db import SessionLocal, User, Team

이 패키지는 DB 연결 객체, SQLAlchemy 모델 클래스, 함수형 CRUD 헬퍼를 공개한다.
"""

from .db import Base, SessionLocal, engine, get_db
from .db_model import (
    Board,
    Comment,
    Post,
    RagDocument,
    StudentProfile,
    Team,
    TeamMember,
    User,
    WeeklySummary,
)
from .db_crud import (
    create_all_table,
    delete_board,
    delete_comment,
    delete_post,
    delete_rag_document,
    delete_student_profile,
    delete_team,
    delete_team_member,
    delete_user,
    delete_weekly_summary,
    drop_all_table,
    insert_board,
    insert_comment,
    insert_post,
    insert_rag_document,
    insert_student_profile,
    insert_team,
    insert_team_member,
    insert_user,
    insert_weekly_summary,
    select_board,
    select_comment,
    select_post,
    select_rag_document,
    select_student_profile,
    select_team,
    select_team_member,
    select_user,
    select_weekly_summary,
    update_board,
    update_comment,
    update_post,
    update_rag_document,
    update_student_profile,
    update_team,
    update_team_member,
    update_user,
    update_weekly_summary,
)

# __all__은 `from backend.db import *`로 가져갈 수 있는 공개 이름 목록이다.
# 내부 구현 세부사항을 실수로 외부에 노출하지 않기 위해 명시적으로 관리한다.
__all__ = [
    # DB 연결/세션 관련 객체
    "Base",
    "SessionLocal",
    "engine",
    "get_db",
    # SQLAlchemy 모델 클래스
    "User",
    "StudentProfile",
    "Team",
    "TeamMember",
    "Board",
    "Post",
    "Comment",
    "RagDocument",
    "WeeklySummary",
    # DB schema helpers
    "create_all_table",
    "drop_all_table",
    # Insert helpers
    "insert_user",
    "insert_student_profile",
    "insert_team",
    "insert_team_member",
    "insert_board",
    "insert_post",
    "insert_comment",
    "insert_rag_document",
    "insert_weekly_summary",
    # Select helpers
    "select_user",
    "select_student_profile",
    "select_team",
    "select_team_member",
    "select_board",
    "select_post",
    "select_comment",
    "select_rag_document",
    "select_weekly_summary",
    # Update helpers
    "update_user",
    "update_student_profile",
    "update_team",
    "update_team_member",
    "update_board",
    "update_post",
    "update_comment",
    "update_rag_document",
    "update_weekly_summary",
    # Delete helpers
    "delete_user",
    "delete_student_profile",
    "delete_team",
    "delete_team_member",
    "delete_board",
    "delete_post",
    "delete_comment",
    "delete_rag_document",
    "delete_weekly_summary",
]
