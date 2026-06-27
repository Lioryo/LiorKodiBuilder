from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

OUTPUT_DIR = Path("output")
DEFAULT_BUILD_NAME = "LiorBuild"
DEFAULT_BASE_URL = "https://lioryo.github.io/KodiBuild/"

EXCLUDE_DIR_NAMES = {
    "cache", "temp", "tmp", "packages", "thumbnails", "screenshots",
    "cdm", "logs", "log", "crashlogs", "__pycache__",
}
EXCLUDE_FILE_SUFFIXES = {
    ".log", ".old", ".tmp", ".pyc", ".pyo", ".bak",
}
EXCLUDE_FILE_NAMES = {
    "kodi.log", "kodi.old.log", "spmc.log", "xbmc.log", "textures13.db",
}
SENSITIVE_ADDON_PATTERNS = [
    "realdebrid", "real-debrid", "real_debrid", "debrid", "premiumize", "alldebrid",
    "trakt", "youtube", "accounts", "account", "oauth", "auth", "token",
]
SENSITIVE_KEY_PATTERNS = [
    "token", "refresh", "oauth", "auth", "apikey", "api_key", "secret", "password",
    "realdebrid", "real_debrid", "trakt", "premiumize", "alldebrid", "username",
]


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def find_kodi_root(path: Path) -> Path:
    path = path.resolve()
    if (path / "addons").is_dir() and (path / "userdata").is_dir():
        return path
    for root, dirs, _files in os.walk(path):
        root_path = Path(root)
        if "addons" in dirs and "userdata" in dirs:
            return root_path
    raise SystemExit("לא נמצאה תיקיית Kodi תקינה. צריך תיקייה שמכילה addons וגם userdata.")


def analyze(kodi_root: Path) -> dict[str, Any]:
    addons_dir = kodi_root / "addons"
    userdata_dir = kodi_root / "userdata"
    addons = sorted([p.name for p in addons_dir.iterdir() if p.is_dir()]) if addons_dir.exists() else []
    repos = [a for a in addons if a.startswith("repository.")]
    plugins = [a for a in addons if a.startswith("plugin.")]
    skins = [a for a in addons if a.startswith("skin.")]
    gui_settings = read_text_safe(userdata_dir / "guisettings.xml")
    current_skin = None
    m = re.search(r'<setting[^>]+id="lookandfeel\.skin"[^>]*>(.*?)</setting>', gui_settings)
    if m:
        current_skin = m.group(1).strip()
    total_files = sum(len(files) for _root, _dirs, files in os.walk(kodi_root))
    return {
        "kodi_root": str(kodi_root),
        "total_files": total_files,
        "addons_count": len(addons),
        "repositories": repos,
        "plugins": plugins,
        "skins": skins,
        "current_skin": current_skin,
    }


def should_exclude(path: Path, kodi_root: Path) -> bool:
    parts = {part.lower() for part in path.relative_to(kodi_root).parts}
    name = path.name.lower()
    if any(part in EXCLUDE_DIR_NAMES for part in parts):
        return True
    if name in EXCLUDE_FILE_NAMES:
        return True
    if any(name.endswith(suf) for suf in EXCLUDE_FILE_SUFFIXES):
        return True
    return False


def copy_clean(kodi_root: Path, work_root: Path) -> dict[str, int]:
    stats = {"copied": 0, "excluded": 0}
    for root, dirs, files in os.walk(kodi_root):
        root_path = Path(root)
        # prune excluded dirs
        keep_dirs = []
        for d in dirs:
            candidate = root_path / d
            if should_exclude(candidate, kodi_root):
                stats["excluded"] += 1
            else:
                keep_dirs.append(d)
        dirs[:] = keep_dirs
        for f in files:
            src = root_path / f
            if should_exclude(src, kodi_root):
                stats["excluded"] += 1
                continue
            rel = src.relative_to(kodi_root)
            dst = work_root / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(src, dst)
                stats["copied"] += 1
            except Exception:
                stats["excluded"] += 1
    return stats


def scrub_text_file(path: Path) -> bool:
    text = read_text_safe(path)
    if not text:
        return False
    original = text
    # simple XML/JSON/value redaction; conservative but practical
    for key in SENSITIVE_KEY_PATTERNS:
        text = re.sub(rf'(<setting[^>]+id="[^"]*{re.escape(key)}[^"]*"[^>]*>)(.*?)(</setting>)', rf'\1\3', text, flags=re.I | re.S)
        text = re.sub(rf'("[^"]*{re.escape(key)}[^"]*"\s*:\s*")[^"]*(")', rf'\1\2', text, flags=re.I)
        text = re.sub(rf'({re.escape(key)}\s*=\s*)[^\n\r&<]+', rf'\1', text, flags=re.I)
    if text != original:
        path.write_text(text, encoding="utf-8", errors="ignore")
        return True
    return False


