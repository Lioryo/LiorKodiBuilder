# LiorKodiBuilder v1.1

תיקון Repository ל-Kodi 21.x.

מה תוקן:
- Repository addon.xml משתמש עכשיו בסכימת `<dir minversion="21.0.0">` החדשה.
- Wizard מוגדר כ-Program Add-on תקני: `xbmc.python.script`.

פקודת הרצה מומלצת:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.4 --name "Lior Build"
```

לאחר מכן מעתיקים את תוכן:

```text
output\UPLOAD_TO_KODIBUILD_ROOT
```

לתיקיית המאגר `KodiBuild`, ואז Commit + Push.

חשוב: בקודי מומלץ להסיר את `Lior Repository` הישן ולהתקין מחדש את `repository.lior-1.0.4.zip`.
