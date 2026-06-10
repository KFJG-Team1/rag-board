from fastmcp import FastMCP

from backend.db import *

mcp = FastMCP()

def user_to_dict(user):
    return {
        "id": user.id,
        "name": user.name,
        "github_id": user.github_id,
        "phone_num": user.phone_num,
        "classroom": user.classroom,
        "team": user.team,
        "score": user.score,
        "project_cnt": user.project_cnt,
    }


def post_to_dict(post):
    return {
        "id": post.id,
        "post_title": post.post_title,
        "board_id": post.board_id,
        "user_id": post.user_id,
        "content": post.content,
        "timestamp": post.timestamp.isoformat() if post.timestamp else None,
    }


@mcp.tool
def get_all_users_data():
    """학생 데이터 가져오기."""
    with SessionLocal() as db:
        return [user_to_dict(user) for user in select_user(db=db)]


@mcp.tool
def get_all_posts_from_board(board_id: int):
    """선택한 게시판에서 게시글 정보 가져오기."""
    with SessionLocal() as db:
        return [post_to_dict(post) for post in select_post(db=db, board_id=board_id)]

