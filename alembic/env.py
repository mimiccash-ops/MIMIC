"""
MIMIC - Alembic Environment Configuration
==========================================
This module configures Alembic to work with the Flask-SQLAlchemy models.
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the Flask app and models
from app import app as flask_app
from models import db

# Alembic Config object
config = context.config

# Set up logging from alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Get the SQLAlchemy metadata from our models
target_metadata = db.metadata


def get_url():
    """Get database URL from Flask config or environment."""
    # Try Flask config first
    with flask_app.app_context():
        url = flask_app.config.get('SQLALCHEMY_DATABASE_URI')
        if url:
            return url
    
    # Fallback to environment variable
    url = os.environ.get('DATABASE_URL')
    if url:
        # Handle Heroku/Railway-style postgres:// URLs
        if url.startswith('postgres://'):
            url = url.replace('postgres://', 'postgresql://', 1)
        return url
    
    # Default to SQLite for local development
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return f'sqlite:///{os.path.join(base_dir, "brain_capital.db")}'


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode.
    
    This configures the context with just a URL and not an Engine,
    though an Engine is acceptable here as well. By skipping the Engine
    creation we don't even need a DBAPI to be available.
    
    Calls to context.execute() here emit the given string to the
    script output.
    """
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode.
    
    In this scenario we need to create an Engine and associate a
    connection with the context.
    """
    # Create configuration dict
    configuration = config.get_section(config.config_ini_section, {})
    configuration['sqlalchemy.url'] = get_url()
    
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
