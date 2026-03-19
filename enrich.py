"""
Web Enrichment Module
=====================
既存のAI動画サマリーMarkdownを入力として受け取り、
Claude Opus 4.6 の Web Search ツールを使ってインターネット上から
追加情報・ファクトチェック・関連ソースを収集し、
NotebookLM 読み込みに最適化した詳細ドキュメントを生成します。

使い方:
  python enrich.py [markdown_file]        # 指定ファイルを入力
  python enrich.py                        # 最新の ai_summary_*.md を自動選択
"""

import glob
import os
import sys
from datetime import datetime

import anthropic

MODEL = "claude-opus-4-6"
MAX_CONTINUATION = 5  # pause_turn の最大継続回数

SYSTEM_PROMPT = """\
あなたは AI 技術専門のリサーチャー兼ジャーナリストです。
YouTube 動画のサマリーを受け取り、以下の作業を行ってください。

【作業内容】
1. サマリーで言及されている各トピック・AIモデル・企業・出来事について Web 検索を実施する
2. 公式ソース（企業ブログ、論文、プレスリリース、公式ドキュメント）を優先的に探す
3. 信頼できるニュースメディア（TechCrunch, The Verge, Wired, Ars Technica, VentureBeat 等）の記事も収集する
4. サマリー内の主要な主張をファクトチェックし、正確な情報に更新・補足する
5. 各トピックの技術的背景・歴史的文脈・業界への影響を詳しく解説する
6. 日本語圏での関連報道・反応があれば追加する

【NotebookLM 最適化の要件】
- 明確な階層構造（H1 → H2 → H3）を使用する
- すべての情報にソース URL を付与する
- 各トピックに「技術的詳細」「業界への影響」「関連情報」のサブセクションを設ける
- 最後に「参考文献・ソース一覧」セクションをまとめる
- AI 用語・固有名詞には簡潔な説明を追加し、NotebookLM が質問に答えやすくする
- 検索で見つかった情報の信頼度を明示する（例: 公式発表・報道・未確認情報）

出力言語: 日本語（URL・技術用語・固有名詞は英語のまま可）
"""


def find_latest_summary() -> str | None:
    """最新の ai_summary_*.md ファイルを探す。"""
    files = glob.glob("ai_summary_*.md")
    if not files:
        return None
    return max(files)  # ファイル名のタイムスタンプで最新を判定


