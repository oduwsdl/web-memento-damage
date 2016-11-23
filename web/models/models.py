from sqlalchemy import Column, Integer, String, DateTime, Text

from web import database


class MementoModel(database.Model):
    __tablename__ = 'memento'

    id = Column(Integer, primary_key=True)
    uri = Column(String(255), nullable=False)
    hashed_uri = Column(String(255), nullable=False)
    request_time = Column(DateTime(), nullable=False)
    response_time = Column(DateTime(), nullable=True)
    result = Column(Text, nullable=True)