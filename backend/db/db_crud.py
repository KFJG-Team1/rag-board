from datetime import datetime
from typing import Any, cast

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.db import Base, engine
from backend.db.db_model import (
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


def create_all_table() -> None:
    Base.metadata.create_all(bind=engine)


def drop_all_table() -> None:
    Base.metadata.drop_all(bind=engine)


def insert_user(
    db: Session,
    name: str,
    classroom: int,
    phone_num: str | None = None,
) -> User:
    user = User(
        name=name,
        phone_num=phone_num,
        classroom=classroom,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def insert_student_profile(
    db: Session,
    user_id: int,
    score: int = 0,
    project_count: int = 0,
    interests: str | None = None,
    self_intro: str | None = None,
    avoid_condition: str | None = None,
) -> StudentProfile:
    profile = StudentProfile(
        user_id=user_id,
        score=score,
        project_count=project_count,
        interests=interests,
        self_intro=self_intro,
        avoid_condition=avoid_condition,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    return profile


def insert_team(
    db: Session,
    week: int,
    classroom: int,
    team_num: int,
    name: str,
) -> Team:
    team = Team(
        week=week,
        classroom=classroom,
        team_num=team_num,
        name=name,
    )
    db.add(team)
    db.commit()
    db.refresh(team)

    return team


def insert_team_member(db: Session, team_id: int, user_id: int) -> TeamMember:
    team_member = TeamMember(
        team_id=team_id,
        user_id=user_id,
    )
    db.add(team_member)
    db.commit()
    db.refresh(team_member)

    return team_member


def insert_board(db: Session, team_id: int, board_name: str) -> Board:
    board = Board(
        team_id=team_id,
        board_name=board_name,
    )
    db.add(board)
    db.commit()
    db.refresh(board)

    return board


def insert_post(
    db: Session,
    board_id: int,
    user_id: int,
    post_title: str,
    content: str,
    category: str = "학습 기록",
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Post:
    post = Post(
        board_id=board_id,
        user_id=user_id,
        category=category,
        post_title=post_title,
        content=content,
    )

    if created_at is not None:
        post.created_at = created_at

    if updated_at is not None:
        post.updated_at = updated_at

    db.add(post)
    db.commit()
    db.refresh(post)

    return post


def insert_comment(
    db: Session,
    board_id: int,
    post_id: int,
    user_id: int,
    content: str,
    created_at: datetime | None = None,
    updated_at: datetime | None = None,
) -> Comment:
    comment = Comment(
        board_id=board_id,
        post_id=post_id,
        user_id=user_id,
        content=content,
    )

    if created_at is not None:
        comment.created_at = created_at

    if updated_at is not None:
        comment.updated_at = updated_at

    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment


def insert_rag_document(
    db: Session,
    source_type: str,
    source_id: int,
    vector_doc_id: str,
    content: str,
    content_hash: str,
    chunk_index: int = 0,
    title: str | None = None,
    metadata_json: dict[str, Any] | None = None,
) -> RagDocument:
    rag_document = RagDocument(
        source_type=source_type,
        source_id=source_id,
        chunk_index=chunk_index,
        vector_doc_id=vector_doc_id,
        title=title,
        content=content,
        metadata_json={} if metadata_json is None else metadata_json,
        content_hash=content_hash,
    )
    db.add(rag_document)
    db.commit()
    db.refresh(rag_document)

    return rag_document


def insert_weekly_summary(
    db: Session,
    team_id: int,
    week: int,
    summary: str,
    keywords: list[str] | None = None,
    frequent_questions: list[str] | None = None,
    blocked_points: list[str] | None = None,
    recommended_materials: list[str] | None = None,
) -> WeeklySummary:
    weekly_summary = WeeklySummary(
        team_id=team_id,
        week=week,
        summary=summary,
        keywords=[] if keywords is None else keywords,
        frequent_questions=[] if frequent_questions is None else frequent_questions,
        blocked_points=[] if blocked_points is None else blocked_points,
        recommended_materials=[] if recommended_materials is None else recommended_materials,
    )
    db.add(weekly_summary)
    db.commit()
    db.refresh(weekly_summary)

    return weekly_summary


def select_user(
    db: Session,
    user_id: int | None = None,
    name: str | None = None,
    phone_num: str | None = None,
    classroom: int | None = None,
) -> list[User]:
    stmt = select(User)

    if user_id is not None:
        stmt = stmt.where(User.id == user_id)

    if name is not None:
        stmt = stmt.where(User.name == name)

    if phone_num is not None:
        stmt = stmt.where(User.phone_num == phone_num)

    if classroom is not None:
        stmt = stmt.where(User.classroom == classroom)

    return list(db.scalars(stmt).all())


def select_student_profile(
    db: Session,
    profile_id: int | None = None,
    user_id: int | None = None,
    score: int | None = None,
    project_count: int | None = None,
) -> list[StudentProfile]:
    stmt = select(StudentProfile)

    if profile_id is not None:
        stmt = stmt.where(StudentProfile.id == profile_id)

    if user_id is not None:
        stmt = stmt.where(StudentProfile.user_id == user_id)

    if score is not None:
        stmt = stmt.where(StudentProfile.score == score)

    if project_count is not None:
        stmt = stmt.where(StudentProfile.project_count == project_count)

    return list(db.scalars(stmt).all())


def select_team(
    db: Session,
    team_id: int | None = None,
    week: int | None = None,
    classroom: int | None = None,
    team_num: int | None = None,
    name: str | None = None,
) -> list[Team]:
    stmt = select(Team)

    if team_id is not None:
        stmt = stmt.where(Team.id == team_id)

    if week is not None:
        stmt = stmt.where(Team.week == week)

    if classroom is not None:
        stmt = stmt.where(Team.classroom == classroom)

    if team_num is not None:
        stmt = stmt.where(Team.team_num == team_num)

    if name is not None:
        stmt = stmt.where(Team.name == name)

    return list(db.scalars(stmt).all())


def select_team_member(
    db: Session,
    team_member_id: int | None = None,
    team_id: int | None = None,
    user_id: int | None = None,
) -> list[TeamMember]:
    stmt = select(TeamMember)

    if team_member_id is not None:
        stmt = stmt.where(TeamMember.id == team_member_id)

    if team_id is not None:
        stmt = stmt.where(TeamMember.team_id == team_id)

    if user_id is not None:
        stmt = stmt.where(TeamMember.user_id == user_id)

    return list(db.scalars(stmt).all())


def select_board(
    db: Session,
    board_id: int | None = None,
    team_id: int | None = None,
    board_name: str | None = None,
) -> list[Board]:
    stmt = select(Board)

    if board_id is not None:
        stmt = stmt.where(Board.id == board_id)

    if team_id is not None:
        stmt = stmt.where(Board.team_id == team_id)

    if board_name is not None:
        stmt = stmt.where(Board.board_name == board_name)

    return list(db.scalars(stmt).all())


def select_post(
    db: Session,
    post_id: int | None = None,
    board_id: int | None = None,
    user_id: int | None = None,
    category: str | None = None,
    post_title: str | None = None,
) -> list[Post]:
    stmt = select(Post)

    if post_id is not None:
        stmt = stmt.where(Post.id == post_id)

    if board_id is not None:
        stmt = stmt.where(Post.board_id == board_id)

    if user_id is not None:
        stmt = stmt.where(Post.user_id == user_id)

    if category is not None:
        stmt = stmt.where(Post.category == category)

    if post_title is not None:
        stmt = stmt.where(Post.post_title == post_title)

    return list(db.scalars(stmt).all())


def select_comment(
    db: Session,
    comment_id: int | None = None,
    board_id: int | None = None,
    post_id: int | None = None,
    user_id: int | None = None,
) -> list[Comment]:
    stmt = select(Comment)

    if comment_id is not None:
        stmt = stmt.where(Comment.id == comment_id)

    if board_id is not None:
        stmt = stmt.where(Comment.board_id == board_id)

    if post_id is not None:
        stmt = stmt.where(Comment.post_id == post_id)

    if user_id is not None:
        stmt = stmt.where(Comment.user_id == user_id)

    return list(db.scalars(stmt).all())


def select_rag_document(
    db: Session,
    rag_document_id: int | None = None,
    source_type: str | None = None,
    source_id: int | None = None,
    chunk_index: int | None = None,
    vector_doc_id: str | None = None,
) -> list[RagDocument]:
    stmt = select(RagDocument)

    if rag_document_id is not None:
        stmt = stmt.where(RagDocument.id == rag_document_id)

    if source_type is not None:
        stmt = stmt.where(RagDocument.source_type == source_type)

    if source_id is not None:
        stmt = stmt.where(RagDocument.source_id == source_id)

    if chunk_index is not None:
        stmt = stmt.where(RagDocument.chunk_index == chunk_index)

    if vector_doc_id is not None:
        stmt = stmt.where(RagDocument.vector_doc_id == vector_doc_id)

    return list(db.scalars(stmt).all())


def select_weekly_summary(
    db: Session,
    weekly_summary_id: int | None = None,
    team_id: int | None = None,
    week: int | None = None,
) -> list[WeeklySummary]:
    stmt = select(WeeklySummary)

    if weekly_summary_id is not None:
        stmt = stmt.where(WeeklySummary.id == weekly_summary_id)

    if team_id is not None:
        stmt = stmt.where(WeeklySummary.team_id == team_id)

    if week is not None:
        stmt = stmt.where(WeeklySummary.week == week)

    return list(db.scalars(stmt).all())


def update_user(
    db: Session,
    user_id: int,
    name: str | None = None,
    phone_num: str | None = None,
    classroom: int | None = None,
) -> User | None:
    user = cast(User | None, db.get(User, user_id))

    if user is None:
        return None

    if name is not None:
        user.name = name

    if phone_num is not None:
        user.phone_num = phone_num

    if classroom is not None:
        user.classroom = classroom

    db.commit()
    db.refresh(user)

    return user


def update_student_profile(
    db: Session,
    profile_id: int,
    user_id: int | None = None,
    score: int | None = None,
    project_count: int | None = None,
    interests: str | None = None,
    self_intro: str | None = None,
    avoid_condition: str | None = None,
) -> StudentProfile | None:
    profile = cast(StudentProfile | None, db.get(StudentProfile, profile_id))

    if profile is None:
        return None

    if user_id is not None:
        profile.user_id = user_id

    if score is not None:
        profile.score = score

    if project_count is not None:
        profile.project_count = project_count

    if interests is not None:
        profile.interests = interests

    if self_intro is not None:
        profile.self_intro = self_intro

    if avoid_condition is not None:
        profile.avoid_condition = avoid_condition

    db.commit()
    db.refresh(profile)

    return profile


def update_team(
    db: Session,
    team_id: int,
    week: int | None = None,
    classroom: int | None = None,
    team_num: int | None = None,
    name: str | None = None,
) -> Team | None:
    team = cast(Team | None, db.get(Team, team_id))

    if team is None:
        return None

    if week is not None:
        team.week = week

    if classroom is not None:
        team.classroom = classroom

    if team_num is not None:
        team.team_num = team_num

    if name is not None:
        team.name = name

    db.commit()
    db.refresh(team)

    return team


def update_team_member(
    db: Session,
    team_member_id: int,
    team_id: int | None = None,
    user_id: int | None = None,
) -> TeamMember | None:
    team_member = cast(TeamMember | None, db.get(TeamMember, team_member_id))

    if team_member is None:
        return None

    if team_id is not None:
        team_member.team_id = team_id

    if user_id is not None:
        team_member.user_id = user_id

    db.commit()
    db.refresh(team_member)

    return team_member


def update_board(
    db: Session,
    board_id: int,
    team_id: int | None = None,
    board_name: str | None = None,
) -> Board | None:
    board = cast(Board | None, db.get(Board, board_id))

    if board is None:
        return None

    if team_id is not None:
        board.team_id = team_id

    if board_name is not None:
        board.board_name = board_name

    db.commit()
    db.refresh(board)

    return board


def update_post(
    db: Session,
    post_id: int,
    board_id: int | None = None,
    user_id: int | None = None,
    category: str | None = None,
    post_title: str | None = None,
    content: str | None = None,
) -> Post | None:
    post = cast(Post | None, db.get(Post, post_id))

    if post is None:
        return None

    if board_id is not None:
        post.board_id = board_id

    if user_id is not None:
        post.user_id = user_id

    if category is not None:
        post.category = category

    if post_title is not None:
        post.post_title = post_title

    if content is not None:
        post.content = content

    db.commit()
    db.refresh(post)

    return post


def update_comment(
    db: Session,
    comment_id: int,
    board_id: int | None = None,
    post_id: int | None = None,
    user_id: int | None = None,
    content: str | None = None,
) -> Comment | None:
    comment = cast(Comment | None, db.get(Comment, comment_id))

    if comment is None:
        return None

    if board_id is not None:
        comment.board_id = board_id

    if post_id is not None:
        comment.post_id = post_id

    if user_id is not None:
        comment.user_id = user_id

    if content is not None:
        comment.content = content

    db.commit()
    db.refresh(comment)

    return comment


def update_rag_document(
    db: Session,
    rag_document_id: int,
    source_type: str | None = None,
    source_id: int | None = None,
    chunk_index: int | None = None,
    vector_doc_id: str | None = None,
    title: str | None = None,
    content: str | None = None,
    metadata_json: dict[str, Any] | None = None,
    content_hash: str | None = None,
) -> RagDocument | None:
    rag_document = cast(RagDocument | None, db.get(RagDocument, rag_document_id))

    if rag_document is None:
        return None

    if source_type is not None:
        rag_document.source_type = source_type

    if source_id is not None:
        rag_document.source_id = source_id

    if chunk_index is not None:
        rag_document.chunk_index = chunk_index

    if vector_doc_id is not None:
        rag_document.vector_doc_id = vector_doc_id

    if title is not None:
        rag_document.title = title

    if content is not None:
        rag_document.content = content

    if metadata_json is not None:
        rag_document.metadata_json = metadata_json

    if content_hash is not None:
        rag_document.content_hash = content_hash

    db.commit()
    db.refresh(rag_document)

    return rag_document


def update_weekly_summary(
    db: Session,
    weekly_summary_id: int,
    team_id: int | None = None,
    week: int | None = None,
    summary: str | None = None,
    keywords: list[str] | None = None,
    frequent_questions: list[str] | None = None,
    blocked_points: list[str] | None = None,
    recommended_materials: list[str] | None = None,
) -> WeeklySummary | None:
    weekly_summary = cast(
        WeeklySummary | None,
        db.get(WeeklySummary, weekly_summary_id),
    )

    if weekly_summary is None:
        return None

    if team_id is not None:
        weekly_summary.team_id = team_id

    if week is not None:
        weekly_summary.week = week

    if summary is not None:
        weekly_summary.summary = summary

    if keywords is not None:
        weekly_summary.keywords = keywords

    if frequent_questions is not None:
        weekly_summary.frequent_questions = frequent_questions

    if blocked_points is not None:
        weekly_summary.blocked_points = blocked_points

    if recommended_materials is not None:
        weekly_summary.recommended_materials = recommended_materials

    db.commit()
    db.refresh(weekly_summary)

    return weekly_summary


def delete_user(db: Session, user_id: int) -> bool:
    user = cast(User | None, db.get(User, user_id))

    if user is None:
        return False

    db.delete(user)
    db.commit()

    return True


def delete_student_profile(db: Session, profile_id: int) -> bool:
    profile = cast(StudentProfile | None, db.get(StudentProfile, profile_id))

    if profile is None:
        return False

    db.delete(profile)
    db.commit()

    return True


def delete_team(db: Session, team_id: int) -> bool:
    team = cast(Team | None, db.get(Team, team_id))

    if team is None:
        return False

    db.delete(team)
    db.commit()

    return True


def delete_team_member(db: Session, team_member_id: int) -> bool:
    team_member = cast(TeamMember | None, db.get(TeamMember, team_member_id))

    if team_member is None:
        return False

    db.delete(team_member)
    db.commit()

    return True


def delete_board(db: Session, board_id: int) -> bool:
    board = cast(Board | None, db.get(Board, board_id))

    if board is None:
        return False

    db.delete(board)
    db.commit()

    return True


def delete_post(db: Session, post_id: int) -> bool:
    post = cast(Post | None, db.get(Post, post_id))

    if post is None:
        return False

    db.delete(post)
    db.commit()

    return True


def delete_comment(db: Session, comment_id: int) -> bool:
    comment = cast(Comment | None, db.get(Comment, comment_id))

    if comment is None:
        return False

    db.delete(comment)
    db.commit()

    return True


def delete_rag_document(db: Session, rag_document_id: int) -> bool:
    rag_document = cast(RagDocument | None, db.get(RagDocument, rag_document_id))

    if rag_document is None:
        return False

    db.delete(rag_document)
    db.commit()

    return True


def delete_weekly_summary(db: Session, weekly_summary_id: int) -> bool:
    weekly_summary = cast(
        WeeklySummary | None,
        db.get(WeeklySummary, weekly_summary_id),
    )

    if weekly_summary is None:
        return False

    db.delete(weekly_summary)
    db.commit()

    return True
