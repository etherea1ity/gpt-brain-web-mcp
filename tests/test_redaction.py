from gpt_brain_web_mcp.redaction import redact_obj, redact_text


def test_redacts_common_secrets():
    text = "sk-abc1234567890 Bearer abc.def ghp_abcdefghijklmnop AWS_SECRET_ACCESS_KEY=abcdef1234567890 Authorization: Bearer nope"
    out = redact_text(text)
    assert "sk-" not in out
    assert "ghp_" not in out
    assert "abcdef1234567890" not in out
    assert "Bearer abc" not in out
    assert "[REDACTED" in out


def test_redacts_nested_objects():
    obj = {"token": "github_pat_abc", "nested": ["Authorization: Bearer secret"]}
    out = redact_obj(obj)
    assert "github_pat_" not in str(out)
    assert "Bearer secret" not in str(out)


def test_redacts_cookie_and_session_headers():
    text = "Cookie: __Secure-next-auth.session-token=abc123; other=value\nSet-Cookie: sessionid=secret; HttpOnly\nsession_token=flatsecret csrf_token=csrfsecret Authorization: Basic abcdef"
    out = redact_text(text)
    assert "abc123" not in out
    assert "sessionid=secret" not in out
    assert "flatsecret" not in out
    assert "csrfsecret" not in out
    assert "Basic abcdef" not in out
    assert "Cookie: [REDACTED]" in out
    assert "Set-Cookie: [REDACTED]" in out


def test_redacts_signed_secret_bearing_urls():
    text = "see https://example.com/file?X-Amz-Signature=abcdef&token=secret&safe=ok and https://user:pass@example.org/a?x=1"
    out = redact_text(text)
    assert "abcdef" not in out
    assert "token=secret" not in out
    assert "safe=ok" in out
    assert "user:pass" not in out
