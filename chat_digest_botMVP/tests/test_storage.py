from app.services.storage import InMemorySessionStore


def test_session_store_returns_same_session_for_user():
    store = InMemorySessionStore()
    first = store.get(123)
    second = store.get(123)

    assert first is second


def test_clear_resets_session_messages():
    store = InMemorySessionStore()
    session = store.get(123)
    session.messages.append("anything")  # type: ignore[arg-type]

    store.clear(123)

    assert store.get(123).messages == []
