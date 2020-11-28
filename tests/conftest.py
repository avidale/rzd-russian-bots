import unittest.mock
import pytest

from bot.dialog_manager import RzdDialogManager


@pytest.fixture()
def mock_dm():
    mock_api_helper = unittest.mock.Mock()
    mock_api_helper.get_world.return_value = {
        'stations': [],
        'regions': [],
        'settlements': [],
    }
    return RzdDialogManager(rasp_api=mock_api_helper)
