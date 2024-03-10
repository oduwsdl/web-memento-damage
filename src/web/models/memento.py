from web import flask_app

class MementoDbModel(flask_app.flask_app.db.Model):
    uri = flask_app.db.Column(flask_app.db.String(255), nullable=False, primary_key=True)
    directory = flask_app.db.Column(flask_app.db.String(255), nullable=False)
    status = flask_app.db.Column(flask_app.db.String(255), nullable=False)
    dereferencedUri = flask_app.db.Column(flask_app.db.String(255), nullable=True)
    datetimeRequest = flask_app.db.Column(flask_app.db.DateTime(), nullable=False)
    datetimeResponse = flask_app.db.Column(flask_app.db.DateTime(), nullable=True)
    result = flask_app.db.Column(flask_app.db.Text, nullable=True)