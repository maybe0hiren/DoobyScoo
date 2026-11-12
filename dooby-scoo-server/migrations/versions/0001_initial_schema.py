from app.database.base import SCHEMA_STATEMENTS, DROP_STATEMENTS

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade(connection=None):
    if connection is not None:
        for stmt in SCHEMA_STATEMENTS:
            connection.execute(stmt)
        return
    from alembic import op
    for stmt in SCHEMA_STATEMENTS:
        op.execute(stmt)


def downgrade(connection=None):
    if connection is not None:
        for stmt in DROP_STATEMENTS:
            connection.execute(stmt)
        return
    from alembic import op
    for stmt in DROP_STATEMENTS:
        op.execute(stmt)

