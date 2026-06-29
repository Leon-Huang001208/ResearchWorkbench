"""Repository base session compatibility tests."""


def test_get_session_returns_closeable_session():
    from sqlalchemy.orm import Session

    from data_layer.repositories.base import get_session

    session = get_session()
    try:
        assert isinstance(session, Session)
    finally:
        session.close()
