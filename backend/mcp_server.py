from fastmcp import FastMCP
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from sqlalchemy import select

from backend.db import Post, SessionLocal, User, Board, select_post
from backend.db import select_student_profile
from db import insert_weekly_summary
from rag import get_llm

mcp = FastMCP()


def user_to_dict(user: User) -> dict:
    # TODO(user_to_dict): 관리자 계정은 기본 결과에서 제외할지 role 필터를 추가한다.
    # 함수 계약: user_to_dict(user: User) -> dict
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
    # TODO(post_to_dict): 댓글 수와 작성자 이름을 함께 반환할지 API 계약을 맞춘다.
    # 함수 계약: post_to_dict(post: Post) -> dict
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
def get_all_users_data() -> list[dict]:
    # TODO(get_all_users_data): classroom/role 필터 파라미터를 추가한다.
    # 함수 계약: get_all_users_data() -> list[dict]
    """학생 기본 정보, 프로필, 팀 배정 정보를 가져오기. 팀 매치 만들때 해당 데이터를 활용한다."""
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.classroom, User.id)).all()
        return [user_to_dict(user) for user in users]


@mcp.tool
def get_all_posts_from_board(board_id: int) -> list[dict]:
    # TODO(get_all_posts_from_board): 댓글과 RAG 출처 요약을 함께 반환하는 옵션을 추가한다.
    # 함수 계약: get_all_posts_from_board(board_id: int) -> list[dict]
    """선택한 게시판의 게시글 정보 가져오기."""
    with SessionLocal() as db:
        posts = db.scalars(
            select(Post).where(Post.board_id == board_id).order_by(Post.created_at)
        ).all()
        return [post_to_dict(post) for post in posts]

@mcp.tool
def create_team_summary(board_id: int, week: int):
    """해당 게시판 게시글을 가지고 이번주 진행 사항 요약글 작성"""
    posts = get_all_posts_from_board(board_id)

    prompt = ChatPromptTemplate.from_messages([
        ("system", "너는 개발 부트캠프 멘토를 돕는 요약 assistant야."),
        ("human", """
        다음은 한 팀의 주간 게시글이야.
        {context}
        
        아래 형식으로 요약해줘
        - summary
        - keywords
        - frequent_questions
        - blocked_points
        - recommended_materials
        """),
    ])
    llm = get_llm()
    parser = StrOutputParser()
    chain = prompt | llm | parser
    #result = chain.invoke("context": "")
    #with SessionLocal() as db:
    #    insert_weekly_summary(db=db,week=week, )








@mcp.tool
def get_team_summary(team_id: int, week: int) -> list[dict]:
    """팀 id와 week에 맞는 해당 주차 팀 요약을 DB의 weekly_summaries테이블에서 에서 가져오기"""
    # TODO(get_team_summary): weekly_summaries와 게시판 근거 문서를 조회해 멘토용 요약을 반환한다.
    # 함수 계약: get_team_summary(team_id: int, week: int) -> dict





@mcp.tool
def search_board_sources(query: str, board_id: int, k: int = 5) -> list[dict]:
    # TODO(search_board_sources): backend.rag.search_board_docs와 연결해 게시판 RAG 검색을 제공한다.
    # 함수 계약: search_board_sources(query: str, board_id: int, k: int = 5) -> list[dict]
    raise NotImplementedError("게시판 RAG 검색 MCP 도구는 아직 구현되지 않았습니다.")



if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8765)
