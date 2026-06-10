from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from backend.db import Base
from datetime import datetime, UTC


# relationship의 단수/복수 기준은 테이블 이름이 아니라 관계의 개수
# User 1명은 Post 여러 개를 쓸 수 있음
# Post 1개는 User 1명이 작성함



class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    github_id = Column(String)
    phone_num = Column(String)
    classroom = Column(Integer)
    team = Column(Integer)
    score = Column(Integer)
    project_cnt = Column(Integer)

    posts = relationship("Post", back_populates="user")
    comments = relationship("Comment", back_populates="user")


class Board(Base):
    __tablename__ = 'boards'

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_name = Column(String)
    week = Column(Integer)
    classroom = Column(Integer)
    team = Column(Integer)

    posts = relationship("Post", back_populates="board")
    comments = relationship("Comment", back_populates="board")

class Post(Base):
    __tablename__ = 'posts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_title = Column(String)
    board_id = Column(Integer, ForeignKey('boards.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    board = relationship("Board", back_populates="posts")
    user = relationship("User", back_populates="posts")
    comments = relationship("Comment", back_populates="post")


class Comment(Base):
    __tablename__ = 'comments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    board_id = Column(Integer, ForeignKey('boards.id'))
    post_id = Column(Integer, ForeignKey('posts.id'))
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(UTC))

    board = relationship("Board", back_populates="comments")
    post = relationship("Post", back_populates="comments")
    user = relationship("User", back_populates="comments")

