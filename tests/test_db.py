import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.db import (
    Base,
    Board,
    Comment,
    Post,
    StudentProfile,
    Team,
    TeamMember,
    User,
    WeeklySummary,
)
from backend.db.dummy_seed_data import (
    EXPECTED_BOARD_COUNT,
    EXPECTED_COMMENT_COUNT,
    EXPECTED_POST_COUNT,
    EXPECTED_STUDENT_PROFILE_COUNT,
    EXPECTED_TEAM_COUNT,
    EXPECTED_TEAM_MEMBER_COUNT,
    EXPECTED_USER_COUNT,
    EXPECTED_WEEKLY_SUMMARY_COUNT,
)
from backend.db.seed_dummy_data import seed_dummy_data
from backend.db.db_crud import (
    delete_comment,
    insert_board,
    insert_comment,
    insert_post,
    insert_student_profile,
    insert_team,
    insert_team_member,
    insert_user,
    select_comment,
    select_post,
    select_student_profile,
    select_team,
    select_team_member,
    select_user,
    update_post,
    update_user,
)


def make_test_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine)


def test_team_board_post_relationships():
    Session = make_test_session()

    with Session() as db:
        user = User(
            name="테스트학생",
            phone_num="010-0000-0000",
            classroom=301,
        )
        profile = StudentProfile(
            user=user,
            score=84,
            project_count=3,
            interests="RAG 기반 게시판 검색",
            self_intro="팀 게시판 데이터를 요약하는 기능을 구현하고 싶습니다.",
            avoid_condition="매일 늦은 밤 회의는 어렵습니다.",
        )
        team = Team(week=1, classroom=301, team_num=1, name="301반 1주차 1팀")
        membership = TeamMember(
            team=team,
            user=user,
        )
        board = Board(team=team, board_name="301반 1주차 1팀 학습 게시판")
        post = Post(
            board=board,
            user=user,
            category="학습 기록",
            post_title="RAG 모델링 정리",
            content="Team과 TeamMember를 분리해서 팀 소속을 관리했습니다.",
        )
        comment = Comment(
            board=board,
            post=post,
            user=user,
            content="이 내용은 주간 요약에 포함하면 좋겠습니다.",
        )
        summary = WeeklySummary(
            team=team,
            week=1,
            summary="RAG 게시판 모델링을 정리했습니다.",
            keywords=["RAG", "SQLAlchemy"],
            frequent_questions=["TeamMember가 필요한 이유는 무엇인가요?"],
            blocked_points=["관계형 모델 설계"],
            recommended_materials=["SQLAlchemy relationship 문서"],
        )

        db.add_all([user, profile, team, membership, board, post, comment, summary])
        db.commit()

        saved_user = db.scalar(select(User).where(User.name == "테스트학생"))

        assert saved_user is not None
        assert saved_user.profile.score == 84
        assert saved_user.profile.project_count == 3
        assert saved_user.profile.interests == "RAG 기반 게시판 검색"
        assert saved_user.team_memberships[0].team.team_num == 1
        assert saved_user.posts[0].comments[0].content.startswith("이 내용")
        assert saved_user.team_memberships[0].team.board.board_name.endswith("학습 게시판")


def test_team_week_classroom_team_num_is_unique():
    Session = make_test_session()

    with Session() as db:
        db.add_all(
            [
                Team(week=1, classroom=301, team_num=1, name="팀 A"),
                Team(week=1, classroom=301, team_num=1, name="팀 B"),
            ]
        )

        with pytest.raises(IntegrityError):
            db.commit()


def test_seed_dummy_data_with_normalized_models():
    Session = make_test_session()

    with Session() as db:
        counts = seed_dummy_data(db, reset_schema=True)

        assert counts.users == EXPECTED_USER_COUNT
        assert counts.student_profiles == EXPECTED_STUDENT_PROFILE_COUNT
        assert counts.teams == EXPECTED_TEAM_COUNT
        assert counts.team_members == EXPECTED_TEAM_MEMBER_COUNT
        assert counts.boards == EXPECTED_BOARD_COUNT
        assert counts.posts == EXPECTED_POST_COUNT
        assert counts.comments == EXPECTED_COMMENT_COUNT
        assert counts.weekly_summaries == EXPECTED_WEEKLY_SUMMARY_COUNT
        assert counts.rag_documents == 0


def test_crud_helpers_with_current_models():
    Session = make_test_session()

    with Session() as db:
        user = insert_user(
            db=db,
            name="CRUD학생",
            classroom=301,
            phone_num="010-1111-2222",
        )
        profile = insert_student_profile(
            db=db,
            user_id=user.id,
            score=77,
            project_count=2,
            interests="게시판 RAG 검색",
            self_intro="CRUD 함수 테스트를 위한 학생입니다.",
            avoid_condition="늦은 밤 회의는 어렵습니다.",
        )
        team = insert_team(
            db=db,
            week=1,
            classroom=301,
            team_num=9,
            name="CRUD 테스트 팀",
        )
        team_member = insert_team_member(db=db, team_id=team.id, user_id=user.id)
        board = insert_board(db=db, team_id=team.id, board_name="CRUD 테스트 게시판")
        post = insert_post(
            db=db,
            board_id=board.id,
            user_id=user.id,
            category="질문",
            post_title="CRUD 질문",
            content="처음 작성한 내용",
        )
        comment = insert_comment(
            db=db,
            board_id=board.id,
            post_id=post.id,
            user_id=user.id,
            content="댓글 내용",
        )

        assert select_user(db, name="CRUD학생")[0].id == user.id
        assert select_student_profile(db, user_id=user.id)[0].id == profile.id
        assert select_student_profile(db, score=77)[0].id == profile.id
        assert select_team(db, week=1, classroom=301, team_num=9)[0].id == team.id
        assert select_team_member(db, team_id=team.id)[0].id == team_member.id
        assert select_post(db, category="질문")[0].id == post.id
        assert select_comment(db, post_id=post.id)[0].id == comment.id

        updated_user = update_user(db, user.id, phone_num="010-3333-4444")
        updated_post = update_post(db, post.id, content="수정한 내용")

        assert updated_user is not None
        assert updated_user.phone_num == "010-3333-4444"
        assert updated_post is not None
        assert updated_post.content == "수정한 내용"
        assert delete_comment(db, comment.id) is True
        assert select_comment(db, comment_id=comment.id) == []
