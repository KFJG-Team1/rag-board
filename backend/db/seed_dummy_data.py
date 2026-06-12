from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, TypeVar

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.db.db import Base, SessionLocal
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
from backend.db.dummy_seed_data import (
    BOARDS,
    COMMENTS,
    EXPECTED_BOARD_COUNT,
    EXPECTED_CLASSROOMS,
    EXPECTED_COMMENT_COUNT,
    EXPECTED_MEMBERS_PER_TEAM,
    EXPECTED_POST_COUNT,
    EXPECTED_STUDENT_PROFILE_COUNT,
    EXPECTED_TEAM_COUNT,
    EXPECTED_TEAM_MEMBER_COUNT,
    EXPECTED_TEAMS_PER_CLASSROOM,
    EXPECTED_USER_COUNT,
    EXPECTED_WEEKLY_SUMMARY_COUNT,
    POSTS,
    STUDENT_PROFILES,
    TEAMS,
    TEAM_MEMBERS,
    USERS,
    WEEKLY_SUMMARIES,
)
from backend.db.db_crud import drop_all_table, create_all_table

T = TypeVar("T")


@dataclass(frozen=True)
class SeedResult:
    users: int
    student_profiles: int
    teams: int
    team_members: int
    boards: int
    posts: int
    comments: int
    weekly_summaries: int
    rag_documents: int


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _ensure_unique(values: Iterable[T], label: str) -> None:
    items = list(values)
    if len(items) != len(set(items)):
        raise ValueError(f"Duplicate {label} exists")


def _clear_tables(db: Session) -> None:
    """FK 제약을 고려해 자식 테이블부터 삭제한다."""

    db.execute(delete(RagDocument))
    db.execute(delete(WeeklySummary))
    db.execute(delete(Comment))
    db.execute(delete(Post))
    db.execute(delete(Board))
    db.execute(delete(TeamMember))
    db.execute(delete(Team))
    db.execute(delete(StudentProfile))
    db.execute(delete(User))
    db.commit()


def _count_rows(db: Session) -> SeedResult:
    return SeedResult(
        users=db.scalar(select(func.count()).select_from(User)) or 0,
        student_profiles=(
            db.scalar(select(func.count()).select_from(StudentProfile)) or 0
        ),
        teams=db.scalar(select(func.count()).select_from(Team)) or 0,
        team_members=db.scalar(select(func.count()).select_from(TeamMember)) or 0,
        boards=db.scalar(select(func.count()).select_from(Board)) or 0,
        posts=db.scalar(select(func.count()).select_from(Post)) or 0,
        comments=db.scalar(select(func.count()).select_from(Comment)) or 0,
        weekly_summaries=(
            db.scalar(select(func.count()).select_from(WeeklySummary)) or 0
        ),
        rag_documents=db.scalar(select(func.count()).select_from(RagDocument)) or 0,
    )


