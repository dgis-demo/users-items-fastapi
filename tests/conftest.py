import os
import psycopg2
import pytest
from alembic.config import Config
from databases import Database
from pathlib import Path
from urllib import parse

from alembic import command
from app import settings


@pytest.fixture(scope='session', autouse=True)
def test_db_uri() -> str:
    db_uri = os.getenv('DB_URI')
    test_db_name = 'test'
    db_parsed_uri = parse.urlparse(db_uri)._asdict()
    db_parsed_uri['path'] = f'/{test_db_name}'
    test_db_parsed_uri = parse.ParseResult(**db_parsed_uri)
    test_db_uri_ = parse.urlunparse(test_db_parsed_uri)

    connection = psycopg2.connect(db_uri)
    connection.autocommit = True
    cursor = connection.cursor()
    cursor.execute(f'DROP database IF EXISTS {test_db_name}')
    cursor.execute(f'CREATE database {test_db_name}')
    print(f'Test database "{test_db_name}" has been created')

    alembic_cfg = Config(Path(os.getcwd()) / 'alembic.ini')
    os.environ['DB_URI'] = test_db_uri_
    command.upgrade(alembic_cfg, 'head')
    try:
        yield test_db_uri_
    finally:
        cursor.execute(f'DROP database {test_db_name}')
        connection.close()
        os.environ['DB_URI'] = db_uri
        print(f'Test database "{test_db_name}" has been dropped')


@pytest.fixture
async def database(test_db_uri):
    db = settings.database
    test_db = Database(test_db_uri, force_rollback=True)
    settings.database = test_db
    await test_db.connect()
    try:
        yield test_db
    finally:
        await test_db.disconnect()
        settings.database = db
