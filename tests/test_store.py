from gpt_brain_web_mcp.store import Store


def test_store_sessions_jobs_and_profile(tmp_path):
    store = Store(tmp_path / "brain.db")
    store.upsert_profile(str(tmp_path / "profile"), "logged_in", True)
    assert store.get_profile()["login_state"] == "logged_in"
    sid = store.create_session("proj", "thinking_heavy")
    store.add_message(sid, "user", "hello sk-abc1234567890")
    store.update_session(sid, conversation_url="https://chatgpt.com/c/1", resolved_tier="thinking_heavy")
    job = store.create_job("proj", "research", "thinking_heavy", "deep_research")
    store.update_job(job, status="completed", result_redacted="done", sources_json=[{"url": "https://example.com"}])
    listed = store.list_sessions("proj")
    assert listed["sessions"][0]["conversation_url"] == "https://chatgpt.com/c/1"
    assert listed["jobs"][0]["status"] == "completed"
    assert store.get_job(job)["sources"][0]["url"] == "https://example.com"