def _validate_seed_rows() -> None:
    if len(USERS) != EXPECTED_USER_COUNT:
        raise ValueError(f"Expected {EXPECTED_USER_COUNT} users, got {len(USERS)}")

    if len(STUDENT_PROFILES) != EXPECTED_STUDENT_PROFILE_COUNT:
        raise ValueError(
            "Expected "
            f"{EXPECTED_STUDENT_PROFILE_COUNT} profiles, got {len(STUDENT_PROFILES)}"
        )

    if len(TEAMS) != EXPECTED_TEAM_COUNT:
        raise ValueError(f"Expected {EXPECTED_TEAM_COUNT} teams, got {len(TEAMS)}")

    if len(TEAM_MEMBERS) != EXPECTED_TEAM_MEMBER_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_TEAM_MEMBER_COUNT} team members, "
            f"got {len(TEAM_MEMBERS)}"
        )

    if len(BOARDS) != EXPECTED_BOARD_COUNT:
        raise ValueError(f"Expected {EXPECTED_BOARD_COUNT} boards, got {len(BOARDS)}")

    if len(POSTS) != EXPECTED_POST_COUNT:
        raise ValueError(f"Expected {EXPECTED_POST_COUNT} posts, got {len(POSTS)}")

    if len(COMMENTS) != EXPECTED_COMMENT_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_COMMENT_COUNT} comments, got {len(COMMENTS)}"
        )

    if len(WEEKLY_SUMMARIES) != EXPECTED_WEEKLY_SUMMARY_COUNT:
        raise ValueError(
            f"Expected {EXPECTED_WEEKLY_SUMMARY_COUNT} summaries, "
            f"got {len(WEEKLY_SUMMARIES)}"
        )

    classrooms = {row["classroom"] for row in USERS}
    if classrooms != set(EXPECTED_CLASSROOMS):
        raise ValueError(
            f"Expected classrooms {EXPECTED_CLASSROOMS}, got {sorted(classrooms)}"
        )

    user_keys = {row["key"] for row in USERS}
    _ensure_unique((row["key"] for row in USERS), "user key")

    profile_user_keys = {row["user_key"] for row in STUDENT_PROFILES}
    if profile_user_keys != user_keys:
        raise ValueError("Student profiles must exist exactly once for every user")

    _ensure_unique((row["key"] for row in TEAMS), "team key")
    _ensure_unique(
        ((row["week"], row["classroom"], row["team_num"]) for row in TEAMS),
        "week/classroom/team_num",
    )

    teams_by_key = {row["key"]: row for row in TEAMS}
    expected_team_count = len(EXPECTED_CLASSROOMS) * EXPECTED_TEAMS_PER_CLASSROOM
    if len(TEAMS) != expected_team_count:
        raise ValueError(f"Expected {expected_team_count} generated teams")

    unknown_team_keys = {
        row["team_key"] for row in TEAM_MEMBERS if row["team_key"] not in teams_by_key
    }
    if unknown_team_keys:
        raise ValueError(f"Unknown team_key in TEAM_MEMBERS: {unknown_team_keys}")

    unknown_member_users = {
        row["user_key"]
        for row in TEAM_MEMBERS
        if row["user_key"] not in user_keys
    }
    if unknown_member_users:
        raise ValueError(f"Unknown user in TEAM_MEMBERS: {unknown_member_users}")

    _ensure_unique(
        ((row["team_key"], row["user_key"]) for row in TEAM_MEMBERS),
        "team member pair",
    )

    team_member_counts: dict[str, int] = {}
    for row in TEAM_MEMBERS:
        team_member_counts[row["team_key"]] = team_member_counts.get(row["team_key"], 0) + 1

    invalid_team_sizes = {
        team_key: count
        for team_key, count in team_member_counts.items()
        if count != EXPECTED_MEMBERS_PER_TEAM
    }
    if invalid_team_sizes:
        raise ValueError(f"Invalid team sizes: {invalid_team_sizes}")

    _ensure_unique((row["key"] for row in BOARDS), "board key")
    _ensure_unique((row["team_key"] for row in BOARDS), "board team key")

    unknown_board_team_keys = {
        row["team_key"] for row in BOARDS if row["team_key"] not in teams_by_key
    }
    if unknown_board_team_keys:
        raise ValueError(f"Unknown team_key in BOARDS: {unknown_board_team_keys}")

    boards_by_key = {row["key"]: row for row in BOARDS}
    _ensure_unique((row["key"] for row in POSTS), "post key")

    unknown_post_boards = {
        row["board_key"] for row in POSTS if row["board_key"] not in boards_by_key
    }
    if unknown_post_boards:
        raise ValueError(f"Unknown board_key in POSTS: {unknown_post_boards}")

    unknown_post_authors = {
        row["author_user_key"]
        for row in POSTS
        if row["author_user_key"] not in user_keys
    }
    if unknown_post_authors:
        raise ValueError(f"Unknown author in POSTS: {unknown_post_authors}")

    posts_by_key = {row["key"]: row for row in POSTS}
    unknown_comment_posts = {
        row["post_key"] for row in COMMENTS if row["post_key"] not in posts_by_key
    }
    if unknown_comment_posts:
        raise ValueError(f"Unknown post_key in COMMENTS: {unknown_comment_posts}")

    unknown_comment_authors = {
        row["author_user_key"]
        for row in COMMENTS
        if row["author_user_key"] not in user_keys
    }
    if unknown_comment_authors:
        raise ValueError(f"Unknown author in COMMENTS: {unknown_comment_authors}")

    unknown_summary_teams = {
        row["team_key"] for row in WEEKLY_SUMMARIES if row["team_key"] not in teams_by_key
    }
    if unknown_summary_teams:
        raise ValueError(f"Unknown team_key in WEEKLY_SUMMARIES: {unknown_summary_teams}")

    _ensure_unique(
        ((row["team_key"], row["week"]) for row in WEEKLY_SUMMARIES),
        "weekly summary team/week",
    )


def _build_users() -> list[User]:
    return [
        User(
            name=row["name"],
            phone_num=row["phone_num"],
            classroom=row["classroom"],
        )
        for row in USERS
    ]


def _build_student_profiles(
    users_by_key: dict[str, User],
) -> list[StudentProfile]:
    profiles: list[StudentProfile] = []

    for row in STUDENT_PROFILES:
        user = users_by_key[row["user_key"]]
        profiles.append(
            StudentProfile(
                user_id=user.id,
                score=row["score"],
                project_count=row["project_count"],
                interests=row["interests"],
                self_intro=row["self_intro"],
                avoid_condition=row["avoid_condition"],
            )
        )

    return profiles


def _build_teams() -> tuple[list[Team], dict[str, Team]]:
    teams: list[Team] = []
    teams_by_key: dict[str, Team] = {}

    for row in TEAMS:
        team = Team(
            week=row["week"],
            classroom=row["classroom"],
            team_num=row["team_num"],
            name=row["name"],
        )
        teams.append(team)
        teams_by_key[row["key"]] = team

    return teams, teams_by_key


