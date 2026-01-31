"""YouTube API service for video uploads and management."""

import json
import os
import pickle
import random
import time
from pathlib import Path
from typing import Any, Callable, Optional

import httplib2
from googleapiclient.discovery import build, Resource
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage

from ..config import CREDENTIALS_FILE, TOKEN_FILE, CONFIG_DIR

YOUTUBE_UPLOAD_SCOPE = "https://www.googleapis.com/auth/youtube.upload"
YOUTUBE_READONLY_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MAX_RETRIES = 10
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)

httplib2.RETRIES = 1


class YouTubeService:
    """Service for interacting with YouTube API."""

    def __init__(self) -> None:
        self._youtube: Optional[Resource] = None

    def authenticate(self, scopes: list[str] | None = None) -> Resource:
        """Authenticate with YouTube API."""
        if scopes is None:
            scopes = [YOUTUBE_UPLOAD_SCOPE, YOUTUBE_READONLY_SCOPE]

        if not CREDENTIALS_FILE.exists():
            raise FileNotFoundError(
                f"OAuth credentials not found at {CREDENTIALS_FILE}\n"
                "Run 'tubecast setup' to configure credentials."
            )

        flow = flow_from_clientsecrets(
            str(CREDENTIALS_FILE),
            scope=scopes,
            message=f"Please configure OAuth credentials at {CREDENTIALS_FILE}",
        )

        storage = Storage(str(CONFIG_DIR / "oauth2.json"))
        credentials = storage.get()

        if credentials is None or credentials.invalid:
            from oauth2client.tools import run_flow, argparser
            args = argparser.parse_args([])
            credentials = run_flow(flow, storage, args)

        self._youtube = build(
            YOUTUBE_API_SERVICE_NAME,
            YOUTUBE_API_VERSION,
            http=credentials.authorize(httplib2.Http()),
        )
        return self._youtube

    @property
    def youtube(self) -> Resource:
        """Get authenticated YouTube service."""
        if self._youtube is None:
            self.authenticate()
        return self._youtube

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str,
        tags: list[str] | None = None,
        category: str = "22",
        privacy: str = "unlisted",
        made_for_kids: bool = False,
        contains_synthetic_media: bool = True,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Upload a video to YouTube."""
        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category,
            },
            "status": {
                "privacyStatus": privacy,
                "selfDeclaredMadeForKids": made_for_kids,
                "containsSyntheticMedia": contains_synthetic_media,
            },
        }

        media = MediaFileUpload(file_path, chunksize=1024 * 1024, resumable=True)

        insert_request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = self._resumable_upload(insert_request, progress_callback)
        return response

    def _resumable_upload(
        self,
        insert_request: Any,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> dict[str, Any]:
        """Execute resumable upload with retry logic."""
        response = None
        error = None
        retry = 0

        while response is None:
            try:
                status, response = insert_request.next_chunk()
                if status and progress_callback:
                    progress_callback(
                        int(status.resumable_progress),
                        int(status.total_size),
                    )
                if response is not None:
                    if "id" in response:
                        return response
                    raise Exception(f"Upload failed: {response}")
            except HttpError as e:
                if e.resp.status in RETRIABLE_STATUS_CODES:
                    error = f"HTTP error {e.resp.status}: {e.content}"
                else:
                    raise
            except RETRIABLE_EXCEPTIONS as e:
                error = f"Retriable error: {e}"

            if error is not None:
                retry += 1
                if retry > MAX_RETRIES:
                    raise Exception(f"Upload failed after {MAX_RETRIES} retries: {error}")

                sleep_seconds = random.random() * (2 ** retry)
                time.sleep(sleep_seconds)
                error = None

        return response or {}

    def list_videos(self, max_results: int = 10) -> list[dict]:
        """List user's uploaded videos."""
        channels = self.youtube.channels().list(part="contentDetails", mine=True).execute()

        if not channels.get("items"):
            return []

        uploads_playlist_id = channels["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

        videos = []
        request = self.youtube.playlistItems().list(
            part="snippet,status",
            playlistId=uploads_playlist_id,
            maxResults=max_results,
        )

        while request and len(videos) < max_results:
            response = request.execute()
            videos.extend(response.get("items", []))
            request = self.youtube.playlistItems().list_next(request, response)

        return videos[:max_results]

    def get_video(self, video_id: str) -> dict:
        """Get video details by ID."""
        response = self.youtube.videos().list(
            part="snippet,status,statistics,contentDetails",
            id=video_id,
        ).execute()

        if response.get("items"):
            return response["items"][0]
        raise ValueError(f"Video not found: {video_id}")

    def update_video(
        self,
        video_id: str,
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        category: str | None = None,
        privacy: str | None = None,
    ) -> dict:
        """Update video metadata."""
        video = self.get_video(video_id)

        snippet = video["snippet"]
        status = video["status"]

        if title:
            snippet["title"] = title
        if description:
            snippet["description"] = description
        if tags is not None:
            snippet["tags"] = tags
        if category:
            snippet["categoryId"] = category

        body = {"id": video_id, "snippet": snippet}

        if privacy:
            status["privacyStatus"] = privacy
            body["status"] = status

        response = self.youtube.videos().update(
            part=",".join(body.keys()),
            body=body,
        ).execute()

        return response

    def set_thumbnail(self, video_id: str, thumbnail_path: str) -> dict:
        """Set custom thumbnail for a video."""
        media = MediaFileUpload(thumbnail_path, mimetype="image/jpeg")
        response = self.youtube.thumbnails().set(
            videoId=video_id,
            media_body=media,
        ).execute()
        return response

    def create_playlist(
        self,
        title: str,
        description: str = "",
        privacy: str = "unlisted",
    ) -> dict:
        """Create a new playlist."""
        body = {
            "snippet": {
                "title": title,
                "description": description,
            },
            "status": {
                "privacyStatus": privacy,
            },
        }

        response = self.youtube.playlists().insert(
            part="snippet,status",
            body=body,
        ).execute()

        return response

    def add_to_playlist(self, playlist_id: str, video_id: str) -> dict:
        """Add a video to a playlist."""
        body = {
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {
                    "kind": "youtube#video",
                    "videoId": video_id,
                },
            },
        }

        response = self.youtube.playlistItems().insert(
            part="snippet",
            body=body,
        ).execute()

        return response

    def list_playlists(self, max_results: int = 25) -> list[dict]:
        """List user's playlists."""
        response = self.youtube.playlists().list(
            part="snippet,status,contentDetails",
            mine=True,
            maxResults=max_results,
        ).execute()

        return response.get("items", [])


def get_video_url(video_id: str) -> str:
    """Get the watch URL for a video."""
    return f"https://youtu.be/{video_id}"


def get_studio_url(video_id: str) -> str:
    """Get the YouTube Studio URL for a video."""
    return f"https://studio.youtube.com/video/{video_id}/edit"
