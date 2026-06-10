from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from backend.db.db import Base, SessionLocal, engine
from backend.db.db_model import Board, Comment, Post, User
from backend.db.dummy_seed_data import (
    BOARDS,
    COMMENTS,
    EXPECTED_CLASSROOMS,
    EXPECTED_USER_COUNT,
    POSTS,
    USERS,
)


@dataclass(frozen=True)
class SeedResult:
    users: int
    boards: int
    posts: int
    comments: int


def _clear_tables(db: Session) -> None:
    db.execute(delete(Comment))
    db.execute(delete(Post))
    db.execute(delete(Board))
    db.execute(delete(User))
    db.commit()


def _count_rows(db: Session) -> SeedResult:
    return SeedResult(
        users=db.scalar(select(func.count()).select_from(User)) or 0,
        boards=db.scalar(select(func.count()).select_from(Board)) or 0,
        posts=db.scalar(select(func.count()).select_from(Post)) or 0,
        comments=db.scalar(select(func.count()).select_from(Comment)) or 0,
    )


def _validate_seed_rows() -> None:
    if len(USERS) != EXPECTED_USER_COUNT:
        raise ValueError(f"Expected {EXPECTED_USER_COUNT} users, got {len(USERS)}")

    classrooms = {row["classroom"] for row in USERS}
    if classrooms != set(EXPECTED_CLASSROOMS):
        raise ValueError(
            f"Expected classrooms {EXPECTED_CLASSROOMS}, got {sorted(classrooms)}"
        )

    github_ids = [row["github_id"] for row in USERS]
    if len(github_ids) != len(set(github_ids)):
        raise ValueError("Duplicate github_id exists in USERS")

    board_keys = [row["key"] for row in BOARDS]
    if len(board_keys) != len(set(board_keys)):
        raise ValueError("Duplicate key exists in BOARDS")

    post_keys = [row["key"] for row in POSTS]
    if len(post_keys) != len(set(post_keys)):
        raise ValueError("Duplicate key exists in POSTS")

    unknown_board_keys = {
        row["board_key"]
        for row in POSTS
        if row["board_key"] not in set(board_keys)
    }
    if unknown_board_keys:
        raise ValueError(f"Unknown board_key exists in POSTS: {unknown_board_keys}")

    unknown_post_keys = {
        row["post_key"]
        for row in COMMENTS
        if row["post_key"] not in set(post_keys)
    }
    if unknown_post_keys:
        raise ValueError(f"Unknown post_key exists in COMMENTS: {unknown_post_keys}")

    known_github_ids = set(github_ids)
    unknown_authors = {
        row["author_github_id"]
        for row in POSTS + COMMENTS
        if row["author_github_id"] not in known_github_ids
    }
    if unknown_authors:
        raise ValueError(f"Unknown author_github_id exists: {unknown_authors}")


def _parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _build_users() -> list[User]:
    return [
        User(
            name=row["name"],
            github_id=row["github_id"],
            phone_num=row["phone_num"],
            classroom=row["classroom"],
            team=row["team"],
            score=row["score"],
            project_cnt=row["project_cnt"],
        )
        for row in USERS
    ]


def _build_boards() -> tuple[list[Board], dict[str, Board]]:
    boards: list[Board] = []
    boards_by_key: dict[str, Board] = {}

    for row in BOARDS:
        board = Board(
            board_name=row["board_name"],
            week=row["week"],
            classroom=row["classroom"],
            team=row["team"],
        )
        boards.append(board)
        boards_by_key[row["key"]] = board

    return boards, boards_by_key


def _build_posts(
    users_by_github_id: dict[str, User],
    boards_by_key: dict[str, Board],
) -> tuple[list[Post], dict[str, Post]]:
    posts: list[Post] = []
    posts_by_key: dict[str, Post] = {}

    for row in POSTS:
        board = boards_by_key[row["board_key"]]
        user = users_by_github_id[row["author_github_id"]]
        post = Post(
            post_title=row["post_title"],
            board_id=board.id,
            user_id=user.id,
            content=row["content"],
            timestamp=_parse_timestamp(row["timestamp"]),
        )
        posts.append(post)
        posts_by_key[row["key"]] = post

    return posts, posts_by_key


def _build_comments(
    users_by_github_id: dict[str, User],
    posts_by_key: dict[str, Post],
) -> list[Comment]:
    comments: list[Comment] = []

    for row in COMMENTS:
        post = posts_by_key[row["post_key"]]
        user = users_by_github_id[row["author_github_id"]]
        comments.append(
            Comment(
                board_id=post.board_id,
                post_id=post.id,
                user_id=user.id,
                content=row["content"],
                timestamp=_parse_timestamp(row["timestamp"]),
            )
        )

    return comments


def seed_dummy_data(db: Session) -> SeedResult:
    Base.metadata.create_all(bind=engine)
    _validate_seed_rows()

    _clear_tables(db)

    users = _build_users()
    db.add_all(users)
    db.flush()
    users_by_github_id = {user.github_id: user for user in users}

    boards, boards_by_key = _build_boards()
    db.add_all(boards)
    db.flush()

    posts, posts_by_key = _build_posts(users_by_github_id, boards_by_key)
    db.add_all(posts)
    db.flush()

    comments = _build_comments(users_by_github_id, posts_by_key)
    db.add_all(comments)
    db.commit()

    return _count_rows(db)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed dummy users, boards, posts, and comments."
    )
    parser.parse_args()

    with SessionLocal() as db:
        counts = seed_dummy_data(db)

    print(
        "Seed complete: "
        f"users={counts.users}, boards={counts.boards}, "
        f"posts={counts.posts}, comments={counts.comments}"
    )


if __name__ == "__main__":
    main()