def _build_team_members(
    teams_by_key: dict[str, Team],
    users_by_key: dict[str, User],
) -> list[TeamMember]:
    team_members: list[TeamMember] = []

    for row in TEAM_MEMBERS:
        team = teams_by_key[row["team_key"]]
        user = users_by_key[row["user_key"]]
        team_members.append(
            TeamMember(
                team_id=team.id,
                user_id=user.id,
            )
        )

    return team_members


def _build_boards(teams_by_key: dict[str, Team]) -> tuple[list[Board], dict[str, Board]]:
    boards: list[Board] = []
    boards_by_key: dict[str, Board] = {}

    for row in BOARDS:
        team = teams_by_key[row["team_key"]]
        board = Board(
            team_id=team.id,
            board_name=row["board_name"],
        )
        boards.append(board)
        boards_by_key[row["key"]] = board

    return boards, boards_by_key


def _build_posts(
    users_by_key: dict[str, User],
    boards_by_key: dict[str, Board],
) -> tuple[list[Post], dict[str, Post]]:
    posts: list[Post] = []
    posts_by_key: dict[str, Post] = {}

    for row in POSTS:
        board = boards_by_key[row["board_key"]]
        user = users_by_key[row["author_user_key"]]
        created_at = _parse_timestamp(row["created_at"])
        post = Post(
            board_id=board.id,
            user_id=user.id,
            category=row["category"],
            post_title=row["post_title"],
            content=row["content"],
            created_at=created_at,
            updated_at=created_at,
        )
        posts.append(post)
        posts_by_key[row["key"]] = post

    return posts, posts_by_key


def _build_comments(
    users_by_key: dict[str, User],
    posts_by_key: dict[str, Post],
) -> list[Comment]:
    comments: list[Comment] = []

    for row in COMMENTS:
        post = posts_by_key[row["post_key"]]
        user = users_by_key[row["author_user_key"]]
        created_at = _parse_timestamp(row["created_at"])
        comments.append(
            Comment(
                board_id=post.board_id,
                post_id=post.id,
                user_id=user.id,
                content=row["content"],
                created_at=created_at,
                updated_at=created_at,
            )
        )

    return comments


def _build_weekly_summaries(
    teams_by_key: dict[str, Team],
) -> list[WeeklySummary]:
    summaries: list[WeeklySummary] = []

    for row in WEEKLY_SUMMARIES:
        team = teams_by_key[row["team_key"]]
        summaries.append(
            WeeklySummary(
                team_id=team.id,
                week=row["week"],
                summary=row["summary"],
                keywords=row["keywords"],
                frequent_questions=row["frequent_questions"],
                blocked_points=row["blocked_points"],
                recommended_materials=row["recommended_materials"],
            )
        )

    return summaries


def seed_dummy_data(db: Session, reset_schema: bool = False) -> SeedResult:
    bind = db.get_bind()

    if reset_schema:
        Base.metadata.drop_all(bind=bind)

    Base.metadata.create_all(bind=bind)
    _validate_seed_rows()

    _clear_tables(db)

    users = _build_users()
    db.add_all(users)
    db.flush()
    users_by_key = {row["key"]: user for row, user in zip(USERS, users, strict=True)}

    student_profiles = _build_student_profiles(users_by_key)
    db.add_all(student_profiles)
    db.flush()

    teams, teams_by_key = _build_teams()
    db.add_all(teams)
    db.flush()

    team_members = _build_team_members(teams_by_key, users_by_key)
    db.add_all(team_members)
    db.flush()

    boards, boards_by_key = _build_boards(teams_by_key)
    db.add_all(boards)
    db.flush()

    posts, posts_by_key = _build_posts(users_by_key, boards_by_key)
    db.add_all(posts)
    db.flush()

    comments = _build_comments(users_by_key, posts_by_key)
    db.add_all(comments)
    db.flush()

    weekly_summaries = _build_weekly_summaries(teams_by_key)
    db.add_all(weekly_summaries)
    db.commit()

    return _count_rows(db)


def main() -> None:
    drop_all_table()
    create_all_table()
    parser = argparse.ArgumentParser(
        description="Seed normalized dummy users, teams, boards, posts, and comments."
    )
    parser.add_argument(
        "--reset-schema",
        action="store_true",
        help="Drop all known tables before recreating them. This deletes existing data.",
    )
    args = parser.parse_args()

    with SessionLocal() as db:
        counts = seed_dummy_data(db, reset_schema=args.reset_schema)

    print(
        "Seed complete: "
        f"users={counts.users}, "
        f"student_profiles={counts.student_profiles}, "
        f"teams={counts.teams}, "
        f"team_members={counts.team_members}, "
        f"boards={counts.boards}, "
        f"posts={counts.posts}, "
        f"comments={counts.comments}, "
        f"weekly_summaries={counts.weekly_summaries}, "
        f"rag_documents={counts.rag_documents}"
    )


if __name__ == "__main__":
    main()
