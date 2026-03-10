"""
LLM client for conversational BI agent. Supports Groq (free tier) and Ollama (open source).
"""
from typing import Optional
from config import (
    LLM_PROVIDER,
    GROQ_API_KEY,
    GROQ_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
)


SYSTEM_PROMPT = """You are a Business Intelligence assistant for founders and executives. You answer questions about work orders, deals, pipeline, revenue, and operations using ONLY the data provided below. You do not make up numbers or facts.

Rules:
- Base every number and fact on the "Current data summary and samples" section. If the answer is not in the data, say "I don't have that in the current data" or "The data doesn't include that metric."
- Mention data quality when relevant (e.g. "Values are masked", "Some dates are missing").
- For revenue, pipeline, or sector questions, use the summary statistics and sample rows provided.
- Be concise but insightful. Add brief context or caveats when helpful.
- If the user asks for a "leadership update", "exec summary", or "prep for leadership", provide a short summary with key metrics (pipeline value, work order status, sector breakdown), main caveats (e.g. masked values, missing data), and 2–3 bullet insights.
- If the user's question is ambiguous, ask one short clarifying question (e.g. "Do you mean this quarter or all time?").
"""


def _call_groq(messages: list[dict], api_key: Optional[str] = None) -> str:
    try:
        from groq import Groq
        client = Groq(api_key=api_key or GROQ_API_KEY)
        resp = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=0.2,
            max_tokens=1024,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception as e:
        return f"[Error calling Groq: {e}. Set GROQ_API_KEY or use Ollama.]"


def _call_ollama(messages: list[dict]) -> str:
    try:
        import requests
        # Ollama expects a single "prompt" for chat; we fold system + user into one
        prompt_parts = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        prompt = "\n\n".join(prompt_parts) + "\n\nAssistant:"
        r = requests.post(
            f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=120,
        )
        r.raise_for_status()
        return (r.json().get("response") or "").strip()
    except Exception as e:
        return f"[Error calling Ollama: {e}. Is Ollama running and model pulled?]"


def chat_with_context(user_message: str, data_context: str, history: list[dict]) -> str:
    """
    Send user message with current data context and conversation history.
    Returns assistant reply. Uses only provided context to minimize hallucination.
    """
    system_content = SYSTEM_PROMPT + "\n\n## Current data summary and samples\n\n" + data_context
    messages = [{"role": "system", "content": system_content}]
    for h in history[-10:]:  # last 10 turns
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": user_message})

    if LLM_PROVIDER == "groq" and GROQ_API_KEY:
        return _call_groq(messages)
    return _call_ollama(messages)
