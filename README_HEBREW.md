# LiorKodiBuilder v0.7

גרסה זו מתקנת את בעיית GitHub Pages/Kodi: GitHub לא מציג רשימת תיקיות אוטומטית, לכן הכלי יוצר `index.html` בשורש וגם בתוך `repo/` עם קישורים מפורשים לקבצי ה-ZIP.

פקודה לדוגמה:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.1 --name "Lior Build"
```

אחרי ההרצה מעלים את כל התוכן של:

```text
output\UPLOAD_TO_KODIBUILD_ROOT
```

לשורש המאגר `KodiBuild`.

בקודי מוסיפים מקור:

```text
https://lioryo.github.io/KodiBuild/
```

ואז: Add-ons → Install from zip file → המקור → `repository.lior.zip`.
