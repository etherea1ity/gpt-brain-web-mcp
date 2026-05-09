from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.product_policy import ProductPolicy
from gpt_brain_web_mcp.tools import WebBrainService, expected_tools


def test_policy_defaults_match_product_contract(tmp_path):
    settings = Settings(home=tmp_path, mock_browser=True)
    policy = ProductPolicy.from_settings(settings)
    assert policy.default_backend == "web-chatgpt"
    assert policy.default_tier == "thinking_heavy"
    assert policy.omitted_project_strategy == "new"
    assert policy.omitted_project_retention == "ephemeral"
    assert policy.explicit_project_strategy == "reuse_project"
    assert policy.explicit_project_retention == "persistent"
    assert policy.research_retention == "job"
    assert policy.allow_pro_default is False


def test_resolve_ask_policy_omitted_vs_explicit_project(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    omitted = svc.resolve_policy(project=None)
    explicit = svc.resolve_policy(project="Repo A")
    assert omitted["project"] == "Codex Brain"
    assert omitted["project_explicit"] is False
    assert omitted["conversation_strategy"] == "new"
    assert omitted["retention"] == "ephemeral"
    assert explicit["project"] == "Repo A"
    assert explicit["project_explicit"] is True
    assert explicit["conversation_strategy"] == "reuse_project"
    assert explicit["retention"] == "persistent"


def test_resolve_research_policy_is_async_job_cleanup_default(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    research = svc.resolve_policy(kind="research", project="Repo A")
    assert research["kind"] == "research"
    assert research["conversation_strategy"] == "new_job_conversation"
    assert research["retention"] == "job"
    assert research["cleanup_remote"] is True


def test_policy_tools_are_exposed(tmp_path):
    svc = WebBrainService(Settings(home=tmp_path, mock_browser=True))
    assert "product_policy" in expected_tools()
    assert "resolve_policy" in expected_tools()
    policy = svc.product_policy()
    assert policy["default_backend"] == "web-chatgpt"
    assert "recommended_workflows" in policy
