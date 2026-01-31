"""TubeCast CLI - Professional YouTube uploader with AI."""

import json
import shutil
from pathlib import Path
from typing import Optional

import questionary
import typer
from rich.prompt import Confirm

from .config import (
    CONFIG_DIR,
    CREDENTIALS_FILE,
    GEMINI_MODELS,
    PRIVACY_OPTIONS,
    CATEGORY_OPTIONS,
    load_config,
    save_config,
    is_configured,
)
from .services import YouTubeService, GeminiService, get_video_url, get_studio_url, is_gemini_available
from .utils import (
    console,
    print_banner,
    print_success,
    print_error,
    print_warning,
    print_info,
    print_step,
    print_upload_result,
    create_progress,
    print_videos_table,
    print_playlists_table,
    print_video_card,
)

app = typer.Typer(
    name="tubecast",
    help="Professional YouTube video uploader with AI-powered metadata generation",
    add_completion=False,
)


@app.command()
def setup() -> None:
    """Configure TubeCast with OAuth credentials and preferences."""
    print_banner()
    console.print("[bold]Welcome to TubeCast Setup[/]\n")

    # Step 1: OAuth Credentials
    print_step("Step 1: OAuth Credentials")

    if CREDENTIALS_FILE.exists():
        if not Confirm.ask("OAuth credentials already exist. Overwrite?", default=False):
            print_info("Keeping existing credentials")
        else:
            _setup_oauth()
    else:
        _setup_oauth()

    # Step 2: Gemini API (optional)
    print_step("\nStep 2: AI-Powered Metadata (Optional)")
    console.print("Gemini AI can automatically generate titles, descriptions, and tags.\n")

    use_ai = questionary.confirm(
        "Enable AI-powered metadata generation?",
        default=True,
    ).ask()

    config = load_config()
    config["ai_enabled"] = use_ai

    if use_ai:
        api_key = questionary.text(
            "Enter your Gemini API key:",
            instruction="(Get one at https://aistudio.google.com/app/apikey)",
        ).ask()

        if api_key:
            config["gemini_api_key"] = api_key

            model = questionary.select(
                "Select Gemini model:",
                choices=[
                    questionary.Choice(
                        f"{m['label']} - {m['description']}",
                        value=m["value"],
                    )
                    for m in GEMINI_MODELS
                ],
                default=GEMINI_MODELS[0]["value"],
            ).ask()
            config["gemini_model"] = model

    # Step 3: Default preferences
    print_step("\nStep 3: Default Preferences")

    privacy = questionary.select(
        "Default privacy status:",
        choices=[
            questionary.Choice(f"{p['label']} - {p['description']}", value=p["value"])
            for p in PRIVACY_OPTIONS
        ],
        default="unlisted",
    ).ask()
    config["default_privacy"] = privacy

    category = questionary.select(
        "Default video category:",
        choices=[
            questionary.Choice(c["label"], value=c["value"])
            for c in CATEGORY_OPTIONS
        ],
        default="22",
    ).ask()
    config["default_category"] = category

    save_config(config)

    print_success("\nSetup complete!")
    console.print(f"Config saved to: {CONFIG_DIR}")
    console.print("\nRun [bold cyan]tubecast upload[/] to upload your first video!")


def _setup_oauth() -> None:
    """Guide user through OAuth setup."""
    console.print("""
To use TubeCast, you need OAuth 2.0 credentials from Google Cloud Console:

1. Go to https://console.cloud.google.com/
2. Create a project (or select existing)
3. Enable YouTube Data API v3
4. Create OAuth 2.0 credentials (Desktop app)
5. Download the JSON file
""")

    creds_path = questionary.path(
        "Enter path to your client_secret.json file:",
        only_files=True,
    ).ask()

    if creds_path and Path(creds_path).exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy(creds_path, CREDENTIALS_FILE)
        print_success(f"Credentials copied to {CREDENTIALS_FILE}")
    else:
        print_error("Invalid file path. Please run setup again.")


