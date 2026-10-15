"""@model_call: an answer entered the study from a language model."""
from .._base import Concern

TOKENS = ("openai", "anthropic", "litellm", "ollama", "cohere", "mistral",
          "chat.completions", "messages.create", "completions.create",
          "chat.complete", "generate_content", "transformers", "huggingface")
CALLS = {"OpenAI", "AzureOpenAI", "Anthropic", "ChatCompletion", "ChatOpenAI"}


def detect(v):
    hits = v.hits(TOKENS, CALLS)
    return (f"calls a language model: {', '.join(hits[:2])}", "high") if hits else None


CONCERN = Concern(
    "model_call",
    "Output came from a language model: are model, version, prompt and parameters recorded?",
    detect)
