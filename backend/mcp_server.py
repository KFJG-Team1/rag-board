from fastmcp import FastMCP
from sqlalchemy import select

from backend.db import Post, SessionLocal, User
from backend.db import select_student_profile

mcp = FastMCP()


def user_to_dict(user: User) -> dict:
    profile = user.profile

    return {
        "id": user.id,
        "name": user.name,
        "phone_num": user.phone_num,
        "classroom": user.classroom,
        "profile": None
        if profile is None
        else {
            "score": profile.score,
            "project_count": profile.project_count,
            "interests": profile.interests,
            "self_intro": profile.self_intro,
            "avoid_condition": profile.avoid_condition,
        },
        "teams": [
            {
                "team_id": membership.team_id,
                "week": membership.team.week,
                "classroom": membership.team.classroom,
                "team_num": membership.team.team_num,
            }
            for membership in user.team_memberships
        ],
    }


def post_to_dict(post: Post) -> dict:
    return {
        "id": post.id,
        "board_id": post.board_id,
        "user_id": post.user_id,
        "category": post.category,
        "post_title": post.post_title,
        "content": post.content,
        "created_at": post.created_at.isoformat() if post.created_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }


@mcp.tool
def get_all_users_data():
    """학생 기본 정보, 프로필, 팀 배정 정보를 가져오기. 팀 매치 만들때 해당 데이터를 활용한다."""
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.classroom, User.id)).all()
        return [user_to_dict(user) for user in users]


@mcp.tool
def get_all_posts_from_board(board_id: int):
    """선택한 게시판의 게시글 정보 가져오기."""
    with SessionLocal() as db:
        posts = db.scalars(
            select(Post).where(Post.board_id == board_id).order_by(Post.created_at)
        ).all()
        return [post_to_dict(post) for post in posts]




if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8765)
