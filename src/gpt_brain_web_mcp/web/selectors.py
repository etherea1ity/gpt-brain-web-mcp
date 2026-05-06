from __future__ import annotations

from pathlib import Path

DEFAULT_SELECTORS = {
    "prompt_box": ["role:textbox", "textarea", 'div[contenteditable="true"]'],
    "send_button": ["role:button:Send", 'button[aria-label*="Send"]'],
    "model_picker": ["role:button:Model", 'button[aria-haspopup="menu"]'],
    "source_links": ['a[href^="http"]'],
    "assistant_messages": ['[data-message-author-role="assistant"]', "article"],
}


def load_simple_yaml(path: str | Path) -> dict[str, object]:
    # Tiny YAML subset parser for this project's list-based config; avoids mandatory PyYAML.
    p = Path(path)
    if not p.exists(): return {}
    root: dict[str, object] = {}; current_key = None; current_list = None
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if not line.strip() or line.lstrip().startswith("#"): continue
        if not line.startswith(" ") and line.endswith(":"):
            current_key = line[:-1]; root[current_key] = {}; current_list = None
        elif current_key and line.startswith("  ") and line.strip().endswith(":"):
            sub = line.strip()[:-1]
            if not isinstance(root[current_key], dict): root[current_key] = {}
            root[current_key][sub] = []
            current_list = root[current_key][sub]
        elif current_key and line.strip().startswith("-"):
            val = line.strip()[1:].strip().strip('"').strip("'")
            if current_list is not None: current_list.append(val)
            elif isinstance(root[current_key], list): root[current_key].append(val)
        elif current_key and ":" in line:
            k, v = line.strip().split(":", 1)
            val = v.strip().lower()
            parsed = True if val == "true" else False if val == "false" else v.strip()
            if isinstance(root[current_key], dict): root[current_key][k] = parsed
    return root


def load_selectors(path: str | Path | None = None) -> dict[str, list[str]]:
    if not path: return DEFAULT_SELECTORS
    data = load_simple_yaml(path)
    out = {**DEFAULT_SELECTORS}
    for key, value in data.items():
        if isinstance(value, list): out[key] = [str(v) for v in value]
    return out