@app.command()
def upload(
    file: Path = typer.Argument(..., help="Video file to upload"),
    title: Optional[str] = typer.Option(None, "--title", "-t", help="Video title"),
    description: Optional[str] = typer.Option(None, "--description", "-d", help="Video description"),
    tags: Optional[str] = typer.Option(None, "--tags", help="Comma-separated tags"),
    privacy: Optional[str] = typer.Option(None, "--privacy", "-p", help="Privacy: public, unlisted, private"),
    category: Optional[str] = typer.Option(None, "--category", "-c", help="Category ID"),
    ai: bool = typer.Option(False, "--ai", help="Use AI to generate metadata"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Interactive mode"),
) -> None:
    """Upload a video to YouTube."""
    if not is_configured():
        print_error("TubeCast not configured. Run 'tubecast setup' first.")
        raise typer.Exit(1)

    if not file.exists():
        print_error(f"File not found: {file}")
        raise typer.Exit(1)

    print_banner()
    config = load_config()

    # Determine metadata source
    if interactive or (not title and not ai):
        _upload_interactive(file, config)
    elif ai:
        _upload_with_ai(file, title, description, tags, privacy, category, config)
    else:
        _upload_direct(file, title, description, tags, privacy, category, config)


def _upload_interactive(file: Path, config: dict) -> None:
    """Interactive upload flow."""
    print_step(f"Uploading: {file.name}\n")

    # Check if AI is available
    use_ai = False
    if config.get("ai_enabled") and is_gemini_available():
        use_ai = questionary.confirm(
            "Generate metadata with AI?",
            default=True,
        ).ask()

    if use_ai:
        print_step("Generating metadata with AI...")
        gemini = GeminiService()

        context = questionary.text(
            "Any context about this video? (optional)",
            instruction="Press Enter to skip",
        ).ask()

        try:
            metadata = gemini.generate_metadata(file.name, context or "")
            title = metadata.get("title", file.stem)
            description = metadata.get("description", "")
            tags = metadata.get("tags", [])

            console.print(f"\n[bold]Generated Title:[/] {title}")
            console.print(f"[bold]Generated Tags:[/] {', '.join(tags[:5])}...")

            if not questionary.confirm("Use this metadata?", default=True).ask():
                title = questionary.text("Title:", default=title).ask()
                description = questionary.text("Description:", default=description).ask()
                tags_str = questionary.text("Tags (comma-separated):", default=",".join(tags)).ask()
                tags = [t.strip() for t in tags_str.split(",") if t.strip()]

        except Exception as e:
            print_warning(f"AI generation failed: {e}")
            use_ai = False

    if not use_ai:
        title = questionary.text("Title:", default=file.stem).ask()
        description = questionary.text("Description:", default="").ask()
        tags_str = questionary.text("Tags (comma-separated):", default="").ask()
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    privacy = questionary.select(
        "Privacy:",
        choices=[p["value"] for p in PRIVACY_OPTIONS],
        default=config.get("default_privacy", "unlisted"),
    ).ask()

    category = questionary.select(
        "Category:",
        choices=[questionary.Choice(c["label"], value=c["value"]) for c in CATEGORY_OPTIONS],
        default=config.get("default_category", "22"),
    ).ask()

    _do_upload(file, title, description, tags, privacy, category, config)


def _upload_with_ai(
    file: Path,
    title: Optional[str],
    description: Optional[str],
    tags: Optional[str],
    privacy: Optional[str],
    category: Optional[str],
    config: dict,
) -> None:
    """Upload with AI-generated metadata."""
    print_step("Generating metadata with AI...")

    gemini = GeminiService()

    try:
        metadata = gemini.generate_metadata(file.name)
        final_title = title or metadata.get("title", file.stem)
        final_description = description or metadata.get("description", "")
        final_tags = tags.split(",") if tags else metadata.get("tags", [])

    except Exception as e:
        print_warning(f"AI generation failed: {e}")
        final_title = title or file.stem
        final_description = description or ""
        final_tags = tags.split(",") if tags else []

    _do_upload(
        file,
        final_title,
        final_description,
        final_tags,
        privacy or config.get("default_privacy", "unlisted"),
        category or config.get("default_category", "22"),
        config,
    )


def _upload_direct(
    file: Path,
    title: Optional[str],
    description: Optional[str],
    tags: Optional[str],
    privacy: Optional[str],
    category: Optional[str],
    config: dict,
) -> None:
    """Direct upload with provided metadata."""
    _do_upload(
        file,
        title or file.stem,
        description or "",
        tags.split(",") if tags else [],
        privacy or config.get("default_privacy", "unlisted"),
        category or config.get("default_category", "22"),
        config,
    )


def _do_upload(
    file: Path,
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    category: str,
    config: dict,
) -> None:
    """Execute the upload."""
    print_step(f"Uploading: {title}")

    youtube = YouTubeService()
    youtube.authenticate()

    with create_progress() as progress:
        task = progress.add_task("Uploading...", total=100)

        def update_progress(current: int, total: int) -> None:
            if total > 0:
                progress.update(task, completed=int(current / total * 100))

        try:
            response = youtube.upload_video(
                file_path=str(file),
                title=title,
                description=description,
                tags=tags,
                category=category,
                privacy=privacy,
                made_for_kids=config.get("made_for_kids", False),
                contains_synthetic_media=config.get("contains_synthetic_media", True),
                progress_callback=update_progress,
            )

            progress.update(task, completed=100)

        except Exception as e:
            print_error(f"Upload failed: {e}")
            raise typer.Exit(1)

    video_id = response.get("id")
    if video_id:
        print_upload_result(video_id, title)
    else:
        print_error("Upload completed but no video ID returned")


@app.command()
def batch(
    folder: Path = typer.Argument(..., help="Folder containing videos to upload"),
    privacy: Optional[str] = typer.Option(None, "--privacy", "-p", help="Privacy for all videos"),
    ai: bool = typer.Option(False, "--ai", help="Use AI to generate metadata"),
) -> None:
    """Upload multiple videos from a folder."""
    if not is_configured():
        print_error("TubeCast not configured. Run 'tubecast setup' first.")
        raise typer.Exit(1)

    if not folder.exists() or not folder.is_dir():
        print_error(f"Folder not found: {folder}")
        raise typer.Exit(1)

    print_banner()

    videos = list(folder.glob("*.mp4")) + list(folder.glob("*.mkv")) + list(folder.glob("*.mov"))

    if not videos:
        print_error("No video files found in folder")
        raise typer.Exit(1)

    print_info(f"Found {len(videos)} videos to upload\n")

    config = load_config()
    results: list[tuple[str, str, str]] = []

    for i, video in enumerate(videos, 1):
        console.print(f"\n[bold][{i}/{len(videos)}] {video.name}[/]")

        try:
            youtube = YouTubeService()
            youtube.authenticate()

            if ai and config.get("ai_enabled"):
                gemini = GeminiService()
                metadata = gemini.generate_metadata(video.name)
                title = metadata.get("title", video.stem)
                description = metadata.get("description", "")
                tags = metadata.get("tags", [])
            else:
                # Check for JSON metadata file
                json_file = video.with_suffix(".json")
                if json_file.exists():
                    with open(json_file) as f:
                        metadata = json.load(f)
                    title = metadata.get("title", video.stem)
                    description = metadata.get("description", "")
                    tags = metadata.get("tags", "").split(",") if isinstance(metadata.get("tags"), str) else metadata.get("tags", [])
                else:
                    title = video.stem
                    description = ""
                    tags = []

            response = youtube.upload_video(
                file_path=str(video),
                title=title,
                description=description,
                tags=tags,
                privacy=privacy or config.get("default_privacy", "unlisted"),
            )

            video_id = response.get("id", "")
            results.append((video.name, video_id, get_video_url(video_id)))
            print_success(f"Uploaded: {get_video_url(video_id)}")

        except Exception as e:
            print_error(f"Failed: {e}")
            results.append((video.name, "", str(e)))

    # Summary
    console.print("\n[bold]Upload Summary[/]")
    for name, video_id, url in results:
        if video_id:
            console.print(f"  [green][OK][/] {name}: {url}")
        else:
            console.print(f"  [red][FAIL][/] {name}: {url}")


@app.command(name="list")
def list_videos(
    count: int = typer.Option(10, "--count", "-n", help="Number of videos to list"),
) -> None:
    """List your uploaded videos."""
    if not is_configured():
        print_error("TubeCast not configured. Run 'tubecast setup' first.")
        raise typer.Exit(1)

    print_banner()
    print_step("Fetching your videos...")

    youtube = YouTubeService()
    youtube.authenticate()

    videos = youtube.list_videos(max_results=count)

    if not videos:
        print_info("No videos found")
        return

    print_videos_table(videos)


@app.command()
def playlists() -> None:
    """List your playlists."""
    if not is_configured():
        print_error("TubeCast not configured. Run 'tubecast setup' first.")
        raise typer.Exit(1)

    print_banner()
    print_step("Fetching your playlists...")

    youtube = YouTubeService()
    youtube.authenticate()

    playlist_list = youtube.list_playlists()

    if not playlist_list:
        print_info("No playlists found")
        return

    print_playlists_table(playlist_list)


@app.command()
def info(
    video_id: str = typer.Argument(..., help="Video ID to get info for"),
) -> None:
    """Get detailed info about a video."""
    if not is_configured():
        print_error("TubeCast not configured. Run 'tubecast setup' first.")
        raise typer.Exit(1)

    print_banner()

    youtube = YouTubeService()
    youtube.authenticate()

    try:
        video = youtube.get_video(video_id)
        print_video_card(video, get_video_url(video_id), get_studio_url(video_id))
    except Exception as e:
        print_error(f"Failed to get video info: {e}")


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context) -> None:
    """TubeCast - Professional YouTube uploader with AI."""
    if ctx.invoked_subcommand is None:
        # No command provided, run interactive mode
        if not is_configured():
            print_banner()
            console.print("Welcome to TubeCast! Let's set you up.\n")
            setup()
        else:
            _interactive_main()


