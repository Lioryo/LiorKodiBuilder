# Lior Kodi Builder

כלי לבניית Build פרטי של Kodi מתוך התקנה קיימת.

## גרסה 0.2

בגרסה זו נוסף מנוע בדיקה ראשוני:

- בדיקת תיקיית Kodi
- זיהוי תיקיות addons ו-userdata
- ספירת תוספים
- זיהוי repositories
- זיהוי skin מותקן אם ניתן
- יצירת דוח JSON

## הרצה

ב-Windows:

```bat
python builder\build_release.py "C:\Users\USERNAME\AppData\Roaming\Kodi"
```

אם בודקים ZIP שחולץ מגיבוי, יש להריץ על התיקייה שבתוכה נמצאות `addons` ו-`userdata`.

## הערה

גרסה זו עדיין לא יוצרת Build להתקנה. היא רק בודקת ומדווחת.
