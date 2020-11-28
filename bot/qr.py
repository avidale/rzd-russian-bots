from flask import Blueprint, request, render_template_string

qr_blueprint = Blueprint('qr_bp', __name__, url_prefix='/qr')


@qr_blueprint.route('/')
def redirect_any():
    f = request.args.get('f')
    t = request.args.get('t')
    tx = ''
    if f and t:
        tx = f' от станции {f} до станции {t}'
    s = f"<div>" \
        f"<h1>Ура, вы успешно приобрели билет{tx}!</h1> " \
        f"<br>Точнее, здесь может оказаться настоящий билет, когда РЖД проведут с нами интеграцию." \
        f"<br>Если вы хотите поговорить об этом светлом будущем, напишите мне: " \
        f"<a href=""https://t.me/cointegrated"">@cointegrated</a>." \
        "<br>О том, кто я, можно почитать <a href=""http://daviddale.ru/"">тут</a>." \
        f"</div>"
    return render_template_string(s)
