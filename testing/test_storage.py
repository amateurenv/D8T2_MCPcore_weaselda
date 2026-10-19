"""Изолированные проверки SQLite-хранилища участка weaselda."""

from pathlib import Path

import pytest

from src.storage import Storage


SEED = Path(__file__).resolve().parents[1] / "data/seed.sql"


@pytest.fixture
def storage(tmp_path):
    instance = Storage(tmp_path / "storage.db", SEED)
    try:
        yield instance
    finally:
        instance.close()


def table_state(storage):
    """Снимок всех изменяемых таблиц для проверки отката."""
    state = {}
    for table in ("products", "stock", "users", "orders"):
        rows = storage.connection.execute(
            f"SELECT * FROM {table} ORDER BY 1, 2"
        ).fetchall()
        state[table] = [tuple(row) for row in rows]
    return state


def test_read_methods_return_expected_shapes(storage):
    products = storage.list_products()
    assert [product["id"] for product in products] == sorted(
        product["id"] for product in products
    )
    assert storage.get_user("student_01") == {
        "id": "student_01",
        "coins": 1000,
    }
    assert storage.get_user("missing") is None
    assert storage.get_order("missing") is None
    assert storage.count_owned("student_01", "bottle") == 0


def test_create_order_changes_order_balance_and_stock(storage):
    order = storage.create_order(
        "student_01", "bottle", "one_size", quantity=1, total_price=150
    )

    assert order["status"] == "created"
    assert order["total_price"] == 150
    assert storage.get_user("student_01")["coins"] == 850
    assert storage.get_product("bottle")["stock"]["one_size"] == 11
    assert storage.count_owned("student_01", "bottle") == 1


def test_failed_create_rolls_back_every_table(storage):
    before = table_state(storage)

    with pytest.raises(ValueError):
        storage.create_order(
            "student_poor", "hoodie", "M", quantity=1, total_price=500
        )

    assert table_state(storage) == before


def test_cancel_restores_balance_stock_and_limit(storage):
    order = storage.create_order(
        "student_01", "bottle", "one_size", quantity=1, total_price=150
    )

    cancelled = storage.cancel_order(order, refund=order["total_price"])

    assert cancelled["status"] == "cancelled"
    assert storage.get_user("student_01")["coins"] == 1000
    assert storage.get_product("bottle")["stock"]["one_size"] == 12
    assert storage.count_owned("student_01", "bottle") == 0

    after_first_cancel = table_state(storage)
    with pytest.raises(ValueError):
        storage.cancel_order(order, refund=order["total_price"])
    assert table_state(storage) == after_first_cancel


def test_pickup_changes_only_order_status(storage):
    order = storage.create_order(
        "student_01", "bottle", "one_size", quantity=1, total_price=150
    )
    balance_before = storage.get_user("student_01")["coins"]
    stock_before = storage.get_product("bottle")["stock"]["one_size"]

    picked_up = storage.confirm_pickup(order["id"])

    assert picked_up["status"] == "picked_up"
    assert storage.get_user("student_01")["coins"] == balance_before
    assert storage.get_product("bottle")["stock"]["one_size"] == stock_before
    assert storage.count_owned("student_01", "bottle") == 1
