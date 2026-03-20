"""
LLM Client Abstraction
======================
Claude (Anthropic) および Gemini (Google) の両方に対応した
バッチ（非ストリーミング）モードの共通インターフェース。

環境変数:
  ANTHROPIC_API_KEY  - Claude 使用時に必須
  GEMINI_API_KEY     - Gemini 使用時に必須
"""

import os
import sys

CLAUDE_DEFAULT_MODEL = "claude-opus-4-6"
GEMINI_DEFAULT_MODEL = "gemini-2.0-flash"

# Claude server-side web search tools
CLAUDE_SEARCH_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search"},
    {"type": "web_fetch_20260209", "name": "web_fetch"},
]

MAX_PAUSE_CONTINUATIONS = 5


def get_provider_model(provider: str) -> str:
    """プロバイダーのデフォルトモデル名を返す。"""
    if provider == "gemini":
        return GEMINI_DEFAULT_MODEL
    return CLAUDE_DEFAULT_MODEL


# ---------------------------------------------------------------------------
# Claude (Anthropic) バッチ呼び出し
# ---------------------------------------------------------------------------

def _claude_client():
    import anthropic
    return anthropic.Anthropic()


def _call_claude(system: str, prompt: str, max_tokens: int) -> str:
    """Claude を非ストリーミング（バッチ）モードで呼び出す。"""
    client = _claude_client()
    response = client.messages.create(
        model=CLAUDE_DEFAULT_MODEL,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in response.content if b.type == "text")


def _call_claude_with_search(system: str, prompt: str, max_tokens: int) -> str:
    """
    Claude + サーバーサイド Web Search を非ストリーミングで呼び出す。
    pause_turn を処理して複数ターンの検索を継続する。
    """
    client = _claude_client()
    messages: list[dict] = [{"role": "user", "content": prompt}]
    collected_text: list[str] = []
    continuations = 0

    while True:
        print("  [Claude] API呼び出し中...", flush=True)
        response = client.messages.create(
            model=CLAUDE_DEFAULT_MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=CLAUDE_SEARCH_TOOLS,
            messages=messages,
        )

        # テキストブロックを収集
        for block in response.content:
            if block.type == "text":
                collected_text.append(block.text)
            elif block.type == "server_tool_use":
                tool_input = getattr(block, "input", {})
                query = tool_input.get("query", tool_input.get("url", ""))
                print(f"  [検索] {query[:80]}", flush=True)

        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break
        elif response.stop_reason == "pause_turn":
            continuations += 1
            if continuations >= MAX_PAUSE_CONTINUATIONS:
                print(
                    f"  [警告] 最大継続回数 ({MAX_PAUSE_CONTINUATIONS}) に達しました。",
                    file=sys.stderr,
                )
                break
            print(f"  [継続] {continuations}/{MAX_PAUSE_CONTINUATIONS}", flush=True)
        else:
            break

    return "".join(collected_text)


# ---------------------------------------------------------------------------
# Gemini (Google) バッチ呼び出し
# ---------------------------------------------------------------------------

def _call_gemini(system: str, prompt: str, max_tokens: int) -> str:
    """Gemini を非ストリーミング（バッチ）モードで呼び出す。"""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")

    client = genai.Client(api_key=api_key)
    print("  [Gemini] API呼び出し中...", flush=True)
    response = client.models.generate_content(
        model=GEMINI_DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
        ),
    )
    return response.text or ""


def _call_gemini_with_search(system: str, prompt: str, max_tokens: int) -> str:
    """
    Gemini + Google Search グラウンディングを非ストリーミングで呼び出す。
    """
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY が設定されていません。")

    client = genai.Client(api_key=api_key)
    print("  [Gemini] Google Search グラウンディングで検索中...", flush=True)
    response = client.models.generate_content(
        model=GEMINI_DEFAULT_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system,
            max_output_tokens=max_tokens,
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )
    return response.text or ""


# ---------------------------------------------------------------------------
# 公開 API
# ---------------------------------------------------------------------------

def call_llm(provider: str, system: str, prompt: str, max_tokens: int = 4096) -> str:
    """
    LLM をバッチモードで呼び出す。
    provider: "claude" | "gemini"
    """
    if provider == "gemini":
        return _call_gemini(system, prompt, max_tokens)
    return _call_claude(system, prompt, max_tokens)


def call_llm_with_search(
    provider: str, system: str, prompt: str, max_tokens: int = 8000
) -> str:
    """
    Web 検索付きで LLM をバッチモードで呼び出す。
    provider: "claude" | "gemini"
    """
    if provider == "gemini":
        return _call_gemini_with_search(system, prompt, max_tokens)
    return _call_claude_with_search(system, prompt, max_tokens)
