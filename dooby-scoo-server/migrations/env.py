import os
from logging.config import fileConfig

try:
    from alembic import context
    from sqlalchemy import engine_from_config, pool
except ImportError:
    context = None

from app.config import settings
from app.database.base import SCHEMA_STATEMENTS


def runMigrationsOffline():
    if context is None:
        return
    url = settings.databaseUrl
    context.configure(url=url, target_metadata=None, literal_binds=True)
    with context.begin_transaction():
        for stmt in SCHEMA_STATEMENTS:
            context.execute(stmt)


def runMigrationsOnline():
    if context is None:
        return
    configuration = context.config.get_section(context.config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = os.getenv("DATABASE_URL", settings.databaseUrl)
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            for stmt in SCHEMA_STATEMENTS:
                context.execute(stmt)


if context is not None:
    if context.config.config_file_name is not None:
        fileConfig(context.config.config_file_name)
    if context.is_offline_mode():
        runMigrationsOffline()
    else:
        runMigrationsOnline()

