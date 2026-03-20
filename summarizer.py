"""
LLM-based analyzer and summarizer for YouTube AI videos.

Given a list of videos with transcripts, the LLM:
1. Selects the most important/newsworthy videos (up to 7)
2. Produces a concise Japanese summary for each

Supports Claude (Anthropic) and Gemini (Google) via llm_client.
"""

from llm_client import call_llm

SYSTEM_PROMPT = """\
あなたはAI業界の動向を深く理解しているテクノロジーアナリストです。
YouTubeの動画情報（タイトル、チャンネル名、字幕テキスト）をもとに、
直近の AI 関連動画の中から特に重要なものを選定し、
わかりやすい日本語でサマリーを作成してください。

重要度の判断基準:
- AIの新モデル・新機能のリリース情報
- 業界の大きなニュースや政策・規制の動向
- 研究上のブレークスルーや技術的な重要発見
- 著名人・企業による重大な発表や議論
- 社会的影響が大きいAI活用事例

出力形式:
- 選定した動画ごとに、以下の形式で出力する
- 全体のまとめとして最後に「今週のAIトレンド総括」を1〜2段落で書く
"""

VIDEO_ENTRY_TEMPLATE = """\
---
動画ID: {index}
タイトル: {title}
チャンネル: {channel}
投稿日: {published_at}
URL: {url}
概要: {description}

字幕テキスト（抜粋）:
{transcript}
"""

OUTPUT_FORMAT = """\
以下の形式で出力してください。マークダウンを使ってください。

## 重要AI動画サマリー

### 1. [動画タイトル]
- **URL**: [動画URL]
- **チャンネル**: [チャンネル名]
- **重要度**: ★★★★★（5段階）
- **サマリー**: [3〜5文で内容を要約]
- **ポイント**:
  - [箇条書きで重要ポイント2〜4つ]

（以降、選定した動画分繰り返し）

---

## 今週のAIトレンド総括
[1〜2段落で今週のAI動向全体を総括]
"""


def build_prompt(videos: list[dict]) -> str:
    entries = []
    for i, video in enumerate(videos, 1):
        entry = VIDEO_ENTRY_TEMPLATE.format(
            index=i,
            title=video["title"],
            channel=video["channel"],
            published_at=video.get("published_at", "不明"),
            url=video["url"],
            description=video.get("description", ""),
            transcript=video.get("transcript", "（字幕なし）"),
        )
        entries.append(entry)

    all_entries = "\n".join(entries)

    return f"""\
以下は直近の YouTube 上の AI 関連動画（字幕テキスト付き）です。
合計 {len(videos)} 件の動画候補があります。

この中から特に重要な動画を最大7件選定し、日本語でサマリーを作成してください。

{all_entries}

{OUTPUT_FORMAT}
"""


def analyze_and_summarize(videos: list[dict], provider: str = "claude") -> str:
    """
    LLM をバッチモードで呼び出し、動画リストを分析して日本語サマリーを返す。
    provider: "claude" | "gemini"
    """
    if not videos:
        return "動画が見つかりませんでした。"

    prompt = build_prompt(videos)
    return call_llm(provider, SYSTEM_PROMPT, prompt, max_tokens=4096)
