#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Lior Kodi Builder
יוצר חבילת הפצה ל-Kodi Build מתוך גיבוי Kodi.zip או תיקיית Kodi.
מותאם ל-Kodi 21.x, Windows/Android.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

BASE_URL_DEFAULT = "https://lioryo.github.io/KodiBuild/"
BUILD_NAME_DEFAULT = "Lior Build"
BUILD_ID_DEFAULT = "liorbuild"
VERSION_DEFAULT = "1.0"

# קבצים ותיקיות שלא כדאי להפיץ בתוך Build לחברים
EXCLUDE_DIR_PARTS = {
    "cache", "temp", "tmp", "thumbnails", "packages", "logs",
    "__pycache__", ".git", ".github"
}
EXCLUDE_FILE_NAMES = {
    "kodi.log", "kodi.old.log", "crashlog.txt", "Textures13.db",
}
EXCLUDE_EXT = {".log", ".tmp", ".bak", ".pyc", ".pyo"}

# מילות מפתח לניקוי הגדרות אישיות בלבד. לא מוחקים תוסף, רק נתוני משתמש.
PRIVATE_SETTING_KEYWORDS = [
    "realdebrid", "real-debrid", "rd.auth", "rd_api", "rdtoken", "rd_token",
    "alldebrid", "premiumize", "trakt", "youtube", "oauth", "token",
    "refresh_token", "access_token", "client_secret", "password", "passwd",
    "username", "email", "api_key", "apikey", "authorization"
]

TEXT_EXT = {".xml", ".json", ".txt", ".ini", ".cfg", ".properties"}


def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def zip_dir(src_dir: Path, zip_path: Path) -> None:
    if zip_path.exists():
        zip_path.unlink()
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for p in src_dir.rglob("*"):
            if p.is_file():
                z.write(p, p.relative_to(src_dir).as_posix())


def extract_or_copy(input_path: Path, work_dir: Path) -> Path:
    """מחזיר תיקיית Kodi עבודה."""
    target = work_dir / "kodi_src"
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(input_path, "r") as z:
            z.extractall(target)
        # אם הזיפ מכיל תיקיית Kodi אחת, נשתמש בה
        kids = [p for p in target.iterdir() if p.is_dir()]
        if len(kids) == 1 and (kids[0] / "addons").exists():
            return kids[0]
        return target
    if input_path.is_dir():
        shutil.copytree(input_path, target)
        if (target / "Kodi").exists() and (target / "Kodi" / "addons").exists():
            return target / "Kodi"
        return target
    raise ValueError("הקלט חייב להיות קובץ ZIP או תיקיית Kodi")


def should_exclude(path: Path, root: Path) -> bool:
    rel_parts = [x.lower() for x in path.relative_to(root).parts]
    if any(part in EXCLUDE_DIR_PARTS for part in rel_parts):
        return True
    if path.name in EXCLUDE_FILE_NAMES:
        return True
    if path.suffix.lower() in EXCLUDE_EXT:
        return True
    # בסיסי נתונים כבדים שנבנים מחדש
    rel = "/".join(rel_parts)
    if "userdata/database/textures" in rel:
        return True
    return False


def clean_private_text(text: str) -> tuple[str, bool]:
    changed = False
    # XML: <setting id="...">value</setting>
    def repl_xml(m):
        nonlocal changed
        sid = (m.group(1) or "").lower()
        val = m.group(2)
        if any(k in sid for k in PRIVATE_SETTING_KEYWORDS) or any(k in val.lower() for k in ["token", "realdebrid", "trakt"]):
            changed = True
            return f'<setting id="{m.group(1)}"></setting>'
        return m.group(0)
    text = re.sub(r'<setting\s+id="([^"]+)"[^>]*>(.*?)</setting>', repl_xml, text, flags=re.I|re.S)

    # JSON או טקסט: "token":"..."
    keys = "|".join(re.escape(k) for k in PRIVATE_SETTING_KEYWORDS)
    pattern = re.compile(rf'("(?:{keys})"\s*:\s*)"[^"]*"', re.I)
    new = pattern.sub(lambda m: m.group(1) + '""', text)
    if new != text:
        changed = True
        text = new
    return text, changed


