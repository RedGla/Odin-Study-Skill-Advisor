import models
import usage_service
from tests.helpers import auth_client, cleanup_user, create_user


def test_usage_requires_authentication(client):
    assert client.get("/usage/me").status_code == 401


def test_new_user_usage_is_zero(client, db):
    user = create_user(db)
    try:
        response = auth_client(client, user).get("/usage/me")
        assert response.status_code == 200
        assert response.json()["messages_today"] == 0
    finally:
        cleanup_user(str(user.id))


def test_user_sees_only_own_daily_usage(client, db):
    user = create_user(db)
    other = create_user(db)
    db.add_all([
        models.UsageCounter(user_id=user.id, date_str=usage_service._today_str(), messages_today=3, tokens_today=25, est_spend_today=0),
        models.UsageCounter(user_id=other.id, date_str=usage_service._today_str(), messages_today=17, tokens_today=200, est_spend_today=0),
    ])
    db.commit()
    try:
        response = auth_client(client, user).get("/usage/me")
        assert response.status_code == 200
        body = response.json()
        assert body["date"] == usage_service._today_str()
        assert body["messages_today"] == 3
        assert body["daily_message_cap"] > 0
        assert "user_id" not in body
    finally:
        cleanup_user(str(user.id))
        cleanup_user(str(other.id))
