"""
Web Enrichment Module
=====================
既存のAI動画サマリーMarkdownを入力として受け取り、
Web 検索で追加情報・ファクトチェック・関連ソースを収集し、
NotebookLM 読み込みに最適化した詳細ドキュメントを生成します。

Claude 使用時: Anthropic サーバーサイド Web Search ツール
Gemini 使用時: Google Search グラウンディング

使い方:
  python enrich.py [markdown_file]        # 指定ファイルを入力
  python enrich.py                        # 最新の ai_summary_*.md を自動選択
"""

import glob
import os
import sys
from datetime import datetime

from llm_client import call_llm_with_search, get_provider_model

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
    return max(files)


def read_markdown(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def build_enrichment_prompt(summary_text: str) -> str:
    return f"""\
以下は直近の重要AI動画サマリーです。

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


def enrich_summary(summary_text: str, provider: str = "claude") -> str:
    """
    Web 検索付き LLM でサマリーを詳細化する（バッチモード）。
    provider: "claude" | "gemini"
    """
    prompt = build_enrichment_prompt(summary_text)
    return call_llm_with_search(provider, SYSTEM_PROMPT, prompt, max_tokens=8000)


def save_enriched(content: str, source_file: str, provider: str = "claude") -> str:
    """強化済みコンテンツを新しいMarkdownファイルとして保存する。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"ai_enriched_{timestamp}.md"
    model_label = get_provider_model(provider)

    header = (
        f"# AI週次詳細レポート（NotebookLM最適化版）\n\n"
        f"> 生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n"
        f"> 元ソース: {source_file}\n"
        f"> 生成モデル: {model_label} + Web Search\n\n"
        f"---\n\n"
    )

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write(content)

    return output_path


def main():
    provider = "claude"
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--provider" and i < len(sys.argv):
            provider = sys.argv[i + 1]

    # コマンドライン引数 or 最新ファイルの自動選択
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    input_file = args[0] if args else find_latest_summary()

    if not input_file:
        print("エラー: 入力ファイルが見つかりません。")
        print("使い方: python enrich.py [ai_summary_*.md] [--provider claude|gemini]")
        sys.exit(1)

    if not os.path.exists(input_file):
        print(f"エラー: ファイルが存在しません: {input_file}")
        sys.exit(1)

    print("=" * 60)
    print("  AI動画サマリー 情報強化・ファクトチェック")
    print(f"  入力ファイル: {input_file}")
    print(f"  プロバイダー: {provider} ({get_provider_model(provider)})")
    print("=" * 60)
    print()

    summary_text = read_markdown(input_file)

    print(f"{get_provider_model(provider)} + Web Search で情報収集・補完中...\n")
    print("-" * 60)

    enriched = enrich_summary(summary_text, provider=provider)

    print("-" * 60)

    output_path = save_enriched(enriched, input_file, provider=provider)
    print(f"\n💾 強化済みレポートを保存しました: {output_path}")
    print(f"📚 NotebookLM にこのファイルをアップロードして活用できます。")


if __name__ == "__main__":
    main()
