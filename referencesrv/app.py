
from werkzeug.serving import run_simple

from flask_discoverer import Discoverer

from adsmutils import ADSFlask

from referencesrv.views import bp, redis_db, text_model

def create_app(**config):
    """
    Create the application and return it to the user
    :return: flask.Flask application
    """

    if config:
        app = ADSFlask(__name__, static_folder=None, local_config=config)
    else:
        app = ADSFlask(__name__, static_folder=None)

    app.url_map.strict_slashes = False

    Discoverer(app)

    with  app.app_context() as ac:
        text_model()

    app.register_blueprint(bp)

    redis_db.init_app(app)

    return app

if __name__ == '__main__':
    run_simple('0.0.0.0', 5000, create_app(), use_reloader=False, use_debugger=False)