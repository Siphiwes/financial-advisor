from app.core.security import (
    create_access_token,
    decode_access_token,
    get_email_lookup_document_id,
    hash_password,
    verify_password,
)


def test_password_is_hashed_and_verified() -> None:
    password = "Correct horse battery staple 2026"
    password_hash = hash_password(password)

    assert password_hash != password
    assert verify_password(password, password_hash)
    assert not verify_password("incorrect password", password_hash)


def test_access_token_contains_validated_user_claims(monkeypatch) -> None:
    monkeypatch.setenv("JWT_SECRET_KEY", "j" * 48)
    monkeypatch.setenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15")

    token = create_access_token(
        user_id="user-123",
        user_document_id="user:email:" + ("a" * 64),
        auth_version=1,
    )

    claims = decode_access_token(token)

    assert claims is not None
    assert claims["sub"] == "user-123"
    assert claims["ver"] == 1
    assert claims["typ"] == "access"


def test_email_lookup_id_is_keyed_and_does_not_contain_email(monkeypatch) -> None:
    monkeypatch.setenv("AUTH_EMAIL_INDEX_KEY", "i" * 48)

    document_id = get_email_lookup_document_id("Person@Example.com")

    assert document_id.startswith("user:email:")
    assert "person" not in document_id
    assert len(document_id.rsplit(":", maxsplit=1)[1]) == 64
