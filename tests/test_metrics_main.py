from pathlib import Path
from types import SimpleNamespace

from metrics_report.__main__ import DB_NAME, TEST_DB_NAME, db_path


def test_test_flag_uses_separate_store():
    s = SimpleNamespace(data_dir=Path("data"))
    assert db_path(s, False) == Path("data") / DB_NAME
    assert db_path(s, True) == Path("data") / TEST_DB_NAME
    assert DB_NAME != TEST_DB_NAME
