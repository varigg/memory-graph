from unittest.mock import patch

import pytest

FIXED_VECTOR = [0.1, 0.2, 0.3]


@pytest.fixture()
def app(tmp_path):
    db_file = tmp_path / "test_memory.db"

    with patch("embeddings.embed", return_value=FIXED_VECTOR):
        from api_server import create_app

        flask_app = create_app(db_path=str(db_file))
        flask_app.config["TESTING"] = True
        yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()
