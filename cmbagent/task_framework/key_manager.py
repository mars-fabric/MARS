import os
from pydantic import BaseModel
from dotenv import load_dotenv

class KeyManager(BaseModel):
    ANTHROPIC: str | None = ""
    GEMINI: str | None = ""
    OPENAI: str | None = ""
    PERPLEXITY: str | None = ""
    SEMANTIC_SCHOLAR: str | None = ""
    AZURE_OPENAI_API_KEY: str | None = ""
    AZURE_OPENAI_ENDPOINT: str | None = ""
    AZURE_OPENAI_DEPLOYMENT: str | None = ""
    AZURE_OPENAI_API_VERSION: str | None = ""

    def get_keys_from_env(self) -> None:

        load_dotenv()

        self.OPENAI                 = os.getenv("OPENAI_API_KEY")
        self.GEMINI                 = os.getenv("GOOGLE_API_KEY")
        self.ANTHROPIC              = os.getenv("ANTHROPIC_API_KEY") #not strictly needed
        self.PERPLEXITY             = os.getenv("PERPLEXITY_API_KEY") #only for citations
        self.SEMANTIC_SCHOLAR       = os.getenv("SEMANTIC_SCHOLAR_KEY") #only for fast semantic scholar
        self.AZURE_OPENAI_API_KEY   = os.getenv("AZURE_OPENAI_API_KEY")
        self.AZURE_OPENAI_ENDPOINT  = os.getenv("AZURE_OPENAI_ENDPOINT")
        self.AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT")
        self.AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")

    def __getitem__(self, key: str) -> str:
        return getattr(self, key)

    def __setitem__(self, key: str, value: str) -> None:
        setattr(self, key, value)
