import pytest
import pymysql
from interlude import db


def test_mysql_connect_recovers_transient_failure_without_replaying_transactions():
    assert hasattr(db, "connect_with_retry")
    attempts = []
    connection = object()
    def connect():
        attempts.append(1)
        if len(attempts) < 3:
            raise pymysql.OperationalError(2003, "connection unavailable")
        return connection
    assert db.connect_with_retry(connect, sleep=lambda _: None) is connection
    assert len(attempts) == 3


@pytest.mark.parametrize("code,expected", [(2003, 3), (1045, 1)])
def test_mysql_connect_retry_is_bounded_and_auth_failure_is_immediate(code, expected):
    assert hasattr(db, "connect_with_retry")
    attempts = []
    def connect():
        attempts.append(1)
        raise pymysql.OperationalError(code, "not logged")
    with pytest.raises(pymysql.OperationalError):
        db.connect_with_retry(connect, sleep=lambda _: None)
    assert len(attempts) == expected
