# LiorKodiBuilder v0.9

גרסה זו מוסיפה Wizard אמיתי יותר:

- תפריט ראשי בתוך Kodi
- התקנת Build מתוך `builds.json`
- הצגת מידע גרסאות
- ניקוי Cache / Packages
- אייקון תקין ל־Repository ול־Wizard

פקודה:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.2 --name "Lior Build"
```

אחרי ההרצה מעלים את כל התוכן של:

```text
output\UPLOAD_TO_KODIBUILD_ROOT
```

לתיקיית `KodiBuild`, ואז Commit + Push.