def _interactive_main() -> None:
    """Main interactive menu."""
    print_banner()

    while True:
        action = questionary.select(
            "What would you like to do?",
            choices=[
                questionary.Choice("Upload a video", value="upload"),
                questionary.Choice("Upload folder (batch)", value="batch"),
                questionary.Choice("List my videos", value="list"),
                questionary.Choice("List my playlists", value="playlists"),
                questionary.Choice("Get video info", value="info"),
                questionary.Choice("Settings", value="settings"),
                questionary.Choice("Exit", value="exit"),
            ],
        ).ask()

        if action == "exit" or action is None:
            console.print("\n[dim]Goodbye![/]")
            break

        elif action == "upload":
            file_path = questionary.text(
                "Enter video file path:",
                validate=lambda p: Path(p).is_file() or "File not found",
            ).ask()

            if file_path and Path(file_path).exists():
                _upload_interactive(Path(file_path), load_config())

        elif action == "batch":
            folder_path = questionary.text(
                "Enter folder path with videos:",
                validate=lambda p: Path(p).is_dir() or "Folder not found",
            ).ask()

            if folder_path and Path(folder_path).exists():
                use_ai = questionary.confirm("Use AI for metadata?", default=False).ask()
                batch(Path(folder_path), ai=use_ai)

        elif action == "list":
            list_videos()

        elif action == "playlists":
            playlists()

        elif action == "info":
            video_id = questionary.text("Enter video ID:").ask()
            if video_id:
                info(video_id)

        elif action == "settings":
            setup()

        console.print()


if __name__ == "__main__":
    app()
