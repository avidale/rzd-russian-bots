import logging
import tgalice

from bot.dialog_manager import RzdDialogManager

from dotenv import load_dotenv

from bot.qr import qr_blueprint

load_dotenv()

logging.basicConfig(level=logging.DEBUG)

mongo_db = tgalice.storage.database_utils.get_mongo_or_mock()

connector = tgalice.dialog_connector.DialogConnector(
    dialog_manager=RzdDialogManager(),
    storage=tgalice.session_storage.MongoBasedStorage(database=mongo_db, collection_name='sessions'),
    log_storage=tgalice.storage.message_logging.MongoMessageLogger(
        database=mongo_db, collection_name='message_logs', detect_pings=True
    )
)

server = tgalice.flask_server.FlaskServer(connector=connector)
app = server.app  # can be used with gunicorn
app.register_blueprint(qr_blueprint)

if __name__ == '__main__':
    server.parse_args_and_run()
