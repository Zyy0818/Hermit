from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "scripts" / "wiki_manifest.json"
WIKI_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")
MARKDOWN_LINK_PATTERN = re.compile(r"(!?)\[([^\]]+)\]\(([^)]+)\)")


class SyncError(RuntimeError):
    """Raised when wiki sync inputs are invalid."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync selected repo docs to a GitHub wiki checkout."
    )
    parser.add_argument(
        "--wiki-dir", required=True, help="Path to the checked-out wiki repository."
    )
    parser.add_argument(
        "--repo-url",
        required=True,
        help="Repository URL used to build canonical source links and blob links.",
    )
    parser.add_argument(
        "--default-branch",
        default="main",
        help="Default branch used when building canonical source links.",
    )
    parser.add_argument(
        "--manifest",
        default=str(DEFAULT_MANIFEST),
        help="Manifest JSON file mapping wiki page names to repo source files.",
    )
    return parser.parse_args()


def canonical_repo_url(repo_url: str) -> str:
    return repo_url.rstrip("/").removesuffix(".git")


def load_manifest(manifest_path: Path) -> dict[str, str]:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SyncError(f"Manifest file does not exist: {manifest_path}") from exc
    except json.JSONDecodeError as exc:
        raise SyncError(f"Manifest file is not valid JSON: {manifest_path}") from exc

    if not isinstance(manifest, dict) or not manifest:
        raise SyncError(
            "Manifest must be a non-empty JSON object mapping wiki titles to source files."
        )

    for title, source in manifest.items():
        if not isinstance(title, str) or not isinstance(source, str):
            raise SyncError("Manifest keys and values must be strings.")
        validate_wiki_title(title)

    return manifest


def validate_wiki_title(title: str) -> None:
    if not title or not WIKI_FILENAME_PATTERN.fullmatch(title):
        raise SyncError(
            f"Invalid wiki page title '{title}'. Use only letters, numbers, dots, hyphens, and underscores."
        )


def build_blob_url(repo_url: str, branch: str, relative_path: str, anchor: str = "") -> str:
    path = relative_path.lstrip("/")
    url = f"{canonical_repo_url(repo_url)}/blob/{branch}/{path}"
    return f"{url}{anchor}"


def inject_canonical_notice(content: str, source_path: str, repo_url: str, branch: str) -> str:
    source_url = build_blob_url(repo_url, branch, source_path)
    notice = (
        f"> Canonical source: [{source_path}]({source_url})\n"
        "> \n"
        "> Edit the repository docs first; this wiki page is a generated reading mirror.\n"
    )
    if content.startswith("# "):
        lines = content.splitlines()
        title = lines[0]
        rest = "\n".join(lines[1:]).lstrip("\n")
        if rest:
            return f"{title}\n\n{notice}\n{rest}\n"
        return f"{title}\n\n{notice}\n"
    return f"{notice}\n{content.rstrip()}\n"


def split_target(target: str) -> tuple[str, str]:
    if "#" in target:
        path_part, anchor = target.split("#", 1)
        return path_part, f"#{anchor}"
    return target, ""


def is_external_target(target: str) -> bool:
    lowered = target.lower()
    return lowered.startswith(("http://", "https://", "mailto:", "tel:"))


def relative_repo_path(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_wiki_target(title: str, anchor: str) -> str:
    return f"{title}{anchor}"


def rewrite_target(
    raw_target: str,
    source_path: Path,
    mirrored_sources: dict[str, str],
    repo_url: str,
    branch: str,
) -> str:
    target = raw_target.strip()
    if not target or target.startswith("#") or is_external_target(target):
        return raw_target

    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return raw_target

    target_path_str, anchor = split_target(parsed.path)
    if not target_path_str:
        return raw_target

    resolved_path = (source_path.parent / target_path_str).resolve()
    try:
        repo_relative = relative_repo_path(resolved_path)
    except ValueError:
        return raw_target

    mirrored_title = mirrored_sources.get(repo_relative)
    if mirrored_title is not None:
        rewritten_path = normalize_wiki_target(mirrored_title, anchor)
    else:
        rewritten_path = build_blob_url(repo_url, branch, repo_relative, anchor)

    rewritten = urlunsplit(("", "", rewritten_path, parsed.query, parsed.fragment))
    return rewritten


def rewrite_links(
    content: str,
    source_path: Path,
    mirrored_sources: dict[str, str],
    repo_url: str,
    branch: str,
) -> str:
    def replace(match: re.Match[str]) -> str:
        bang, text, target = match.groups()
        rewritten_target = rewrite_target(target, source_path, mirrored_sources, repo_url, branch)
        return f"{bang}[{text}]({rewritten_target})"

    return MARKDOWN_LINK_PATTERN.sub(replace, content)


def build_sidebar(manifest: dict[str, str]) -> str:
    lines = ["## Hermit Wiki", ""]
    lines.extend(f"- [{title}]({title})" for title in manifest)
    return "\n".join(lines) + "\n"


def sync_docs_to_wiki(
    *,
    manifest_path: Path,
    wiki_dir: Path,
    repo_url: str,
    default_branch: str,
) -> None:
    manifest = load_manifest(manifest_path)
    mirrored_sources = {source: title for title, source in manifest.items()}

    if not wiki_dir.exists():
        raise SyncError(f"Wiki directory does not exist: {wiki_dir}")
    if not wiki_dir.is_dir():
        raise SyncError(f"Wiki path is not a directory: {wiki_dir}")

    for title, source in manifest.items():
        source_path = ROOT / source
        if not source_path.exists():
            raise SyncError(f"Missing source file for wiki page '{title}': {source}")

        content = source_path.read_text(encoding="utf-8")
        content = rewrite_links(content, source_path, mirrored_sources, repo_url, default_branch)
        content = inject_canonical_notice(content, source, repo_url, default_branch)
        output_path = wiki_dir / f"{title}.md"
        output_path.write_text(content, encoding="utf-8")

    sidebar_path = wiki_dir / "_Sidebar.md"
    sidebar_path.write_text(build_sidebar(manifest), encoding="utf-8")


def main() -> int:
    args = parse_args()
    try:
        sync_docs_to_wiki(
            manifest_path=Path(args.manifest).resolve(),
            wiki_dir=Path(args.wiki_dir).resolve(),
            repo_url=args.repo_url,
            default_branch=args.default_branch,
        )
    except SyncError as exc:
        raise SystemExit(str(exc)) from exc
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
