"""Optional generation step for RAG.

If ANTHROPIC_API_KEY is set, retrieved passages are sent to Claude to write the
answer. Without a key the chatbot returns the retrieved clinic text directly, so
the app works fully offline.

Patient messages are sent to an external service. Only enable this after the data
processing agreement and the privacy notice cover it.
"""
import logging
import os

log = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are the virtual assistant for a medical clinic. Answer the patient's message using only "
    "the context passages provided. Never diagnose or prescribe. If the context does not answer the "
    "question, say so and suggest booking with a doctor. If the message describes an emergency, tell "
    "the patient to call 112 immediately. Keep the answer under 80 words."
)
LANGUAGE_NOTE = {"en": "Reply in English.", "de": "Reply in German."}


class LLMClient:
    def __init__(self, api_key, model):
        import anthropic  # imported lazily so the app runs without the package

        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    @classmethod
    def from_env(cls):
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            return None
        try:
            return cls(api_key, os.environ.get("CLAUDE_MODEL", "claude-haiku-5-5"))
        except ImportError:
            log.warning("ANTHROPIC_API_KEY is set but the 'anthropic' package is not installed.")
            return None

    def answer(self, question, passages, lang="en"):
        context = "\n\n".join(f"[{p['title']}]\n{p.get('text_de' if lang == 'de' else 'text', p['text'])}"
                              for p in passages)
        response = self.client.messages.create(
            model=self.model,
            max_tokens=400,
            system=f"{SYSTEM_PROMPT} {LANGUAGE_NOTE.get(lang, LANGUAGE_NOTE['en'])}",
            messages=[{
                "role": "user",
                "content": f"Context:\n{context}\n\nPatient message: {question}",
            }],
        )
        parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return "".join(parts).strip()