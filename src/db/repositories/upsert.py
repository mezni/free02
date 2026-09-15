"""Generic PostgreSQL upsert helper (INSERT ... ON CONFLICT [col] DO UPDATE)."""

from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from src.db.base import Base


def upsert(
    session: Session,
    model: type[Base],
    instance: Base,
    conflict_col: str,
) -> None:
    """Insert or update `instance`, resolving conflicts on `conflict_col`."""
    values = {
        attr.key: getattr(instance, attr.key)
        for attr in inspect(model).mapper.column_attrs
        if attr.key in instance.__dict__
    }
    values.pop("id", None)
    values.pop("created_at", None)

    set_ = {key: value for key, value in values.items() if key != conflict_col}

    statement = pg_insert(model).values(**values).on_conflict_do_update(
        index_elements=[getattr(model, conflict_col)],
        set_=set_,
    )
    session.execute(statement)


__all__ = ["upsert"]