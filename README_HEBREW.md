# Lior Kodi Builder

כלי לבניית חבילת הפצה ל-Kodi מתוך תיקיית Kodi קיימת או גיבוי שחולץ.

## גרסה 0.3

בגרסה הזו הכלי כבר עושה בפועל:

- מזהה תיקיית Kodi תקינה (`addons` + `userdata`).
- מנקה קבצים מיותרים: Cache, Logs, Packages, Thumbnails, Temp.
- מסיר קבצי מידע אישי נפוצים של Real-Debrid / Trakt / YouTube OAuth מתוך `userdata/addon_data`.
- יוצר Build ZIP נקי.
- יוצר מבנה Upload מוכן ל-GitHub Pages:
  - `builds/LiorBuild-1.0.zip`
  - `builds.json`
  - `index.html`
  - דוח `report.json`

## שימוש מהיר ב-Windows

1. התקן Python אם אין לך.
2. חלץ את גיבוי Kodi לתיקייה.
3. הרץ:

```bat
python builder\build_release.py "C:\path\to\Kodi" --version 1.0 --base-url https://lioryo.github.io/KodiBuild/
```

אם אתה רוצה רק לבדוק בלי ליצור ZIP:

```bat
python builder\build_release.py "C:\path\to\Kodi" --dry-run
```

## התוצאה

התוצאה נוצרת בתיקייה:

```text
output\UPLOAD_TO_KODIBUILD
```

את התוכן של התיקייה הזו מעלים למאגר `KodiBuild` בשורש.

## חשוב

לפני הפצה לחברים מומלץ לבדוק את ה-Build על התקנת Kodi חדשה.
