"""SQLAlchemy ORM table metadata. Tables are added in the initial migration phase."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
