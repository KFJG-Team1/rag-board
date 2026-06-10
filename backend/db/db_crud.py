from backend.db import User, Post, Board, Comment, Base, engine
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import cast

def create_all_table():
    Base.metadata.create_all(bind=engine)

def drop_all_table():
    Base.metadata.drop_all(bind=engine)

def insert_user(db: Session, name: str, github_id: str, phone_num: str, classroom: int, team: int, score: int, project_cnt: int) -> User:
    user = User(
        name=name,
        github_id=github_id,
        phone_num=phone_num,
        classroom=classroom,
        team=team,
        score=score,
        project_cnt=project_cnt
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    return user

def insert_board(db: Session, board_name: str, week: int,
                 classroom: int, team: int) -> Board:
    board = Board(
        board_name=board_name,
        week=week,
        classroom=classroom,
        team=team
    )
    db.add(board)
    db.commit()
    db.refresh(board)

    return board

def insert_post(db: Session, post_title: str, board_id: int,
                user_id: int, content: str) -> Post:
    post = Post(
        post_title=post_title,
        board_id=board_id,
        user_id=user_id,
        content=content
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    return post

def insert_comment(db: Session, board_id: int, post_id: int,
                   user_id: int, content: str) -> Comment:
    comment = Comment(
        board_id=board_id,
        post_id=post_id,
        user_id=user_id,
        content=content
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    return comment

def select_user(
    db: Session,
    user_id: int | None = None,
    github_id: str | None = None,
    name: str | None = None,
    phone_num: str | None = None,
    classroom: int | None = None,
    team: int | None = None,
) -> list[User]:
    stmt = select(User)

    if user_id is not None:
        stmt = stmt.where(User.id == user_id)

    if github_id is not None:
        stmt = stmt.where(User.github_id == github_id)

    if name is not None:
        stmt = stmt.where(User.name == name)

    if phone_num is not None:
        stmt = stmt.where(User.phone_num == phone_num)

    if classroom is not None:
        stmt = stmt.where(User.classroom == classroom)

    if team is not None:
        stmt = stmt.where(User.team == team)

    return list(db.scalars(stmt).all())


def select_board(
    db: Session,
    board_id: int | None = None,
    board_name: str | None = None,
    week: int | None = None,
    classroom: int | None = None,
    team: int | None = None,
) -> list[Board]:
    stmt = select(Board)

    if board_id is not None:
        stmt = stmt.where(Board.id == board_id)

    if board_name is not None:
        stmt = stmt.where(Board.board_name == board_name)

    if week is not None:
        stmt = stmt.where(Board.week == week)

    if classroom is not None:
        stmt = stmt.where(Board.classroom == classroom)

    if team is not None:
        stmt = stmt.where(Board.team == team)

    return list(db.scalars(stmt).all())


def select_post(
    db: Session,
    post_id: int | None = None,
    post_title: str | None = None,
    board_id: int | None = None,
    user_id: int | None = None,
) -> list[Post]:
    stmt = select(Post)

    if post_id is not None:
        stmt = stmt.where(Post.id == post_id)

    if post_title is not None:
        stmt = stmt.where(Post.post_title == post_title)

    if board_id is not None:
        stmt = stmt.where(Post.board_id == board_id)

    if user_id is not None:
        stmt = stmt.where(Post.user_id == user_id)

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


def update_user(
    db: Session,
    user_id: int,
    name: str | None = None,
    github_id: str | None = None,
    phone_num: str | None = None,
    classroom: int | None = None,
    team: int | None = None,
    score: int | None = None,
    project_cnt: int | None = None,
) -> User | None:
    user = cast(User | None, db.get(User, user_id))

    if user is None:
        return None

    if name is not None:
        user.name = name

    if github_id is not None:
        user.github_id = github_id

    if phone_num is not None:
        user.phone_num = phone_num

    if classroom is not None:
        user.classroom = classroom

    if team is not None:
        user.team = team

    if score is not None:
        user.score = score

    if project_cnt is not None:
        user.project_cnt = project_cnt

    db.commit()
    db.refresh(user)

    return user


def update_board(
    db: Session,
    board_id: int,
    board_name: str | None = None,
    week: int | None = None,
    classroom: int | None = None,
    team: int | None = None,
) -> Board | None:
    board = cast(Board | None, db.get(Board, board_id))

    if board is None:
        return None

    if board_name is not None:
        board.board_name = board_name

    if week is not None:
        board.week = week

    if classroom is not None:
        board.classroom = classroom

    if team is not None:
        board.team = team

    db.commit()
    db.refresh(board)

    return board


def update_post(
    db: Session,
    post_id: int,
    post_title: str | None = None,
    board_id: int | None = None,
    user_id: int | None = None,
    content: str | None = None,
) -> Post | None:
    post = cast(Post | None, db.get(Post, post_id))

    if post is None:
        return None

    if post_title is not None:
        post.post_title = post_title

    if board_id is not None:
        post.board_id = board_id

    if user_id is not None:
        post.user_id = user_id

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


def delete_user(db: Session, user_id: int) -> bool:
    user = cast(User | None, db.get(User, user_id))

    if user is None:
        return False

    db.delete(user)
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
