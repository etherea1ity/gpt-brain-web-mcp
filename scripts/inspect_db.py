from __future__ import annotations
import json
from gpt_brain_web_mcp.config import Settings
from gpt_brain_web_mcp.store import Store

s=Settings.from_env(); store=Store(s.db_path)
print(json.dumps({"home": str(s.home), "profile": store.get_profile(), **store.list_sessions(limit=20)}, indent=2, ensure_ascii=False))
