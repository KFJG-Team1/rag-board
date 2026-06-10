from backend.db import (
    SessionLocal,
    create_all_table,
    drop_all_table,
    insert_user,
    select_user,
)


def test_insert_and_select_user():
    drop_all_table()
    create_all_table()

    db = SessionLocal()
    try:
        user = insert_user(
            db=db,
            name="test",
            github_id="test_github",
            phone_num="010-0000-0000",
            classroom=1,
            team=1,
            score=0,
            project_cnt=0,
        )

        users = select_user(db, user_id=user.id)

        assert len(users) == 1
        assert users[0].name == "test"
        assert users[0].github_id == "test_github"
    finally:
        db.close()