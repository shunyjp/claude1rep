"""
YouTube AI Summary App
======================
直近の YouTube AI 動画の中から重要なものをピックアップし、
LLM が日本語でサマリーを生成します。
Claude (Anthropic) または Gemini (Google) を選択できます。

使い方:
  python main.py                              # Claude でサマリー生成（直近30日）
  python main.py --provider gemini            # Gemini でサマリー生成
  python main.py --enrich                     # サマリー生成 + Web 強化
  python main.py --days 60                    # 検索範囲を60日に拡張
  python main.py --provider gemini --enrich   # Gemini + Web 強化

環境変数:
  ANTHROPIC_API_KEY  - Claude 使用時に必須
  GEMINI_API_KEY     - Gemini 使用時に必須
  YOUTUBE_API_KEY    - 常に必須
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from llm_client import get_provider_model
from summarizer import analyze_and_summarize
from youtube_client import fetch_videos_with_transcripts


def check_env(provider: str) -> str:
    """Validate required environment variables. Returns youtube_key."""
    youtube_key = os.environ.get("YOUTUBE_API_KEY", "").strip()

    errors = []
    if not youtube_key:
        errors.append("YOUTUBE_API_KEY が設定されていません。")

    if provider == "gemini":
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            errors.append("GEMINI_API_KEY が設定されていません。")
    else:
        if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
            errors.append("ANTHROPIC_API_KEY が設定されていません。")

    if errors:
        print("エラー: 以下の環境変数を .env ファイルに設定してください。", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(1)

    return youtube_key


def print_header(provider: str, enrich_mode: bool = False):
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    print("=" * 60)
    print("  YouTube AI動画サマリー")
    print(f"  プロバイダー: {provider} ({get_provider_model(provider)})")
    if enrich_mode:
        print("  モード: サマリー生成 + Web強化（NotebookLM最適化）")
    print(f"  生成日時: {now}")
    print("=" * 60)
    print()


def save_result(result: str) -> str:
    """Save the summary to a markdown file. Returns the saved filepath."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_summary_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# YouTube AI動画サマリー\n\n生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n")
        f.write(result)
    print(f"\n💾 サマリーを保存しました: {filename}")
    return filename


def parse_args() -> tuple[str, int, bool]:
    """CLI引数を解析。(provider, days, enrich_mode) を返す。"""
    provider = "claude"
    days = 30
    enrich_mode = "--enrich" in sys.argv

    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--provider" and i + 1 < len(argv):
            provider = argv[i + 1]
        elif arg == "--days" and i + 1 < len(argv):
            try:
                days = int(argv[i + 1])
            except ValueError:
                pass

    if provider not in ("claude", "gemini"):
        print(f"エラー: 不明なプロバイダー '{provider}'。claude または gemini を指定してください。", file=sys.stderr)
        sys.exit(1)

    return provider, days, enrich_mode


def main():
    load_dotenv()

    provider, days, enrich_mode = parse_args()

    print_header(provider, enrich_mode)

    youtube_key = check_env(provider)

    # Step 1: Fetch AI videos with transcripts
    videos = fetch_videos_with_transcripts(youtube_key, days=days)

    if not videos:
        print("AI動画が見つかりませんでした。")
        print("ヒント: YOUTUBE_API_KEY が有効か確認し、--days で検索範囲を広げてみてください。")
        print("例: python main.py --days 60")
        sys.exit(0)

    # Step 2: Analyze and summarize with LLM
    print(f"{get_provider_model(provider)} が分析・サマリーを生成中...\n")
    print("-" * 60)

    result = analyze_and_summarize(videos, provider=provider)

    print("-" * 60)

    # Step 3: Save summary to file
    summary_file = save_result(result)

    # Step 4 (optional): Web enrichment for NotebookLM
    if enrich_mode:
        print()
        print("=" * 60)
        print("  Web検索による情報強化フェーズ")
        print("=" * 60)
        print()

        from enrich import enrich_summary, save_enriched

        print(f"{get_provider_model(provider)} + Web Search で情報収集・補完中...\n")
        print("-" * 60)

        enriched = enrich_summary(result, provider=provider)

        print("-" * 60)

        enriched_file = save_enriched(enriched, summary_file, provider=provider)
        print(f"\n📚 NotebookLM 用強化レポート: {enriched_file}")
        print("   → Google NotebookLM (https://notebooklm.google.com/) にアップロードしてください。")
    else:
        print()
        print("ヒント: Web強化モードは `python main.py --enrich` で実行できます。")
        print("       生成された Markdown を NotebookLM に読み込む際は強化モードを推奨します。")


if __name__ == "__main__":
    main()
