from app.domain.models import ConversationSession


def test_unknown_role_gets_stable_fallback_label():
    session = ConversationSession(user_id=1)

    assert session.resolve_role(None) == "Человек 1"
    assert session.resolve_role("") == "Человек 1"


def test_known_role_is_returned_as_is():
    session = ConversationSession(user_id=1)

    assert session.resolve_role("Мария") == "Мария"
