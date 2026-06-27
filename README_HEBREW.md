# LiorKodiBuilder v0.6

גרסה זו מייצרת חבילת הפצה אמיתית יותר ל-KodiBuild:

- Build ZIP מתוך גיבוי Kodi
- repository.lior.zip להתקנה ידנית מתוך Kodi
- plugin.program.liorwizard בתוך repo/
- addons.xml + addons.xml.md5
- builds.json
- index.html

פקודה לדוגמה:

```cmd
python builder\build_release.py "C:\Users\daniel\Downloads\Kodi.zip" --version 1.0.0 --name "Lior Build"
```

את התוכן של `output\UPLOAD_TO_KODIBUILD_ROOT` מעלים לשורש המאגר KodiBuild.
