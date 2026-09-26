from alembic import context
from interlude.config import get_settings
from interlude.db import Base, make_engine

if context.is_offline_mode():
    context.configure(dialect_name="mysql", target_metadata=Base.metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()
else:
    with make_engine(get_settings()).connect() as connection:
        context.configure(connection=connection, target_metadata=Base.metadata)
        with context.begin_transaction():
            context.run_migrations()
