"""
YouTube AI Summary App
======================
直近7日間のYouTube AI動画の中から重要なものをピックアップし、
Claude Opus 4.6 が日本語でサマリーを生成します。
オプションで Web 検索による情報強化・ファクトチェックも実行します。

使い方:
  python main.py                    # サマリー生成のみ（直近30日）
  python main.py --enrich           # サマリー生成 + Web 強化（NotebookLM最適化）
  python main.py --days 60          # 検索範囲を60日に拡張
  python main.py --days 60 --enrich # 範囲拡張 + Web 強化
"""

import os
import sys
from datetime import datetime

from dotenv import load_dotenv

from summarizer import analyze_and_summarize
from youtube_client import fetch_videos_with_transcripts


def check_env() -> tuple[str, str]:
    """Validate required environment variables."""
    youtube_key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

    errors = []
    if not youtube_key:
        errors.append("YOUTUBE_API_KEY が設定されていません。")
    if not anthropic_key:
        errors.append("ANTHROPIC_API_KEY が設定されていません。")

    if errors:
        print("エラー: 以下の環境変数を .env ファイルに設定してください。", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\n.env.example を参考に .env ファイルを作成してください。", file=sys.stderr)
        sys.exit(1)

    return youtube_key, anthropic_key


def print_header(enrich_mode: bool = False):
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    print("=" * 60)
    print("  YouTube AI動画サマリー")
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


def parse_days() -> int:
    """--days N オプションを解析。デフォルト30日。"""
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--days" and i < len(sys.argv):
            try:
                return int(sys.argv[i + 1])
            except (IndexError, ValueError):
                pass
    return 30


def main():
    load_dotenv()

    enrich_mode = "--enrich" in sys.argv
    days = parse_days()

    print_header(enrich_mode)

    youtube_key, _ = check_env()

    # Step 1: Fetch AI videos with transcripts
    videos = fetch_videos_with_transcripts(youtube_key, days=days)

    if not videos:
        print("AI動画が見つかりませんでした。")
        print("ヒント: YOUTUBE_API_KEY が有効か確認し、--days で検索範囲を広げてみてください。")
        print("例: python main.py --days 60")
        sys.exit(0)

    # Step 2: Analyze and summarize with Claude
    print("Claude Opus 4.6 が分析・サマリーを生成中...\n")
    print("-" * 60)

    result = analyze_and_summarize(videos)

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

        # Import here to avoid loading the module unnecessarily
        from enrich import enrich_summary, save_enriched

        print("Claude Opus 4.6 + Web Search で情報収集・補完中...\n")
        print("-" * 60)

        enriched = enrich_summary(result)

        print("-" * 60)

        enriched_file = save_enriched(enriched, summary_file)
        print(f"\n📚 NotebookLM 用強化レポート: {enriched_file}")
        print("   → Google NotebookLM (https://notebooklm.google.com/) にアップロードしてください。")
    else:
        print()
        print("ヒント: Web強化モードは `python main.py --enrich` で実行できます。")
        print("       生成された Markdown を NotebookLM に読み込む際は強化モードを推奨します。")


if __name__ == "__main__":
    main()
