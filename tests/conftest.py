# conftest.py

import pytest

@pytest.fixture
def client():
    from app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

@pytest.fixture
def init_database():
    from app import conn
    # Setup code to initialize the database can go here
    yield
    # Teardown code to clean up the database can go here