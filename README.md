Это пример навыка, работающего на tgalice. 

Установка:
```
pip install requirements.txt
```

Поговорить с ним можно в командной строке (но возможности будут ограничены, т.к. часть NLU разбирается на стороне Яндекса):
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

Если вы хотите воспроизвести навык полностью, вам нужно взять содержимое папки `grammar`, 
и для файлов с расширением `.grammar` создать одноименные интенты в Яндексе, 
а содержимое файла `entities.vocab` переложить в пользовательские сущности. 
Как это делать, читайте в [документации Алисы](https://yandex.ru/dev/dialogs/alice/doc/nlu.html/).
