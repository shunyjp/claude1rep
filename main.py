"""
YouTube AI Summary App
======================
直近7日間のYouTube AI動画の中から重要なものをピックアップし、
Claude Opus 4.6 が日本語でサマリーを生成します。

使い方:
  1. .env.example を .env にコピーして API キーを設定する
  2. pip install -r requirements.txt
  3. python main.py
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


def print_header():
    now = datetime.now().strftime("%Y年%m月%d日 %H:%M")
    print("=" * 60)
    print("  YouTube AI動画サマリー")
    print(f"  生成日時: {now}")
    print("=" * 60)
    print()


def save_result(result: str):
    """Save the summary to a markdown file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"ai_summary_{timestamp}.md"
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"# YouTube AI動画サマリー\n\n生成日時: {datetime.now().strftime('%Y年%m月%d日 %H:%M')}\n\n")
        f.write(result)
    print(f"\n💾 結果を保存しました: {filename}")


def main():
    load_dotenv()

    print_header()

    youtube_key, _ = check_env()

    # Step 1: Fetch AI videos with transcripts from the last 7 days
    videos = fetch_videos_with_transcripts(youtube_key, days=7)

    if not videos:
        print("字幕付きのAI動画が見つかりませんでした。")
        print("ヒント: YouTube_API_KEY が有効か、または対象期間を広げてみてください。")
        sys.exit(0)

    # Step 2: Analyze and summarize with Claude
    print("Claude Opus 4.6 が分析・サマリーを生成中...\n")
    print("-" * 60)

    result = analyze_and_summarize(videos)

    print("-" * 60)

    # Step 3: Save to file
    save_result(result)


if __name__ == "__main__":
    main()
