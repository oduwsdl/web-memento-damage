from memento_damage.web import flask_app

class MementoModel(flask_app.db.Model):
    # id = flask_app.db.Column(flask_app.db.Integer, primary_key=True)
    uri = flask_app.db.Column(flask_app.db.String(255), nullable=False)
    hashed_uri = flask_app.db.Column(flask_app.db.String(255), primary_key=True, nullable=False)
    request_time = flask_app.db.Column(flask_app.db.DateTime(), nullable=False)
    response_time = flask_app.db.Column(flask_app.db.DateTime(), nullable=True)
    result = flask_app.db.Column(flask_app.db.Text, nullable=True)