def read_markdown(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_enrichment_prompt(summary_text: str) -> str:
    return f"""\
以下は直近7日間の重要AI動画サマリーです。

Web 検索を活用して各トピックの情報を詳しく調査し、
NotebookLM への読み込みに最適化した詳細レポートを作成してください。

━━━ 入力サマリー ━━━
{summary_text}
━━━━━━━━━━━━━━━━

【出力形式】

# AI週次詳細レポート：[日付範囲]

## エグゼクティブサマリー
（今週のAI動向を3〜5文で総括）

---

## [トピック番号]. [トピックタイトル]

### 概要
（何が起きたか・なぜ重要か を2〜3文で）

### 詳細情報と背景
（技術的詳細・歴史的文脈・前提知識などを詳しく）

### 検証済み情報とソース
（Web検索で確認した情報を箇条書き、各項目にソースURLを付与）
- ✅ [確認された情報] — 出典: [URL]
- ⚠️ [要注意・未確認の情報]

### 業界・社会への影響
（この出来事がAI業界や社会に与える意味・影響）

### 関連リンク
- [説明](URL)

---

（以降、各トピックを繰り返し）

---

## 参考文献・ソース一覧

### 公式ソース
- [タイトル](URL)

### ニュース・メディア報道
- [タイトル](URL)

### その他参考資料
- [タイトル](URL)

---

## キーワード・用語解説
（本レポートで登場する AI 用語・固有名詞の解説）

| 用語 | 説明 |
|------|------|
| [用語] | [説明] |
"""


def enrich_summary(summary_text: str) -> str:
    """
    Claude Opus 4.6 + Web Search で動画サマリーを詳細化する。
    pause_turn を適切に処理してストリーミングで出力する。
    """
    client = anthropic.Anthropic()
    prompt = build_enrichment_prompt(summary_text)

    messages: list[dict] = [{"role": "user", "content": prompt}]
    collected_text: list[str] = []
    continuations = 0
    current_search_query = ""

    while True:
        with client.messages.stream(
            model=MODEL,
            max_tokens=8000,
            thinking={"type": "adaptive"},
            system=SYSTEM_PROMPT,
            tools=[
                {"type": "web_search_20260209", "name": "web_search"},
                {"type": "web_fetch_20260209", "name": "web_fetch"},
            ],
            messages=messages,
        ) as stream:
            for event in stream:
                # 検索開始を表示
                if event.type == "content_block_start":
                    block = event.content_block
                    if hasattr(block, "type"):
                        if block.type == "server_tool_use":
                            current_search_query = ""
                            print(f"\n  🔍 Web検索/取得中...", flush=True)
                        elif block.type == "web_search_tool_result":
                            print(f"  ✓ 検索結果取得", flush=True)

                # テキストデルタを表示・収集
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "text_delta":
                        print(delta.text, end="", flush=True)
                        collected_text.append(delta.text)
                    elif delta.type == "input_json_delta":
                        # 検索クエリのプレビュー
                        current_search_query += getattr(delta, "partial_json", "")

            final = stream.get_final_message()

        # アシスタントの応答を履歴に追加
        messages.append({"role": "assistant", "content": final.content})

        if final.stop_reason == "end_turn":
            break
        elif final.stop_reason == "pause_turn":
            # サーバーサイドツールの反復上限に達した → 継続
            continuations += 1
            if continuations >= MAX_CONTINUATION:
                print(
                    f"\n  [警告] 最大継続回数 ({MAX_CONTINUATION}) に達しました。",
                    file=sys.stderr,
                )
                break
            print(f"\n  ↻ 継続中 ({continuations}/{MAX_CONTINUATION})...", flush=True)
            # pause_turn の場合はそのまま再送（追加メッセージ不要）
        else:
            # その他の stop_reason（max_tokens 等）
            break

    print()  # ストリーム終了後の改行
    return "".join(collected_text)


def save_enriched(content: str, source_file: str) -> str:
    """強化済みコンテンツを新しいMarkdownファイルとして保存する。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"ai_enriched_{timestamp}.md"

    header = (
        f"# AI週次詳細レポート（NotebookLM最適化版）\n\n"
        f"> 生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n"
        f"> 元ソース: {source_file}\n"
        f"> 生成モデル: Claude Opus 4.6 + Web Search\n\n"
        f"---\n\n"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(content)

    return output_path


def main():
    # コマンドライン引数 or 最新ファイルの自動選択
    if len(sys.argv) >= 2:
        input_file = sys.argv[1]
    else:
        input_file = find_latest_summary()

    if not input_file:
        print("エラー: 入力ファイルが見つかりません。")
        print("使い方: python enrich.py [ai_summary_*.md]")
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"エラー: ファイルが存在しません: {input_file}")
        sys.exit(1)

    print("=" * 60)
    print("  AI動画サマリー 情報強化・ファクトチェック")
    print(f"  入力ファイル: {input_file}")
    print("=" * 60)
    print()

    summary_text = read_markdown(input_file)

    print("Claude Opus 4.6 + Web Search で情報収集・補完中...\n")
    print("-" * 60)

    enriched = enrich_summary(summary_text)

    print("-" * 60)

    output_path = save_enriched(enriched, input_file)
    print(f"\n💾 強化済みレポートを保存しました: {output_path}")
    print(f"📚 NotebookLM にこのファイルをアップロードして活用できます。")


if __name__ == "__main__":
    main()
