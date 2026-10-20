# Задание weaselda: завершить SQLite-хранилище

Текущий коммит `612c7d2` реализует чтение и создание заказа, но участок ещё не
закончен:

- `cancel_order()` содержит `NotImplementedError`;
- `confirm_pickup()` содержит `NotImplementedError`;
- отсутствует `testing/test_storage.py`;
- транзакции отмены, повторной отмены и выдачи не подтверждены тестами.

Нужно завершить `src/storage.py`, добавить тесты, запушить отдельную feature-ветку
и передать её тимлиду. Самостоятельно сливать её в `develop` не нужно.

## 1. Обновить проект и создать ветку

Все команды выполнять из корня проекта.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/storage-complete
```

Если ветка уже существует:

```bash
git switch feature/storage-complete
```

Активировать окружение:

```bash
source .venv/bin/activate
python check_environment.py
```

## 2. Полностью заменить `src/storage.py`

```python
"""SQLite. Методы записи вызываются после проверки правил."""

import sqlite3
import uuid
from pathlib import Path


class Storage:
    def __init__(self, db_path, seed_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        is_new = not self.path.exists()
        self.connection = sqlite3.connect(self.path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")

        if is_new:
            self.connection.executescript(
                Path(seed_path).read_text(encoding="utf-8")
            )
            self.connection.commit()

    def close(self):
        self.connection.close()

    def get_product(self, product_id):
        row = self.connection.execute(
            "SELECT id, name, price_coins, user_limit FROM products WHERE id = ?",
            (product_id,),
        ).fetchone()

        if row is None:
            return None

        product = dict(row)
        rows = self.connection.execute(
            "SELECT size, quantity FROM stock WHERE product_id = ? ORDER BY size",
            (product_id,),
        ).fetchall()
        product["stock"] = {
            stock_row["size"]: stock_row["quantity"]
            for stock_row in rows
        }
        return product

    def list_products(self):
        """Вернуть товары в порядке идентификаторов."""
        rows = self.connection.execute(
            "SELECT id FROM products ORDER BY id"
        ).fetchall()
        return [self.get_product(row["id"]) for row in rows]

    def get_user(self, user_id):
        """Вернуть словарь с id и coins или None."""
        row = self.connection.execute(
            "SELECT id, coins FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def get_order(self, order_id):
        """Вернуть все поля заказа или None."""
        row = self.connection.execute(
            """
            SELECT id, user_id, product_id, size, quantity, total_price, status
            FROM orders
            WHERE id = ?
            """,
            (order_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def count_owned(self, user_id, product_id):
        """Посчитать товар в заказах created и picked_up по всем размерам."""
        row = self.connection.execute(
            """
            SELECT COALESCE(SUM(quantity), 0) AS quantity
            FROM orders
            WHERE user_id = ?
              AND product_id = ?
              AND status IN ('created', 'picked_up')
            """,
            (user_id, product_id),
        ).fetchone()
        return row["quantity"]

    def create_order(
        self,
        user_id,
        product_id,
        size,
        quantity,
        total_price,
    ):
        """Создать заказ, списать коины и остаток одной транзакцией."""
        order_id = str(uuid.uuid4())

        # Контекст соединения фиксирует все три изменения вместе.
        # Любое исключение внутри блока откатывает всю транзакцию.
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO orders
                    (id, user_id, product_id, size, quantity, total_price, status)
                VALUES (?, ?, ?, ?, ?, ?, 'created')
                """,
                (
                    order_id,
                    user_id,
                    product_id,
                    size,
                    quantity,
                    total_price,
                ),
            )

            user_update = self.connection.execute(
                """
                UPDATE users
                SET coins = coins - ?
                WHERE id = ? AND coins >= ?
                """,
                (total_price, user_id, total_price),
            )
            if user_update.rowcount != 1:
                raise ValueError("Не удалось списать коины")

            stock_update = self.connection.execute(
                """
                UPDATE stock
                SET quantity = quantity - ?
                WHERE product_id = ? AND size = ? AND quantity >= ?
                """,
                (quantity, product_id, size, quantity),
            )
            if stock_update.rowcount != 1:
                raise ValueError("Не удалось уменьшить остаток")

        return self.get_order(order_id)

    def cancel_order(self, order, refund):
        """Вернуть коины и товар, затем отменить заказ одной транзакцией."""
        with self.connection:
            user_update = self.connection.execute(
                "UPDATE users SET coins = coins + ? WHERE id = ?",
                (refund, order["user_id"]),
            )
            if user_update.rowcount != 1:
                raise ValueError("Не удалось вернуть коины")

            stock_update = self.connection.execute(
                """
                UPDATE stock
                SET quantity = quantity + ?
                WHERE product_id = ? AND size = ?
                """,
                (
                    order["quantity"],
                    order["product_id"],
                    order["size"],
                ),
            )
            if stock_update.rowcount != 1:
                raise ValueError("Не удалось вернуть товар")

            order_update = self.connection.execute(
                """
                UPDATE orders
                SET status = 'cancelled'
                WHERE id = ? AND status = 'created'
                """,
                (order["id"],),
            )
            if order_update.rowcount != 1:
                raise ValueError("Заказ уже нельзя отменить")

        return self.get_order(order["id"])

    def confirm_pickup(self, order_id):
        """Изменить только статус заказа с created на picked_up."""
        with self.connection:
            order_update = self.connection.execute(
                """
                UPDATE orders
                SET status = 'picked_up'
                WHERE id = ? AND status = 'created'
                """,
                (order_id,),
            )
            if order_update.rowcount != 1:
                raise ValueError("Заказ уже нельзя выдать")

        return self.get_order(order_id)
```

## 3. Создать `testing/test_storage.py`

```python
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
    """Снимок изменяемых таблиц для проверки полного отката."""
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
        "student_01",
        "bottle",
        "one_size",
        quantity=1,
        total_price=150,
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
            "student_poor",
            "hoodie",
            "M",
            quantity=1,
            total_price=500,
        )

    assert table_state(storage) == before


def test_cancel_restores_balance_stock_and_limit(storage):
    order = storage.create_order(
        "student_01",
        "bottle",
        "one_size",
        quantity=1,
        total_price=150,
    )

    cancelled = storage.cancel_order(
        order,
        refund=order["total_price"],
    )

    assert cancelled["status"] == "cancelled"
    assert storage.get_user("student_01")["coins"] == 1000
    assert storage.get_product("bottle")["stock"]["one_size"] == 12
    assert storage.count_owned("student_01", "bottle") == 0

    after_first_cancel = table_state(storage)
    with pytest.raises(ValueError):
        storage.cancel_order(
            order,
            refund=order["total_price"],
        )
    assert table_state(storage) == after_first_cancel


def test_pickup_changes_only_order_status(storage):
    order = storage.create_order(
        "student_01",
        "bottle",
        "one_size",
        quantity=1,
        total_price=150,
    )
    balance_before = storage.get_user("student_01")["coins"]
    stock_before = storage.get_product("bottle")["stock"]["one_size"]

    picked_up = storage.confirm_pickup(order["id"])

    assert picked_up["status"] == "picked_up"
    assert storage.get_user("student_01")["coins"] == balance_before
    assert storage.get_product("bottle")["stock"]["one_size"] == stock_before
    assert storage.count_owned("student_01", "bottle") == 1
```

## 4. Запустить проверки

Проверить отсутствие заглушек. Если `rg` не установлен, использовать `grep`:

```bash
grep -nE "TODO|NotImplementedError" src/storage.py || true
```

При готовом файле команда ничего не выводит.

Запустить тесты своего участка:

```bash
python -m pytest -q testing/test_storage.py
```

Ожидаемый результат:

```text
5 passed
```

Затем запустить все тесты, которые уже находятся в текущем `develop`:

```bash
python -m pytest -q
```

До получения кода остальных участников ожидается не меньше 13 пройденных
тестов: 5 тестов хранилища, 7 тестов чтения и 1 стартовый тест.

Проверить формат diff:

```bash
git diff --check
git status --short
```

## 5. Закоммитить только два файла

Не использовать `git add .`.

```bash
git add src/storage.py testing/test_storage.py
git diff --cached --check
git diff --cached --stat
git commit -m "Complete storage transactions and tests"
git push -u origin feature/storage-complete
```

Не добавлять:

- `logs/`;
- `.venv/`;
- `.idea/`;
- `data/*.db`;
- `__pycache__/`;
- `.pytest_cache/`.

Не изменять:

- `checks/`;
- `data/seed.sql`;
- файлы других участников.

## 6. Что отправить тимлиду

После push отправить:

```text
Ветка: feature/storage-complete
Коммит: <хеш коммита>
Изменены: src/storage.py, testing/test_storage.py
Тест участка: 5 passed
Все текущие тесты: <результат>
```

Тимлид проверит ветку и самостоятельно объединит её с `develop`.

## Как работает реализация

- `get_product()` возвращает товар и остатки по размерам.
- `list_products()` возвращает каталог в порядке идентификаторов.
- `get_user()` и `get_order()` ничего не создают при чтении и возвращают
  `None` для неизвестного идентификатора.
- `count_owned()` учитывает только `created` и `picked_up`. Отменённые заказы
  не расходуют пользовательский лимит.
- `create_order()` записывает заказ, списывает коины и уменьшает остаток в
  одной транзакции. Если одно действие не выполнено, откатываются все таблицы.
- `cancel_order()` возвращает коины и товар ровно один раз. Повторная отмена
  не проходит условие `status = 'created'`, вызывает исключение и откатывает
  уже сделанные внутри транзакции изменения.
- `confirm_pickup()` меняет только статус. Коины и товар уже были списаны при
  создании заказа, поэтому при выдаче они не изменяются.
