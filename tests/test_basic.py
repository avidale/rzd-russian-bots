from bot.dialog_manager import RzdDialogManager
from tgalice.testing.testing_utils import make_context


def test_hello_world():
    dm = RzdDialogManager()
    ctx = make_context(new_session=True)
    resp = dm.respond(ctx)
    assert 'РЖД' in resp.text
