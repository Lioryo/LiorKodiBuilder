# LiorKodiBuilder v1.4

תיקון: שגיאת תחביר ב-Wizard (`default.py`).

מה תוקן:
- תיקון `replace("\\\\", "/")` בקוד החילוץ.
- תיקון שורות טקסט עם `\n` שגרמו ל-SyntaxError.
- בוצעה בדיקת תחביר מקומית ל-`default.py` שנוצר מתוך ה-ZIP.

הרצה מומלצת:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.7 --name "Lior Build"
```

לאחר מכן להעלות את תוכן:

```text
output\UPLOAD_TO_KODIBUILD_ROOT
```

למאגר `KodiBuild`.
