# LiorKodiBuilder v1.0

תיקון Wizard תקני לקודי:
- ה-Wizard מוגדר כ-Program Add-on עם `xbmc.python.script`
- נוצר `plugin.program.liorwizard-<version>.zip`
- נוצר `repository.lior-<version>.zip`
- נוצר `addons.xml` ו-`addons.xml.md5`

פקודה מומלצת:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.3 --name "Lior Build"
```

לאחר מכן להעלות את תוכן:

```text
output\UPLOAD_TO_KODIBUILD_ROOT
```

למאגר `KodiBuild`.
