# LiorKodiBuilder

כלי ליצירת Build פרטי ל-Kodi מתוך גיבוי Kodi.zip.

## המטרה

- ליצור Build שמתאים ל-Kodi 21.x.
- לעבוד גם ב-Windows וגם באנדרואיד.
- להסיר נתונים אישיים כמו Real-Debrid, Trakt ו-YouTube לפני הפצה לחברים.
- ליצור אוטומטית Repository ו-Wizard.
- להכין תיקייה שמעלים ל-GitHub Pages במאגר `KodiBuild`.

## שימוש בסיסי ב-Windows

1. התקן Python 3.11 או חדש יותר.
2. פתח PowerShell בתוך תיקיית הפרויקט.
3. הרץ:

```powershell
python builder\build_release.py --input "C:\path\to\Kodi.zip" --output "C:\Projects\KodiBuild_upload" --version 1.0
```

4. את **התוכן** של תיקיית הפלט מעלים לשורש המאגר `KodiBuild`.

## איך מתקינים בקודי

אחרי העלאה ל-GitHub Pages:

1. Kodi → File Manager → Add Source
2. כתובת:

```text
https://lioryo.github.io/KodiBuild/
```

3. Install from ZIP
4. התקן:

```text
repo/repository.lior.zip
```

5. Install from repository → Lior Repository → Program add-ons → Lior Wizard
6. הפעל את Lior Wizard ובחר התקנה.

## חשוב

לפני הפצה לחברים חובה לבדוק על Kodi נקי.
הכלי מנקה נתונים אישיים לפי מילות מפתח, אבל תמיד כדאי לבדוק ידנית שאין בתוך ה-Build פרטים אישיים.
