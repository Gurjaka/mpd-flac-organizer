"""
Music file deduplication script for finding and removing duplicate files.
This script identifies duplicates based on song titles and provides options for handling them.
"""

import re
import hashlib
import subprocess
import os
import shutil
from pathlib import Path
from collections import defaultdict
from typing import Dict, List


def clear():
    os.system("cls" if os.name == "nt" else "clear")


def download_playlist(url) -> None:
    cmd = [
        "yt-dlp",
        "-x",
        "--audio-format",
        "flac",
        "--audio-quality",
        "0",
        "--embed-thumbnail",
        "--embed-metadata",
        "--add-metadata",
        "-o",
        "%(playlist_index)02d - %(title)s.%(ext)s",
        url,
    ]

    print(f"Downloading: {url}")
    subprocess.run(cmd)


def extract_song_title(filename: str) -> str:
    """Extract song title from filename, removing track numbers and extensions."""
    # Remove track numbers at the beginning (e.g., "01 - ", "166 - ")
    title = re.sub(r"^\d+\s*-\s*", "", filename)
    # Remove file extension
    title = re.sub(r"\.[^.]+$", "", title)
    # Remove quotes if present
    title = title.strip("'\"")
    return title.strip()


def get_file_hash(filepath: Path) -> str:
    """Calculate MD5 hash of file content."""
    hash_md5 = hashlib.md5()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()


def find_duplicates_by_title(directory: str) -> Dict[str, List[Path]]:
    """Find duplicate files based on song titles."""
    duplicates = defaultdict(list)

    music_dir = Path(directory)
    if not music_dir.exists():
        print(f"Directory {directory} does not exist!")
        return {}

    # Group files by extracted song title
    for file_path in music_dir.glob("*.flac"):
        title = extract_song_title(file_path.name)
        duplicates[title].append(file_path)

    # Filter to only keep actual duplicates (more than 1 file per title)
    return {title: files for title, files in duplicates.items() if len(files) > 1}


def find_duplicates_by_hash(directory: str) -> Dict[str, List[Path]]:
    """Find duplicate files based on file content hash."""
    duplicates = defaultdict(list)

    music_dir = Path(directory)
    if not music_dir.exists():
        print(f"Directory {directory} does not exist!")
        return {}

    print("Computing file hashes... This may take a while.")
    for file_path in music_dir.glob("*.flac"):
        file_hash = get_file_hash(file_path)
        duplicates[file_hash].append(file_path)

    return {hash_val: files for hash_val, files in duplicates.items() if len(files) > 1}


def choose_file_to_keep(files: List[Path]) -> Path:
    """Choose which file to keep based on various criteria."""
    # Sort by file size (descending) then by filename
    files_with_stats = [(f, f.stat().st_size) for f in files]
    files_with_stats.sort(key=lambda x: (-x[1], x[0].name))

    # Keep the largest file (assuming better quality)
    return files_with_stats[0][0]


def display_duplicates(duplicates: Dict[str, List[Path]], by_hash: bool = False):
    """Display found duplicates in a readable format."""
    if not duplicates:
        print("No duplicates found!")
        return

    print(f"\nFound {len(duplicates)} groups of duplicates:")
    print("=" * 60)

    for identifier, files in duplicates.items():
        if by_hash:
            print(f"\nDuplicate group (hash: {identifier[:8]}...):")
        else:
            print(f"\nDuplicate group: '{identifier}'")

        for i, file_path in enumerate(files, 1):
            size_mb = file_path.stat().st_size / (1024 * 1024)
            print(f"  {i}. {file_path.name} ({size_mb:.1f}MB)")


def remove_duplicates(duplicates: Dict[str, List[Path]], dry_run: bool = True):
    """Remove duplicate files, keeping the best one from each group."""
    removed_count = 0

    for identifier, files in duplicates.items():
        if len(files) <= 1:
            continue

        # Choose file to keep
        keep_file = choose_file_to_keep(files)
        files_to_remove = [f for f in files if f != keep_file]

        print(f"\nGroup: {identifier}")
        print(f"  Keeping: {keep_file.name}")

        for file_to_remove in files_to_remove:
            if dry_run:
                print(f"  Would remove: {file_to_remove.name}")
            else:
                try:
                    file_to_remove.unlink()
                    print(f"  Removed: {file_to_remove.name}")
                    removed_count += 1
                except Exception as e:
                    print(f"  Error removing {file_to_remove.name}: {e}")

    if dry_run:
        print(
            f"\nDry run completed. Would remove {sum(len(files) - 1 for files in duplicates.values())} files."
        )
    else:
        print(f"\nRemoved {removed_count} duplicate files.")


def move_to_dir(target_dir: Path) -> bool:
    assert target_dir

    # Check if any flac files exist
    flac_files = list(Path.cwd().glob("*.flac"))
    if not flac_files:
        print("No .flac files found in current directory.")
        return False

    # mv with shell to expand *.flac
    cmd = f"mv *.flac {str(target_dir)}"

    print(f"📦 Moving all .flac files to: {target_dir}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ Moved successfully.")
        return True
    else:
        print("❌ Move failed:", result.stderr)
        return False


def update_music() -> bool:
    if shutil.which("mpc") is None:
        print("⚠️  MPD (mpc) not found. Skipping update.")
        return False

    cmd = ["mpc", "update"]

    print("🎵 Updating MPD music database...")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode == 0:
        print("✅ MPD updated.")
        return True
    else:
        print("❌ MPD update failed:", result.stderr)
        return False


def main():
    """Main function with user interface."""

    url_list = []

    with open("list.txt", "r") as list_file:
        while True:
            url = list_file.readline()
            if not url:
                break
            url_list.append(url.strip())

    # assert url_list

    for playlist in url_list:
        download_playlist(playlist)

    clear()

    directory = "."

    print("\nChoose deduplication method:")
    print("1. By song title (faster, may have false positives)")
    print("2. By file content hash (slower, more accurate)")

    choice = input("Enter choice (1 or 2): ").strip()

    if choice == "1":
        duplicates = find_duplicates_by_title(directory)
        display_duplicates(duplicates, by_hash=False)
    elif choice == "2":
        duplicates = find_duplicates_by_hash(directory)
        display_duplicates(duplicates, by_hash=True)
    else:
        print("Invalid choice!")
        return

    if duplicates:
        print("\nWhat would you like to do?")
        print("1. Dry run (show what would be removed)")
        print("2. Actually remove duplicates")
        print("3. Exit without changes")

        action = input("Enter choice (1, 2, or 3): ").strip()

        if action == "1":
            remove_duplicates(duplicates, dry_run=True)
        elif action == "2":
            confirm = (
                input("Are you sure you want to remove files? (yes/no): ")
                .strip()
                .lower()
            )
            if confirm == "yes":
                remove_duplicates(duplicates, dry_run=False)
            else:
                print("Operation cancelled.")
        elif action == "3":
            print("Exiting without changes.")
        else:
            print("Invalid choice!")

        clear()

    try:
        target_dir = Path(
            input("📁 Directory path to move flac files to: ")
        ).expanduser()

        if target_dir.exists():
            if move_to_dir(target_dir):
                update_music()
        else:
            print("⚠️ Directory not found. Create it? (y/N)")
            answer = input("--> ").strip().lower()

            if answer == "y":
                target_dir.mkdir(parents=True, exist_ok=True)
                if move_to_dir(target_dir):
                    update_music()
            else:
                print("Aborting.")
    except Exception as e:
        print(f"🔥 Error: {e}")


if __name__ == "__main__":
    main()
