from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from datetime import datetime
from typing import Any


OUTPUT_DIR = Path("output")


def read_text_safe(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def find_kodi_root(path: Path) -> Path:
    """Return the folder that contains addons and userdata.

    Some backups contain an extra parent folder. This function tries to locate
    the real Kodi data root without being too clever.
    """
    path = path.resolve()
    if (path / "addons").is_dir() and (path / "userdata").is_dir():
        return path

    candidates = []
    for root, dirs, _files in os.walk(path):
        root_path = Path(root)
        if "addons" in dirs and "userdata" in dirs:
            candidates.append(root_path)
            if len(candidates) >= 5:
                break

    if not candidates:
        raise FileNotFoundError(
            "לא נמצאה תיקיית Kodi תקינה. צריך תיקייה שמכילה addons ו-userdata."
        )

    return candidates[0]


def list_addons(addons_dir: Path) -> list[dict[str, Any]]:
    addons: list[dict[str, Any]] = []
    for addon_dir in sorted([p for p in addons_dir.iterdir() if p.is_dir()]):
        addon_xml = addon_dir / "addon.xml"
        addon_id = addon_dir.name
        name = addon_dir.name
        version = ""
        provider = ""
        if addon_xml.exists():
            text = read_text_safe(addon_xml)
            id_match = re.search(r'<addon[^>]+id="([^"]+)"', text)
            name_match = re.search(r'<addon[^>]+name="([^"]+)"', text)
            version_match = re.search(r'<addon[^>]+version="([^"]+)"', text)
            provider_match = re.search(r'<addon[^>]+provider-name="([^"]+)"', text)
            addon_id = id_match.group(1) if id_match else addon_id
            name = name_match.group(1) if name_match else name
            version = version_match.group(1) if version_match else ""
            provider = provider_match.group(1) if provider_match else ""

        addons.append(
            {
                "id": addon_id,
                "folder": addon_dir.name,
                "name": name,
                "version": version,
                "provider": provider,
                "is_repository": addon_id.startswith("repository."),
                "is_skin": addon_id.startswith("skin."),
                "is_program": addon_id.startswith("plugin.program."),
                "is_video": addon_id.startswith("plugin.video."),
            }
        )
    return addons


def detect_selected_skin(userdata_dir: Path) -> str | None:
    guisettings = userdata_dir / "guisettings.xml"
    if not guisettings.exists():
        return None
    text = read_text_safe(guisettings)
    # Kodi often stores skin as: <setting id="lookandfeel.skin">skin.estuary</setting>
    patterns = [
        r'<setting[^>]+id="lookandfeel\.skin"[^>]*>([^<]+)</setting>',
        r'<lookandfeel\.skin>([^<]+)</lookandfeel\.skin>',
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def scan_userdata_sensitive_files(userdata_dir: Path) -> list[str]:
    keywords = [
        "realdebrid", "real-debrid", "debrid", "trakt", "youtube", "oauth",
        "token", "refresh", "account", "password", "api_key", "apikey",
    ]
    hits: list[str] = []
    for path in userdata_dir.rglob("*"):
        if not path.is_file():
            continue
        lower = str(path).lower()
        if any(k in lower for k in keywords):
            hits.append(str(path.relative_to(userdata_dir)))
    return sorted(hits)[:500]


def analyze(kodi_path: Path) -> dict[str, Any]:
    kodi_root = find_kodi_root(kodi_path)
    addons_dir = kodi_root / "addons"
    userdata_dir = kodi_root / "userdata"

    addons = list_addons(addons_dir)
    repositories = [a for a in addons if a["is_repository"]]
    skins = [a for a in addons if a["is_skin"]]
    videos = [a for a in addons if a["is_video"]]
    programs = [a for a in addons if a["is_program"]]

    report = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "kodi_root": str(kodi_root),
        "valid": True,
        "counts": {
            "addons_total": len(addons),
            "repositories": len(repositories),
            "skins": len(skins),
            "video_plugins": len(videos),
            "program_plugins": len(programs),
        },
        "selected_skin": detect_selected_skin(userdata_dir),
        "repositories": repositories,
        "skins": skins,
        "video_plugins": videos,
        "program_plugins": programs,
        "sensitive_file_candidates": scan_userdata_sensitive_files(userdata_dir),
    }
    return report


def write_reports(report: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    json_path = OUTPUT_DIR / "analysis_report.json"
    md_path = OUTPUT_DIR / "analysis_report_HEBREW.md"

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    lines = []
    lines.append("# דוח ניתוח Kodi\n")
    lines.append(f"נוצר בתאריך: `{report['created_at']}`\n")
    lines.append(f"תיקיית Kodi: `{report['kodi_root']}`\n")
    lines.append("## ספירה\n")
    for key, value in report["counts"].items():
        lines.append(f"- {key}: {value}")
    lines.append("")
    lines.append(f"סקין פעיל שזוהה: `{report.get('selected_skin') or 'לא זוהה'}`\n")

    lines.append("## Repositories\n")
    for addon in report["repositories"]:
        lines.append(f"- `{addon['id']}` — {addon['name']} {addon['version']}")
    lines.append("")

    lines.append("## תוספי וידאו\n")
    for addon in report["video_plugins"]:
        lines.append(f"- `{addon['id']}` — {addon['name']} {addon['version']}")
    lines.append("")

    lines.append("## קבצים חשודים ככוללים חשבונות/טוקנים\n")
    if report["sensitive_file_candidates"]:
        for item in report["sensitive_file_candidates"]:
            lines.append(f"- `{item}`")
    else:
        lines.append("לא נמצאו מועמדים ברורים.")

    md_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"נוצר דוח: {json_path}")
    print(f"נוצר דוח: {md_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Analyze a Kodi folder or extracted backup.")
    parser.add_argument("kodi_path", help="Path to Kodi folder or extracted backup folder")
    args = parser.parse_args()

    try:
        report = analyze(Path(args.kodi_path))
        write_reports(report)
        print("הבדיקה הסתיימה בהצלחה.")
        return 0
    except Exception as exc:
        print(f"שגיאה: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
