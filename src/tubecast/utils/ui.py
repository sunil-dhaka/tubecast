"""UI utilities for TubeCast."""

from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.table import Table
from rich.text import Text
from rich import box

console = Console()


def print_banner() -> None:
    """Print the TubeCast banner."""
    banner = """
 _____     _          ___          _
|_   _|  _| |__  ___ / __| __ _ __| |_
  | || || | '_ \\/ -_) (__/ _` (_-<  _|
  |_| \\_,_|_.__/\\___|\\___|\\__,_/__/\\__|
"""
    console.print(Panel(
        Text(banner, style="bold cyan") + Text("\n  Professional YouTube uploader with AI", style="dim"),
        box=box.ROUNDED,
        border_style="cyan",
    ))


def print_success(message: str) -> None:
    """Print a success message."""
    console.print(f"[bold green][OK][/] {message}")


def print_error(message: str) -> None:
    """Print an error message."""
    console.print(f"[bold red][ERROR][/] {message}")


def print_warning(message: str) -> None:
    """Print a warning message."""
    console.print(f"[bold yellow][WARN][/] {message}")


def print_info(message: str) -> None:
    """Print an info message."""
    console.print(f"[bold blue][INFO][/] {message}")


def print_step(message: str) -> None:
    """Print a step message."""
    console.print(f"[bold magenta][*][/] {message}")


def print_video_card(video: dict, video_url: str, studio_url: str) -> None:
    """Print a video card with details and links."""
    table = Table(box=box.ROUNDED, border_style="green", show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")

    snippet = video.get("snippet", {})
    status = video.get("status", {})
    stats = video.get("statistics", {})

    table.add_row("Title", snippet.get("title", "N/A"))
    table.add_row("Video ID", video.get("id", "N/A"))
    table.add_row("Privacy", status.get("privacyStatus", "N/A"))
    table.add_row("Views", stats.get("viewCount", "0"))
    table.add_row("Likes", stats.get("likeCount", "0"))
    table.add_row("", "")
    table.add_row("[bold cyan]Watch[/]", f"[link={video_url}]{video_url}[/link]")
    table.add_row("[bold yellow]Studio[/]", f"[link={studio_url}]{studio_url}[/link]")

    console.print(table)


def print_upload_result(video_id: str, title: str) -> None:
    """Print upload result with clickable links."""
    video_url = f"https://youtu.be/{video_id}"
    studio_url = f"https://studio.youtube.com/video/{video_id}/edit"

    panel = Panel(
        f"""[bold green]Upload Successful![/]

[bold]Title:[/] {title}
[bold]Video ID:[/] {video_id}

[bold cyan]Watch:[/] [link={video_url}]{video_url}[/link]
[bold yellow]Studio:[/] [link={studio_url}]{studio_url}[/link]
""",
        title="[bold]Video Uploaded[/]",
        border_style="green",
        box=box.ROUNDED,
    )
    console.print(panel)


def create_progress() -> Progress:
    """Create a progress bar for uploads."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def print_videos_table(videos: list[dict]) -> None:
    """Print a table of videos."""
    table = Table(title="Your Videos", box=box.ROUNDED, border_style="cyan")
    table.add_column("#", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Privacy")
    table.add_column("Published")
    table.add_column("Video ID", style="dim")

    for i, video in enumerate(videos, 1):
        snippet = video.get("snippet", {})
        status = video.get("status", {})

        privacy = status.get("privacyStatus", "unknown")
        privacy_style = {
            "public": "green",
            "unlisted": "yellow",
            "private": "red",
        }.get(privacy, "white")

        published = snippet.get("publishedAt", "")[:10]
        video_id = snippet.get("resourceId", {}).get("videoId", "")

        table.add_row(
            str(i),
            snippet.get("title", "Untitled")[:50],
            f"[{privacy_style}]{privacy}[/]",
            published,
            video_id,
        )

    console.print(table)


def print_playlists_table(playlists: list[dict]) -> None:
    """Print a table of playlists."""
    table = Table(title="Your Playlists", box=box.ROUNDED, border_style="magenta")
    table.add_column("#", style="dim")
    table.add_column("Title", style="bold")
    table.add_column("Videos")
    table.add_column("Privacy")
    table.add_column("Playlist ID", style="dim")

    for i, playlist in enumerate(playlists, 1):
        snippet = playlist.get("snippet", {})
        status = playlist.get("status", {})
        content = playlist.get("contentDetails", {})

        privacy = status.get("privacyStatus", "unknown")
        privacy_style = {
            "public": "green",
            "unlisted": "yellow",
            "private": "red",
        }.get(privacy, "white")

        table.add_row(
            str(i),
            snippet.get("title", "Untitled")[:40],
            str(content.get("itemCount", 0)),
            f"[{privacy_style}]{privacy}[/]",
            playlist.get("id", ""),
        )

    console.print(table)
