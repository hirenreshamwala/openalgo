import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import all model Bases so Alembic can see them for autogenerate
from database.user_db import Base as UserBase
from database.auth_db import Base as AuthBase
from database.symbol import Base as SymbolBase
from database.broker_creds_db import Base as BrokerCredsBase

config = context.config

# Override sqlalchemy.url from environment
config.set_main_option("sqlalchemy.url", os.getenv("DATABASE_URL", ""))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Combine all metadata
from sqlalchemy import MetaData
target_metadata = MetaData()
for base in [UserBase, AuthBase, SymbolBase, BrokerCredsBase]:
    for table in base.metadata.tables.values():
        table.tometadata(target_metadata)


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
