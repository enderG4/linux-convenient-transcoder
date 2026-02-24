"""
core.scanner
~~~~~~~~~~~~
Pure functions for diffing an input folder against an output folder.
No Qt, no subprocess — easy to unit-test in isolation.
"""

from __future__ import annotations

from pathlib import Path

# Video extensions we consider as valid input files
VIDEO_EXTENSIONS: frozenset[str] = frozenset({
    ".mp4", ".mov", ".mxf", ".avi", ".mkv",
    ".m4v", ".wmv", ".flv", ".webm", ".ts",
    ".mpg", ".mpeg", ".m2t", ".m2ts", ".dv",
    ".r3d", ".braw",  # RED and Blackmagic raw
})


# ── Public API ────────────────────────────────────────────────────────────────

def find_pending_files(
    input_folder: Path,
    output_folder: Path,
    output_extension: str,
) -> list[Path]:
    """
    Return input files that do NOT yet have a corresponding output file.

    Matching is done by stem (filename without extension) so that:
        input/clip001.mov  →  output/clip001.mp4   is considered DONE
        input/clip002.mov  →  (missing)             is considered PENDING

    Args:
        input_folder:     folder to scan for source video files
        output_folder:    folder to check for already-processed files
        output_extension: the extension the output files will have (e.g. ".mp4")

    Returns:
        Sorted list of absolute input Paths that need processing.
    """
    if not input_folder.is_dir():
        return []

    input_files  = _collect_video_files(input_folder)
    output_stems = _collect_stems(output_folder, output_extension)

    pending = [f for f in input_files if f.stem not in output_stems]
    return sorted(pending)


def build_output_path(
    input_file: Path,
    output_folder: Path,
    output_extension: str,
) -> Path:
    """
    Given an input file, return the expected output path.

    Example:
        input_file     = Path("/rushes/clip001.mov")
        output_folder  = Path("/proxies")
        output_extension = ".mp4"
        → Path("/proxies/clip001.mp4")
    """
    return output_folder / (input_file.stem + output_extension)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _collect_video_files(folder: Path) -> list[Path]:
    """Return all video files directly inside *folder* (non-recursive)."""
    return [
        f for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS
    ]


def _collect_stems(folder: Path, extension: str) -> frozenset[str]:
    """
    Return the stems of all files with *extension* inside *folder*.
    Returns an empty frozenset if the folder doesn't exist yet.
    """
    if not folder.is_dir():
        return frozenset()

    return frozenset(
        f.stem for f in folder.iterdir()
        if f.is_file() and f.suffix.lower() == extension.lower()
    )