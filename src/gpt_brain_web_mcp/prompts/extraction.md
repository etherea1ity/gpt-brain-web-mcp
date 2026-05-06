Extraction contract:
- Wait until generation is complete.
- Extract only the assistant's final answer.
- Extract citations/sources when visible.
- If the UI indicates login, CAPTCHA, 2FA, rate limit, or usage limit, return needs_user_action instead of retrying indefinitely.
