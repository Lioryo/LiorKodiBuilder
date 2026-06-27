from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

DEFAULT_BASE_URL = "https://lioryo.github.io/KodiBuild/"
DEFAULT_NAME = "Lior Build"
DEFAULT_VERSION = "1.0"

SKIP_DIR_NAMES = {
    "cache", "temp", "tmp", "thumbnails", "packages", "archive_cache",
    "__pycache__", ".git", ".github"
}
SKIP_FILE_SUFFIXES = {".log", ".old", ".bak", ".tmp", ".pyc", ".pyo"}
SENSITIVE_PATTERNS = [
    "realdebrid", "real-debrid", "real_debrid", "rd.auth", "rd_token",
    "premiumize", "alldebrid", "trakt", "youtube", "oauth", "access_token",
    "refresh_token", "client_secret", "password", "passwd", "cookie"
]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def md5_text(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def is_zip(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() == ".zip"


def find_kodi_root(path: Path) -> Path:
    candidates = [path]
    candidates.extend([p for p in path.rglob("*") if p.is_dir() and p.name.lower() in {"kodi", ".kodi"}][:20])
    for c in candidates:
        if (c / "addons").is_dir() and (c / "userdata").is_dir():
            return c
    raise SystemExit("לא נמצאה תיקיית Kodi תקינה. צריך תיקייה שיש בה addons וגם userdata.")


def extract_if_needed(input_path: Path, work: Path) -> Path:
    if is_zip(input_path):
        dest = work / "extracted"
        dest.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(dest)
        return find_kodi_root(dest)
    return find_kodi_root(input_path)


def should_skip(path: Path) -> bool:
    parts = {p.lower() for p in path.parts}
    if parts & SKIP_DIR_NAMES:
        return True
    if path.is_file() and path.suffix.lower() in SKIP_FILE_SUFFIXES:
        return True
    return False


def sanitize_text(data: str) -> str:
    # מחיקה שמרנית של ערכי טוקנים/סיסמאות נפוצים בקבצי XML/JSON/TXT
    data = re.sub(r"(?i)(access_token|refresh_token|token|password|passwd|client_secret|cookie)(['\"\s:=/>-]+)[^'\"<>,}\s]+", r"\1\2", data)
    data = re.sub(r"(?i)<(access_token|refresh_token|token|password|passwd|client_secret|cookie)>.*?</\1>", r"<\1></\1>", data)
    return data


def copy_clean(src: Path, dst: Path) -> dict:
    stats = {"copied": 0, "skipped": 0, "sanitized": 0}
    for item in src.rglob("*"):
        rel = item.relative_to(src)
        target = dst / rel
        if should_skip(item):
            stats["skipped"] += 1
            continue
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        name = item.name.lower()
        rels = str(rel).lower()
        sensitive = any(p in name or p in rels for p in SENSITIVE_PATTERNS)
        if sensitive and item.suffix.lower() in {".xml", ".json", ".txt", ".ini", ".cfg"}:
            try:
                text = item.read_text(encoding="utf-8", errors="ignore")
                target.write_text(sanitize_text(text), encoding="utf-8")
                stats["sanitized"] += 1
            except Exception:
                stats["skipped"] += 1
                continue
        else:
            shutil.copy2(item, target)
        stats["copied"] += 1
    return stats


def zip_dir(src: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in src.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(src).as_posix())


def read_addon_xml(addon_dir: Path) -> str | None:
    p = addon_dir / "addon.xml"
    if p.is_file():
        return p.read_text(encoding="utf-8", errors="ignore")
    return None


def create_wizard(site: Path, base_url: str, build_name: str) -> Path:
    addon_id = "plugin.program.liorwizard"
    d = site / "repo" / addon_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "addon.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{addon_id}" name="Lior Wizard" version="1.0.0" provider-name="Lior">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.python.pluginsource" library="default.py">
    <provides>executable</provides>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="he_IL">אשף התקנת {build_name}</summary>
    <description lang="he_IL">מוריד ומתקין Build מקובץ ZIP.</description>
    <platform>all</platform>
  </extension>
</addon>
''', encoding="utf-8")
    (d / "default.py").write_text(f'''# -*- coding: utf-8 -*-
import os, shutil, zipfile, urllib.request
import xbmc, xbmcgui, xbmcvfs

BUILD_URL = "{base_url.rstrip('/')}/builds/LiorBuild-1.0.zip"
BUILD_NAME = "{build_name}"


def download(url, dest):
    urllib.request.urlretrieve(url, dest)


def main():
    if not xbmcgui.Dialog().yesno("Lior Wizard", "להתקין את " + BUILD_NAME + "?", "הפעולה תחליף את הגדרות Kodi הקיימות."):
        return
    profile = xbmcvfs.translatePath("special://home")
    tmp = xbmcvfs.translatePath("special://temp/LiorBuild.zip")
    xbmcgui.Dialog().notification("Lior Wizard", "מוריד Build...", xbmcgui.NOTIFICATION_INFO, 3000)
    try:
        download(BUILD_URL, tmp)
        xbmcgui.Dialog().notification("Lior Wizard", "מחלץ Build...", xbmcgui.NOTIFICATION_INFO, 3000)
        with zipfile.ZipFile(tmp, 'r') as z:
            z.extractall(profile)
        xbmcgui.Dialog().ok("Lior Wizard", "ההתקנה הסתיימה. סגור ופתח את Kodi מחדש.")
    except Exception as e:
        xbmcgui.Dialog().ok("שגיאה", str(e))

if __name__ == "__main__":
    main()
''', encoding="utf-8")
    zip_path = site / "repo" / f"{addon_id}-1.0.0.zip"
    zip_dir(d, zip_path)
    return d


def create_repository(site: Path, base_url: str) -> Path:
    addon_id = "repository.lior"
    d = site / "repo" / addon_id
    d.mkdir(parents=True, exist_ok=True)
    (d / "addon.xml").write_text(f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{addon_id}" name="Lior Repository" version="1.0.0" provider-name="Lior">
  <extension point="xbmc.addon.repository" name="Lior Repository">
    <info compressed="false">{base_url.rstrip('/')}/addons.xml</info>
    <checksum>{base_url.rstrip('/')}/addons.xml.md5</checksum>
    <datadir zip="true">{base_url.rstrip('/')}/repo/</datadir>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="he_IL">מאגר Kodi של ליאור</summary>
    <description lang="he_IL">Repository להתקנת Lior Wizard.</description>
    <platform>all</platform>
  </extension>
</addon>
''', encoding="utf-8")
    zip_path = site / "repo" / f"{addon_id}-1.0.0.zip"
    zip_dir(d, zip_path)
    return d


def create_addons_xml(site: Path) -> None:
    addons = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for addon_xml in sorted((site / "repo").glob("*/addon.xml")):
        content = addon_xml.read_text(encoding="utf-8", errors="ignore").strip()
        content = re.sub(r"^<\?xml[^>]*>\s*", "", content)
        addons.append(content)
    addons.append('</addons>')
    text = "\n".join(addons) + "\n"
    (site / "addons.xml").write_text(text, encoding="utf-8")
    (site / "addons.xml.md5").write_text(md5_text(text), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser(description="Lior Kodi Builder - create Kodi build package")
    ap.add_argument("kodi_path", help="נתיב לתיקיית Kodi או לקובץ Kodi.zip")
    ap.add_argument("--version", default=DEFAULT_VERSION)
    ap.add_argument("--name", default=DEFAULT_NAME)
    ap.add_argument("--base-url", default=DEFAULT_BASE_URL)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    input_path = Path(args.kodi_path).expanduser().resolve()
    if not input_path.exists():
        raise SystemExit(f"הנתיב לא קיים: {input_path}")

    out = Path("output").resolve()
    if out.exists():
        shutil.rmtree(out)
    site = out / "UPLOAD_TO_KODIBUILD_ROOT"
    builds = site / "builds"
    repo = site / "repo"
    builds.mkdir(parents=True, exist_ok=True)
    repo.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        kodi_root = extract_if_needed(input_path, work)
        clean_root = work / "clean_kodi"
        clean_root.mkdir()
        stats = copy_clean(kodi_root, clean_root)

        build_zip = builds / f"LiorBuild-{args.version}.zip"
        if not args.dry_run:
            zip_dir(clean_root, build_zip)
        size = build_zip.stat().st_size if build_zip.exists() else 0

    builds_json = {
        "name": args.name,
        "version": args.version,
        "kodi": "21.x",
        "url": f"{args.base_url.rstrip('/')}/builds/LiorBuild-{args.version}.zip",
        "sha256": sha256_file(build_zip) if build_zip.exists() else "dry-run",
        "size_bytes": size,
        "created": datetime.now().isoformat(timespec="seconds"),
        "notes": "Friends build. Personal accounts/tokens sanitized where detected."
    }
    (site / "builds.json").write_text(json.dumps(builds_json, ensure_ascii=False, indent=2), encoding="utf-8")
    (site / "index.html").write_text(f"""<!doctype html><html><head><meta charset='utf-8'><title>Lior Kodi Build</title></head>
<body><h1>Lior Kodi Build</h1><p>Repository ZIP: <a href='repo/repository.lior-1.0.0.zip'>repository.lior-1.0.0.zip</a></p></body></html>""", encoding="utf-8")

    create_wizard(site, args.base_url, args.name)
    create_repository(site, args.base_url)
    create_addons_xml(site)

    report = {
        "input": str(input_path),
        "kodi_root_detected": True,
        "copied_files": stats["copied"],
        "skipped_items": stats["skipped"],
        "sanitized_files": stats["sanitized"],
        "output_folder": str(site),
        "build_zip": str(build_zip),
    }
    (out / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK - נוצרה חבילת הפצה")
    print("העלה ל-GitHub את התוכן של:")
    print(site)
    print(f"קבצים הועתקו: {stats['copied']}, דולגו: {stats['skipped']}, נוקו: {stats['sanitized']}")

if __name__ == "__main__":
    main()
