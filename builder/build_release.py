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

DEFAULT_BASE_URL = "https://lioryo.github.io/KodiBuild/"
DEFAULT_REPO_ID = "repository.lior"
DEFAULT_WIZARD_ID = "plugin.program.liorwizard"
DEFAULT_BUILD_ID = "liorbuild"

EXCLUDE_DIR_NAMES = {
    "cache", "temp", "tmp", "Thumbnails", "thumbnails", "packages", "Packages",
    "__pycache__", ".git", ".idea", ".vscode"
}
EXCLUDE_FILE_EXT = {".log", ".old", ".bak", ".tmp", ".pyc", ".pyo"}
EXCLUDE_FILE_NAMES = {"Textures13.db"}

SECRET_PATTERNS = [
    re.compile(r"real[-_ ]?debrid", re.I),
    re.compile(r"premiumize", re.I),
    re.compile(r"alldebrid", re.I),
    re.compile(r"trakt", re.I),
    re.compile(r"oauth", re.I),
    re.compile(r"token", re.I),
    re.compile(r"refresh", re.I),
    re.compile(r"access", re.I),
    re.compile(r"client_secret", re.I),
    re.compile(r"api[_-]?key", re.I),
]



ICON_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000a49444154789c6360000002000100"
    "05fe02fea5579a0000000049454e44ae426082"
)

