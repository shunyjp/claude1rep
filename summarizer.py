"""
Claude Opus 4.6-based analyzer and summarizer for YouTube AI videos.

Given a list of videos with transcripts, Claude:
1. Selects the most important/newsworthy videos (up to 7)
2. Produces a concise Japanese summary for each
"""

import anthropic

MODEL = "claude-opus-4-6"

SYSTEM_PROMPT = """\
あなたはAI業界の動向を深く理解しているテクノロジーアナリストです。
YouTubeの動画情報（タイトル、チャンネル名、字幕テキスト）をもとに、
直近7日間のAI関連動画の中から特に重要なものを選定し、
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

## 重要AI動画サマリー（直近7日間）

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
以下は直近7日間のYouTube上のAI関連動画（字幕テキスト付き）です。
合計 {len(videos)} 件の動画候補があります。

この中から特に重要な動画を最大7件選定し、日本語でサマリーを作成してください。

{all_entries}

{OUTPUT_FORMAT}
"""


def analyze_and_summarize(videos: list[dict]) -> str:
    """
    Use Claude Opus 4.6 with adaptive thinking to analyze videos and
    produce a Japanese summary. Streams the response for responsiveness.
    Returns the complete response text.
    """
    if not videos:
        return "字幕付きの動画が見つかりませんでした。"

    client = anthropic.Anthropic()
    prompt = build_prompt(videos)

    collected_text: list[str] = []

    with client.messages.stream(
        model=MODEL,
        max_tokens=4096,
        thinking={"type": "adaptive"},
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for event in stream:
            if event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    chunk = delta.text
                    print(chunk, end="", flush=True)
                    collected_text.append(chunk)
                # thinking_delta is silently skipped (internal reasoning)

    print()  # newline after streaming ends
    return "".join(collected_text)
