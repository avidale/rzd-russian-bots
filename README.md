Это пример навыка, работающего на tgalice. 

Установка:
```
pip install requirements.txt
```

Поговорить с ним можно в командной строке:
```
python main.py --cli
```

Ещё его можно запустить как flask приложение, например

```
python main.py
```
или даже
```
gunicorn main:app --threads=10 --workers=1
```

Ещё его можно запустить с ngrok'ом, чтобы сразу прокинуть урл в тестовый навык Алисы
```
python main.py --ngrok
```