def write_binary(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def md5_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def safe_rmtree(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path, ignore_errors=True)


def extract_if_zip(input_path: Path, work: Path) -> Path:
    if input_path.is_file() and input_path.suffix.lower() == ".zip":
        target = work / "extracted"
        target.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(input_path, "r") as zf:
            zf.extractall(target)
        candidates = [p for p in target.iterdir() if p.is_dir() and (p / "addons").exists() and (p / "userdata").exists()]
        if candidates:
            return candidates[0]
        if (target / "addons").exists() and (target / "userdata").exists():
            return target
        raise SystemExit("שגיאה: ה-ZIP לא נראה כמו גיבוי Kodi. חסרות תיקיות addons/userdata")
    return input_path


def validate_kodi_dir(kodi_dir: Path) -> None:
    if not kodi_dir.exists():
        raise SystemExit(f"שגיאה: הנתיב לא קיים: {kodi_dir}")
    if not (kodi_dir / "addons").exists():
        raise SystemExit("שגיאה: לא נמצאה תיקיית addons")
    if not (kodi_dir / "userdata").exists():
        raise SystemExit("שגיאה: לא נמצאה תיקיית userdata")


def should_exclude(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    if parts & EXCLUDE_DIR_NAMES:
        return True
    if path.is_file():
        if path.name in EXCLUDE_FILE_NAMES:
            return True
        if path.suffix in EXCLUDE_FILE_EXT:
            return True
    return False


def copy_clean_kodi(src: Path, dst: Path) -> tuple[int, int]:
    copied = 0
    skipped = 0
    for item in src.rglob("*"):
        if should_exclude(item, src):
            skipped += 1
            continue
        rel = item.relative_to(src)
        out = dst / rel
        if item.is_dir():
            out.mkdir(parents=True, exist_ok=True)
        else:
            out.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, out)
            copied += 1
    return copied, skipped


def scrub_text_file(path: Path) -> bool:
    try:
        data = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    original = data

    # XML settings style: <setting id="...">value</setting> / value="..."
    for pat in SECRET_PATTERNS:
        data = re.sub(rf'(<setting[^>]*(?:id|key|name)="[^"]*{pat.pattern}[^"]*"[^>]*>)(.*?)(</setting>)', r'\1\3', data, flags=re.I | re.S)
        data = re.sub(rf'((?:id|key|name)="[^"]*{pat.pattern}[^"]*"[^>]*value=")([^"]*)(")', r'\1\3', data, flags=re.I | re.S)
        data = re.sub(rf'("[^"]*{pat.pattern}[^"]*"\s*:\s*")[^"]*(")', r'\1\2', data, flags=re.I | re.S)

    # Generic known fields
    data = re.sub(r'("(?:token|refresh_token|access_token|client_secret|api_key)"\s*:\s*")[^"]*(")', r'\1\2', data, flags=re.I)

    if data != original:
        path.write_text(data, encoding="utf-8", newline="\n")
        return True
    return False


def scrub_personal_data(root: Path) -> int:
    changed = 0
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in {".xml", ".json", ".ini", ".cfg", ".txt"}:
            if scrub_text_file(path):
                changed += 1
    return changed


def zip_folder(folder: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(folder).as_posix())


def addon_xml_repo(base_url: str, repo_id: str, version: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{repo_id}" name="Lior Repository" version="{version}" provider-name="Lior">
  <requires>
    <import addon="xbmc.addon" version="12.0.0"/>
  </requires>
  <extension point="xbmc.addon.repository" name="Lior Repository">
    <dir minversion="21.0.0" maxversion="21.9.9">
      <info compressed="false">{base_url}addons.xml</info>
      <checksum>{base_url}addons.xml.md5</checksum>
      <datadir zip="true">{base_url}repo/</datadir>
    </dir>
  </extension>
  <extension point="xbmc.addon.metadata">
    <summary lang="he_IL">מאגר פרטי של Lior Build</summary>
    <description lang="he_IL">מאגר להתקנת Lior Wizard ו-Lior Build.</description>
    <platform>all</platform>
  </extension>
</addon>
'''


def addon_xml_wizard(wizard_id: str, version: str) -> str:
    return f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<addon id="{wizard_id}" name="Lior Build Wizard" version="{version}" provider-name="Lior">
  <requires>
    <import addon="xbmc.python" version="3.0.0"/>
  </requires>
  <extension point="xbmc.python.script" library="default.py"/>
  <extension point="xbmc.addon.metadata">
    <summary lang="he_IL">אשף התקנת Lior Build</summary>
    <description lang="he_IL">מוריד ומתקין את Lior Build ממאגר GitHub.</description>
    <platform>all</platform>
  </extension>
</addon>
'''


def wizard_default_py(base_url: str) -> str:
    return f'''# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import urllib.request
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcplugin
import xbmcvfs

BASE_URL = "{base_url.rstrip('/')}/"
BUILDS_JSON = BASE_URL + "builds.json"
ADDON = xbmcaddon.Addon()
HANDLE = int(sys.argv[1]) if len(sys.argv) > 1 else -1


def t(path):
    return xbmcvfs.translatePath(path)


def notify(message):
    xbmcgui.Dialog().notification("Lior Wizard", message, xbmcgui.NOTIFICATION_INFO, 4000)


def fetch_builds():
    req = urllib.request.Request(BUILDS_JSON, headers={{"User-Agent": "LiorKodiWizard/1.0"}})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def download(url, dest):
    req = urllib.request.Request(url, headers={{"User-Agent": "LiorKodiWizard/1.0"}})
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as f:
        total = r.headers.get("Content-Length")
        total = int(total) if total else 0
        done = 0
        dp = xbmcgui.DialogProgress()
        dp.create("Lior Build", "מוריד Build...")
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            if total:
                dp.update(int(done * 100 / total), "מוריד... %d%%" % int(done * 100 / total))
            if dp.iscanceled():
                dp.close()
                raise Exception("ההורדה בוטלה")
        dp.close()


def extract_zip(zip_path, target_home):
    dp = xbmcgui.DialogProgress()
    dp.create("Lior Build", "מתקין Build...")
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        total = max(1, len(members))
        for i, m in enumerate(members):
            if m.is_dir():
                continue
            name = m.filename.replace("\\", "/")
            if name.startswith("/") or ".." in name.split("/"):
                continue
            target = os.path.join(target_home, *name.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with zf.open(m) as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            if i % 25 == 0:
                dp.update(int(i * 100 / total), "מתקין... %d%%" % int(i * 100 / total))
            if dp.iscanceled():
                dp.close()
                raise Exception("ההתקנה בוטלה")
    dp.close()


def install_build():
    dlg = xbmcgui.Dialog()
    try:
        data = fetch_builds()
        builds = data.get("builds", [])
        if not builds:
            dlg.ok("Lior Wizard", "לא נמצאו Builds בקובץ builds.json")
            return
        labels = []
        for b in builds:
            labels.append("%s  |  גרסה %s  |  Kodi %s" % (b.get("name", "Build"), b.get("version", ""), b.get("kodi", "")))
        idx = dlg.select("בחר Build להתקנה", labels)
        if idx < 0:
            return
        b = builds[idx]
        msg = "להתקין את:\n%s\n\nמומלץ לגבות לפני התקנה. כל משתמש יגדיר Real-Debrid בעצמו." % labels[idx]
        if not dlg.yesno("Lior Wizard", msg):
            return
        packages = t("special://home/addons/packages")
        os.makedirs(packages, exist_ok=True)
        dest = os.path.join(packages, os.path.basename(b["url"]))
        download(b["url"], dest)
        extract_zip(dest, t("special://home"))
        xbmc.executebuiltin("UpdateLocalAddons")
        xbmc.executebuiltin("UpdateAddonRepos")
        dlg.ok("Lior Wizard", "ה-Build הותקן. סגור ופתח את Kodi מחדש.")
    except Exception as e:
        dlg.ok("Lior Wizard - שגיאה", str(e))


def clear_cache():
    paths = [
        "special://home/cache",
        "special://temp",
        "special://home/addons/packages",
    ]
    removed = 0
    for p in paths:
        real = t(p)
        if os.path.exists(real):
            for name in os.listdir(real):
                fp = os.path.join(real, name)
                try:
                    if os.path.isdir(fp):
                        shutil.rmtree(fp, ignore_errors=True)
                    else:
                        os.remove(fp)
                    removed += 1
                except Exception:
                    pass
    xbmcgui.Dialog().ok("Lior Wizard", "ניקוי הסתיים. נמחקו %d פריטים." % removed)


def show_info():
    try:
        data = fetch_builds()
        builds = data.get("builds", [])
        lines = ["Kodi: " + xbmc.getInfoLabel("System.BuildVersion"), "כתובת: " + BASE_URL]
        for b in builds:
            lines.append("%s - %s" % (b.get("name", "Build"), b.get("version", "")))
        xbmcgui.Dialog().ok("Lior Wizard", "\n".join(lines))
    except Exception as e:
        xbmcgui.Dialog().ok("Lior Wizard - שגיאה", str(e))


def main():
    while True:
        choice = xbmcgui.Dialog().select("Lior Wizard", [
            "התקנת Lior Build",
            "מידע על גרסאות",
            "ניקוי Cache / Packages",
            "יציאה",
        ])
        if choice == 0:
            install_build()
        elif choice == 1:
            show_info()
        elif choice == 2:
            clear_cache()
        else:
            break


if __name__ == "__main__":
    main()
'''

def make_addon_zip(folder: Path, zip_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        base = folder.parent
        for path in folder.rglob("*"):
            if path.is_file():
                zf.write(path, path.relative_to(base).as_posix())


def create_addons_xml(addon_dirs: list[Path]) -> str:
    parts = ['<?xml version="1.0" encoding="UTF-8" standalone="yes"?>', '<addons>']
    for d in addon_dirs:
        xml_path = d / "addon.xml"
        if xml_path.exists():
            txt = xml_path.read_text(encoding="utf-8", errors="ignore")
            txt = re.sub(r'^\s*<\?xml[^>]*\?>', '', txt).strip()
            parts.append(txt)
    parts.append('</addons>')
    return "\n".join(parts) + "\n"


def create_project(kodi_input: Path, out_root: Path, version: str, build_name: str, base_url: str, dry_run: bool=False) -> None:
    base_url = base_url.rstrip('/') + '/'
    safe_rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        kodi_dir = extract_if_zip(kodi_input, work)
        validate_kodi_dir(kodi_dir)

        clean = work / "clean_build"
        clean.mkdir()
        copied, skipped = copy_clean_kodi(kodi_dir, clean)
        scrubbed = scrub_personal_data(clean)

        upload = out_root / "UPLOAD_TO_KODIBUILD_ROOT"
        builds_dir = upload / "builds"
        repo_dir = upload / "repo"
        builds_dir.mkdir(parents=True)
        repo_dir.mkdir(parents=True)

        build_zip_name = f"LiorBuild-{version}.zip"
        build_zip = builds_dir / build_zip_name
        if not dry_run:
            zip_folder(clean, build_zip)

        repo_addon_dir = work / DEFAULT_REPO_ID
        repo_addon_dir.mkdir()
        write_text(repo_addon_dir / "addon.xml", addon_xml_repo(base_url, DEFAULT_REPO_ID, version))
        write_binary(repo_addon_dir / "icon.png", ICON_PNG)
        repo_zip_name = f"{DEFAULT_REPO_ID}-{version}.zip"
        if not dry_run:
            make_addon_zip(repo_addon_dir, repo_dir / repo_zip_name)
            # Root copies make installation easier from Kodi File Manager.
            shutil.copy2(repo_dir / repo_zip_name, upload / f"{DEFAULT_REPO_ID}.zip")
            shutil.copy2(repo_dir / repo_zip_name, upload / repo_zip_name)

        wiz_dir = work / DEFAULT_WIZARD_ID
        wiz_dir.mkdir()
        write_text(wiz_dir / "addon.xml", addon_xml_wizard(DEFAULT_WIZARD_ID, version))
        write_text(wiz_dir / "default.py", wizard_default_py(base_url))
        write_binary(wiz_dir / "icon.png", ICON_PNG)
        wiz_zip_name = f"{DEFAULT_WIZARD_ID}-{version}.zip"
        if not dry_run:
            make_addon_zip(wiz_dir, repo_dir / wiz_zip_name)

        builds_json = {
            "name": "Lior Kodi Builds",
            "builds": [{
                "id": DEFAULT_BUILD_ID,
                "name": build_name,
                "version": version,
                "kodi": "21.x",
                "platform": "all",
                "url": base_url + "builds/" + build_zip_name,
                "md5": md5_file(build_zip) if build_zip.exists() else "",
                "notes": "גרסת חברים ללא פרטי Real-Debrid אישיים"
            }]
        }
        write_text(upload / "builds.json", json.dumps(builds_json, ensure_ascii=False, indent=2))

        addons_xml = create_addons_xml([repo_addon_dir, wiz_dir])
        write_text(upload / "addons.xml", addons_xml)
        write_text(upload / "addons.xml.md5", hashlib.md5(addons_xml.encode("utf-8")).hexdigest())

        # GitHub Pages does not provide directory listing. Kodi's HTTP browser parses
        # links from index.html, so we create explicit links to every installable ZIP.
        root_index = f'''<!doctype html>
<html lang="he" dir="rtl">
<meta charset="utf-8">
<title>Lior Kodi Build</title>
<h1>Lior Kodi Build</h1>
<p>כתובת מקור לקודי: <code>{base_url}</code></p>
<h2>התקנה</h2>
<ul>
  <li><a href="{DEFAULT_REPO_ID}.zip">repository.lior.zip</a></li>
  <li><a href="repo/{repo_zip_name}">{repo_zip_name}</a></li>
  <li><a href="repo/{wiz_zip_name}">{wiz_zip_name}</a></li>
</ul>
<h2>קבצי עדכון</h2>
<ul>
  <li><a href="addons.xml">addons.xml</a></li>
  <li><a href="addons.xml.md5">addons.xml.md5</a></li>
  <li><a href="builds.json">builds.json</a></li>
  <li><a href="builds/{build_zip_name}">{build_zip_name}</a></li>
</ul>
</html>'''
        write_text(upload / "index.html", root_index)

        repo_index = f'''<!doctype html>
<html lang="he" dir="rtl">
<meta charset="utf-8">
<title>Lior Kodi Repo</title>
<h1>Lior Kodi Repo</h1>
<ul>
  <li><a href="{repo_zip_name}">{repo_zip_name}</a></li>
  <li><a href="{wiz_zip_name}">{wiz_zip_name}</a></li>
</ul>
</html>'''
        write_text(repo_dir / "index.html", repo_index)

        inv = f'''# דוח יצירת Build

שם Build: {build_name}
גרסה: {version}
כתובת בסיס: {base_url}

קבצים שהועתקו: {copied}
קבצים/תיקיות שדולגו: {skipped}
קבצי הגדרות שנוקו ממידע אישי: {scrubbed}

נוצרו:
- {build_zip.relative_to(upload) if build_zip.exists() else 'build skipped'}
- repo/{repo_zip_name}
- repo/{wiz_zip_name}
- {DEFAULT_REPO_ID}.zip
- addons.xml
- addons.xml.md5
- builds.json
- index.html
'''
        write_text(upload / "INVENTORY_HEBREW.md", inv)

        print("OK - נוצרה חבילת הפצה אמיתית")
        print(f"יש להעלות ל-GitHub את התוכן של: {upload}")
        print(f"קבצים שהועתקו: {copied}, דולגו: {skipped}, נוקו: {scrubbed}")


def main():
    p = argparse.ArgumentParser(description="Create Lior Kodi Build release")
    p.add_argument("kodi_path", help="נתיב לתיקיית Kodi או לקובץ Kodi.zip")
    p.add_argument("--version", default="1.0.0")
    p.add_argument("--name", default="Lior Build")
    p.add_argument("--base-url", default=DEFAULT_BASE_URL)
    p.add_argument("--output", default="output")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    create_project(Path(args.kodi_path), Path(args.output), args.version, args.name, args.base_url, args.dry_run)

if __name__ == "__main__":
    main()
