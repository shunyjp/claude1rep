"""
YouTube Data API v3 client for searching AI-related videos
and fetching their transcripts.
"""

import sys
from datetime import datetime, timedelta, timezone

import requests
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

# Search queries to find important AI videos
SEARCH_QUERIES = [
    "artificial intelligence news",
    "AI breakthrough",
    "large language model LLM",
    "OpenAI ChatGPT",
    "Anthropic Claude AI",
    "Google Gemini AI",
    "AI technology 2025",
]

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# Max transcript characters per video to keep token usage reasonable
MAX_TRANSCRIPT_CHARS = 8000


def search_ai_videos(api_key: str, days: int = 7, max_per_query: int = 8) -> list[dict]:
    """
    Search YouTube for AI-related videos published within the last `days` days.
    Returns a deduplicated list of video metadata dicts.
    """
    published_after = (
        datetime.now(timezone.utc) - timedelta(days=days)
    ).strftime("%Y-%m-%dT%H:%M:%SZ")

    seen_ids: set[str] = set()
    videos: list[dict] = []

    for query in SEARCH_QUERIES:
        params = {
            "key": api_key,
            "part": "snippet",
            "q": query,
            "type": "video",
            "order": "relevance",
            "publishedAfter": published_after,
            "maxResults": max_per_query,
            "videoCaption": "closedCaption",  # only videos with captions
        }

        try:
            resp = requests.get(YOUTUBE_SEARCH_URL, params=params, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"  [警告] YouTube検索失敗 (query='{query}'): {e}", file=sys.stderr)
            continue

        data = resp.json()

        for item in data.get("items", []):
            video_id = item["id"].get("videoId")
            if not video_id or video_id in seen_ids:
                continue

            seen_ids.add(video_id)
            snippet = item["snippet"]
            videos.append(
                {
                    "id": video_id,
                    "title": snippet.get("title", ""),
                    "channel": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "description": snippet.get("description", "")[:300],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                }
            )

    return videos


def get_transcript(video_id: str) -> str | None:
    """
    Fetch the transcript for a YouTube video.
    Tries English first, then Japanese, then any available language.
    Returns a plain-text string truncated to MAX_TRANSCRIPT_CHARS, or None.
    """
    # Preferred language order
    language_preferences = ["en", "en-US", "en-GB", "ja"]

    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(
            video_id, languages=language_preferences
        )
    except (TranscriptsDisabled, NoTranscriptFound, VideoUnavailable):
        # Try any available language as fallback
        try:
            all_transcripts = YouTubeTranscriptApi.list_transcripts(video_id)
            transcript_obj = next(iter(all_transcripts))
            transcript_list = transcript_obj.fetch()
        except Exception:
            return None
    except Exception:
        return None

    text = " ".join(entry.get("text", "") for entry in transcript_list)
    return text[:MAX_TRANSCRIPT_CHARS] if text else None


def fetch_videos_with_transcripts(
    api_key: str, days: int = 7
) -> list[dict]:
    """
    High-level function: search for AI videos and attach transcripts.
    Returns only videos for which a transcript was successfully retrieved.
    """
    print(f"YouTube で直近 {days} 日間の AI 動画を検索中...")
    videos = search_ai_videos(api_key, days=days)
    print(f"  → {len(videos)} 件の動画候補を取得")

    print("字幕テキストを取得中...")
    results: list[dict] = []
    for i, video in enumerate(videos, 1):
        vid_id = video["id"]
        transcript = get_transcript(vid_id)
        if transcript:
            video["transcript"] = transcript
            results.append(video)
            print(f"  [{i}/{len(videos)}] ✓ {video['title'][:60]}")
        else:
            print(f"  [{i}/{len(videos)}] — 字幕なし: {video['title'][:60]}")

    print(f"\n字幕取得済み: {len(results)} 件\n")
    return results
