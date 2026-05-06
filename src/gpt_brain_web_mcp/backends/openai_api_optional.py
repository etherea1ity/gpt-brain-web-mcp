class OpenAIAPIOptionalBackend:
    name = "openai-api-optional"
    def ask_brain(self, *args, **kwargs):
        raise RuntimeError("OpenAI API backend is optional fallback only and not enabled in V1 default path.")
