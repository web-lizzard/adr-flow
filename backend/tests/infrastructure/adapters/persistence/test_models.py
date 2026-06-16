"""ORM metadata contract tests (no database required)."""

from sqlalchemy import Boolean, DateTime, Index, String, Table, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from infrastructure.adapters.persistence.models import Adr, Base, Event, User


def test_metadata_defines_expected_tables() -> None:
    assert set(Base.metadata.tables) == {"events", "users", "adrs"}


def test_events_table_columns_and_indexes() -> None:
    table = Event.__table__
    assert isinstance(table, Table)

    assert table.c.id.type.__class__ is UUID
    assert table.c.aggregate_type.type.__class__ is String
    assert table.c.aggregate_id.type.__class__ is UUID
    assert table.c.event_type.type.__class__ is String
    assert table.c.payload.type.__class__ is JSONB
    assert table.c.occurred_at.type.__class__ is DateTime
    assert table.c.processed_at.type.__class__ is DateTime

    assert table.c.id.primary_key
    assert not table.c.aggregate_type.nullable
    assert not table.c.aggregate_id.nullable
    assert not table.c.event_type.nullable
    assert not table.c.payload.nullable
    assert not table.c.occurred_at.nullable
    assert table.c.processed_at.nullable

    index_names = {index.name for index in table.indexes}
    assert index_names == {"ix_events_aggregate", "ix_events_processed_at"}
    aggregate_index = next(i for i in table.indexes if i.name == "ix_events_aggregate")
    assert isinstance(aggregate_index, Index)
    assert [col.name for col in aggregate_index.columns] == [
        "aggregate_type",
        "aggregate_id",
    ]


def test_users_table_columns_and_unique_email() -> None:
    table = User.__table__
    assert isinstance(table, Table)

    assert table.c.id.type.__class__ is UUID
    assert table.c.email.type.__class__ is String
    assert table.c.password_hash.type.__class__ is Text
    assert table.c.created_at.type.__class__ is DateTime

    assert table.c.id.primary_key
    assert not table.c.email.nullable
    assert not table.c.password_hash.nullable
    assert not table.c.created_at.nullable

    assert table.c.email.unique is True


def test_adrs_table_columns_jsonb_and_soft_delete() -> None:
    table = Adr.__table__
    assert isinstance(table, Table)

    assert table.c.id.type.__class__ is UUID
    assert table.c.user_id.type.__class__ is UUID
    assert table.c.title.type.__class__ is Text
    assert table.c.content.type.__class__ is Text
    assert table.c.status.type.__class__ is String
    assert table.c.review_annotations.type.__class__ is JSONB
    assert table.c.is_deleted.type.__class__ is Boolean
    assert table.c.created_at.type.__class__ is DateTime
    assert table.c.updated_at.type.__class__ is DateTime
    assert table.c.reviewed_at.type.__class__ is DateTime

    assert table.c.review_annotations.nullable
    assert not table.c.is_deleted.nullable
    assert not table.c.user_id.nullable
    assert not table.c.status.nullable

    index_names = {index.name for index in table.indexes}
    assert index_names == {"ix_adrs_user_id", "uq_adrs_active_user_title_ci"}

    title_index = next(
        index for index in table.indexes if index.name == "uq_adrs_active_user_title_ci"
    )
    assert title_index.unique is True