def copy_clean_kodi(src: Path, dst: Path) -> dict:
    report = {"copied_files": 0, "skipped_files": 0, "sanitized_files": []}
    for p in src.rglob("*"):
        if p.is_dir():
            continue
        if should_exclude(p, src):
            report["skipped_files"] += 1
            continue
        rel = p.relative_to(src)
        out = dst / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        if p.suffix.lower() in TEXT_EXT and "userdata" in [x.lower() for x in rel.parts]:
            try:
                txt = p.read_text(encoding="utf-8", errors="ignore")
                txt2, changed = clean_private_text(txt)
                out.write_text(txt2, encoding="utf-8")
                if changed:
                    report["sanitized_files"].append(rel.as_posix())
            except Exception:
                shutil.copy2(p, out)
        else:
            shutil.copy2(p, out)
        report["copied_files"] += 1
    return report


def addon_xml(id_: str, name: str, version: str, provider: str, extension_xml: str, summary: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{id_}" name="{name}" version="{version}" provider-name="{provider}">
{extension_xml}
    <extension point="xbmc.addon.metadata">
        <summary lang="he_IL">{summary}</summary>
        <summary lang="en_GB">{summary}</summary>
        <platform>all</platform>
    </extension>
</addon>
'''


def create_repository_addon(repo_dir: Path, base_url: str) -> None:
    repo_dir.mkdir(parents=True, exist_ok=True)
    xml = addon_xml(
        "repository.lior", "Lior Repository", "1.0.0", "Lior",
        f'''    <extension point="xbmc.addon.repository" name="Lior Repository">
        <info compressed="false">{base_url}addons.xml</info>
        <checksum>{base_url}addons.xml.md5</checksum>
        <datadir zip="true">{base_url}repo/</datadir>
    </extension>''',
        "מאגר פרטי להתקנת Lior Wizard"
    )
    (repo_dir / "addon.xml").write_text(xml, encoding="utf-8")


def create_wizard_addon(wiz_dir: Path, base_url: str) -> None:
    wiz_dir.mkdir(parents=True, exist_ok=True)
    xml = addon_xml(
        "plugin.program.liorwizard", "Lior Wizard", "1.0.0", "Lior",
        '''    <requires>
        <import addon="xbmc.python" version="3.0.0"/>
    </requires>
    <extension point="xbmc.python.pluginsource" library="default.py">
        <provides>executable</provides>
    </extension>''',
        "אשף התקנת Build של Lior"
    )
    (wiz_dir / "addon.xml").write_text(xml, encoding="utf-8")
    default_py = f'''# -*- coding: utf-8 -*-
import json, os, shutil, zipfile, urllib.request
import xbmc, xbmcaddon, xbmcgui, xbmcvfs

BASE_URL = "{base_url}"
BUILDS_JSON = BASE_URL + "builds.json"
ADDON = xbmcaddon.Addon()


def msg(title, text):
    xbmcgui.Dialog().ok(title, text)


def download(url, dest):
    dp = xbmcgui.DialogProgress()
    dp.create("Lior Wizard", "מוריד Build...")
    with urllib.request.urlopen(url) as r, open(dest, "wb") as f:
        total = int(r.headers.get("content-length", 0) or 0)
        done = 0
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                dp.update(int(done * 100 / total))
            if dp.iscanceled():
                raise Exception("בוטל")
    dp.close()


def kodi_home():
    return xbmcvfs.translatePath("special://home/")


def install_build():
    try:
        data = json.loads(urllib.request.urlopen(BUILDS_JSON).read().decode("utf-8"))
        build = data["builds"][0]
        if not xbmcgui.Dialog().yesno("Lior Wizard", "להתקין את " + build["name"] + "?", "הפעולה תחליף את הגדרות Kodi הנוכחיות."):
            return
        home = kodi_home()
        tmp = os.path.join(xbmcvfs.translatePath("special://temp/"), "lior_build.zip")
        download(build["url"], tmp)
        dp = xbmcgui.DialogProgress(); dp.create("Lior Wizard", "מתקין Build...")
        with zipfile.ZipFile(tmp, "r") as z:
            members = z.infolist()
            for i, m in enumerate(members):
                if m.is_dir():
                    continue
                target = os.path.join(home, m.filename)
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with z.open(m) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
                if i % 20 == 0:
                    dp.update(int(i * 100 / max(1, len(members))))
        dp.close()
        msg("Lior Wizard", "ההתקנה הסתיימה. סגור ופתח מחדש את Kodi.")
    except Exception as e:
        msg("שגיאה", str(e))


def clean_cache():
    paths = ["special://home/cache", "special://temp", "special://home/userdata/Thumbnails"]
    for p in paths:
        path = xbmcvfs.translatePath(p)
        if os.path.exists(path):
            shutil.rmtree(path, ignore_errors=True)
    msg("Lior Wizard", "ניקוי הסתיים")


def main():
    choice = xbmcgui.Dialog().select("Lior Wizard", ["התקנת Lior Build", "ניקוי Cache"])
    if choice == 0:
        install_build()
    elif choice == 1:
        clean_cache()

if __name__ == "__main__":
    main()
'''
    (wiz_dir / "default.py").write_text(default_py, encoding="utf-8")


def generate_addons_xml(addon_dirs: list[Path], out_xml: Path) -> None:
    content = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for d in addon_dirs:
        ax = d / "addon.xml"
        txt = ax.read_text(encoding="utf-8", errors="ignore")
        txt = re.sub(r'^\s*<\?xml[^>]*\?>\s*', '', txt).strip()
        content.append(txt)
    content.append('</addons>\n')
    out_xml.write_text("\n".join(content), encoding="utf-8")
    (out_xml.parent / "addons.xml.md5").write_text(md5_file(out_xml), encoding="utf-8")


def inventory(kodi_dir: Path) -> list[dict]:
    items = []
    addons = kodi_dir / "addons"
    if not addons.exists():
        return items
    for d in sorted([x for x in addons.iterdir() if x.is_dir()]):
        ax = d / "addon.xml"
        if not ax.exists():
            continue
        try:
            root = ET.parse(ax).getroot()
            items.append({"id": root.attrib.get("id", d.name), "name": root.attrib.get("name", ""), "version": root.attrib.get("version", "")})
        except Exception:
            items.append({"id": d.name, "name": "", "version": ""})
    return items


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="Kodi.zip או תיקיית Kodi")
    ap.add_argument("--output", default="dist", help="תיקיית פלט")
    ap.add_argument("--base-url", default=BASE_URL_DEFAULT)
    ap.add_argument("--version", default=VERSION_DEFAULT)
    ap.add_argument("--build-name", default=BUILD_NAME_DEFAULT)
    args = ap.parse_args()

    base_url = args.base_url.rstrip("/") + "/"
    out = Path(args.output).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        kodi_src = extract_or_copy(Path(args.input).resolve(), td)
        clean = td / "clean_build"
        report = copy_clean_kodi(kodi_src, clean)

        build_zip = out / "builds" / f"LiorBuild-{args.version}.zip"
        zip_dir(clean, build_zip)

        repo_addon = td / "repository.lior"
        wiz_addon = td / "plugin.program.liorwizard"
        create_repository_addon(repo_addon, base_url)
        create_wizard_addon(wiz_addon, base_url)

        repo_zip_dir = out / "repo"
        zip_dir(repo_addon, repo_zip_dir / "repository.lior.zip")
        zip_dir(wiz_addon, repo_zip_dir / "plugin.program.liorwizard.zip")

        generate_addons_xml([repo_addon, wiz_addon], out / "addons.xml")

        builds = {
            "name": "Lior Kodi Builds",
            "builds": [{
                "id": BUILD_ID_DEFAULT,
                "name": args.build_name,
                "version": args.version,
                "kodi": "21.x Omega",
                "url": base_url + f"builds/LiorBuild-{args.version}.zip",
                "size": build_zip.stat().st_size,
                "md5": md5_file(build_zip),
                "notes": "גרסת חברים ללא חשבון Real-Debrid אישי"
            }]
        }
        (out / "builds.json").write_text(json.dumps(builds, ensure_ascii=False, indent=2), encoding="utf-8")
        (out / "index.html").write_text("<html><body><h1>Lior KodiBuild</h1><ul><li><a href='repo/repository.lior.zip'>repository.lior.zip</a></li></ul></body></html>", encoding="utf-8")

        inv = inventory(kodi_src)
        report_path = out / "INVENTORY_HEBREW.md"
        with report_path.open("w", encoding="utf-8") as f:
            f.write("# דוח Build\n\n")
            f.write(f"קבצים שהועתקו: {report['copied_files']}\n\n")
            f.write(f"קבצים שנוקו/דולגו: {report['skipped_files']}\n\n")
            f.write("## קבצים שבהם נוקו הגדרות פרטיות\n")
            for s in report["sanitized_files"][:200]:
                f.write(f"- {s}\n")
            f.write("\n## תוספים שזוהו\n")
            for a in inv:
                f.write(f"- {a['id']} | {a['name']} | {a['version']}\n")

    print(f"נוצר פלט ב: {out}")
    print("את תוכן התיקייה הזו מעלים לשורש המאגר KodiBuild")

if __name__ == "__main__":
    main()