def scrub_personal_data(work_root: Path) -> dict[str, int]:
    stats = {"removed_files": 0, "scrubbed_files": 0, "removed_dirs": 0}
    addon_data = work_root / "userdata" / "addon_data"
    if addon_data.exists():
        for p in list(addon_data.iterdir()):
            name = p.name.lower()
            if any(pattern in name for pattern in SENSITIVE_ADDON_PATTERNS):
                # Do not delete the entire addon_data folder for common video addons; instead scrub inside it.
                for root, dirs, files in os.walk(p):
                    for f in files:
                        fp = Path(root) / f
                        if fp.suffix.lower() in {".xml", ".json", ".txt", ".db"}:
                            # db files may contain tokens; remove small account DBs by filename
                            if fp.suffix.lower() == ".db" or any(x in fp.name.lower() for x in SENSITIVE_ADDON_PATTERNS):
                                try:
                                    fp.unlink()
                                    stats["removed_files"] += 1
                                except Exception:
                                    pass
                            elif scrub_text_file(fp):
                                stats["scrubbed_files"] += 1
            else:
                for root, _dirs, files in os.walk(p):
                    for f in files:
                        fp = Path(root) / f
                        if fp.suffix.lower() in {".xml", ".json", ".txt"} and scrub_text_file(fp):
                            stats["scrubbed_files"] += 1
    return stats


def make_zip(src_dir: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for root, _dirs, files in os.walk(src_dir):
            for f in files:
                src = Path(root) / f
                arc = src.relative_to(src_dir).as_posix()
                zf.write(src, arc)


def create_upload_package(build_zip: Path, upload_dir: Path, base_url: str, build_name: str, version: str, report: dict[str, Any]) -> None:
    if upload_dir.exists():
        shutil.rmtree(upload_dir)
    (upload_dir / "builds").mkdir(parents=True, exist_ok=True)
    dst_build = upload_dir / "builds" / build_zip.name
    shutil.copy2(build_zip, dst_build)
    size = dst_build.stat().st_size
    checksum = md5_file(dst_build)
    base_url = base_url.rstrip("/") + "/"
    builds = {
        "name": "Lior Kodi Builds",
        "version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "builds": [
            {
                "name": build_name,
                "version": version,
                "kodi": "21.x",
                "url": f"{base_url}builds/{build_zip.name}",
                "size_bytes": size,
                "md5": checksum,
                "notes": "Friends version: personal Real-Debrid/Trakt/YouTube tokens removed where detected."
            }
        ]
    }
    write_json(upload_dir / "builds.json", builds)
    write_json(upload_dir / "report.json", report)
    (upload_dir / "index.html").write_text(f"""<!doctype html><html lang='he' dir='rtl'><meta charset='utf-8'>
<title>Lior Kodi Build</title><body><h1>Lior Kodi Build</h1>
<p>גרסה: {version}</p><p><a href='builds.json'>builds.json</a></p>
<p><a href='builds/{build_zip.name}'>הורדת Build</a></p>
</body></html>""", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a clean Kodi build package")
    parser.add_argument("kodi_path", help="Path to Kodi folder containing addons and userdata")
    parser.add_argument("--version", default="1.0", help="Build version")
    parser.add_argument("--name", default=DEFAULT_BUILD_NAME, help="Build name")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="GitHub Pages base URL")
    parser.add_argument("--dry-run", action="store_true", help="Analyze only")
    args = parser.parse_args()

    kodi_root = find_kodi_root(Path(args.kodi_path))
    report: dict[str, Any] = {"generated_at": datetime.now().isoformat(timespec="seconds")}
    report["analysis_before"] = analyze(kodi_root)

    OUTPUT_DIR.mkdir(exist_ok=True)
    write_json(OUTPUT_DIR / "analysis.json", report)

    if args.dry_run:
        print("בדיקה הסתיימה. נוצר output/analysis.json")
        print(json.dumps(report["analysis_before"], ensure_ascii=False, indent=2))
        return

    with tempfile.TemporaryDirectory(prefix="lior_kodi_build_") as td:
        work_root = Path(td) / "kodi_clean"
        copy_stats = copy_clean(kodi_root, work_root)
        scrub_stats = scrub_personal_data(work_root)
        report["copy_stats"] = copy_stats
        report["scrub_stats"] = scrub_stats
        report["analysis_after"] = analyze(work_root)

        safe_name = re.sub(r"[^A-Za-z0-9_.-]+", "_", args.name).strip("_") or DEFAULT_BUILD_NAME
        build_zip = OUTPUT_DIR / f"{safe_name}-{args.version}.zip"
        if build_zip.exists():
            build_zip.unlink()
        make_zip(work_root, build_zip)
        report["build_zip"] = str(build_zip)
        report["build_zip_size_bytes"] = build_zip.stat().st_size
        report["build_zip_md5"] = md5_file(build_zip)

    upload_dir = OUTPUT_DIR / "UPLOAD_TO_KODIBUILD"
    create_upload_package(build_zip, upload_dir, args.base_url, args.name, args.version, report)
    write_json(OUTPUT_DIR / "report.json", report)
    print("נוצר Build בהצלחה:", build_zip)
    print("תיקיית העלאה:", upload_dir)
    print("העלה ל-KodiBuild את התוכן של output/UPLOAD_TO_KODIBUILD")


if __name__ == "__main__":
    main()
