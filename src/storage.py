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
            self.connection.executescript(Path(seed_path).read_text(encoding="utf-8"))
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
        product["stock"] = {r["size"]: r["quantity"] for r in rows}
        return product

    def list_products(self):
        'Список товаров в порядке id.'
        rows = self.connection.execute(
            "SELECT id FROM products ORDER BY id"
        ).fetchall()
        return [self.get_product(row["id"]) for row in rows]

    def get_user(self, user_id):
        'Словарь id, coins или None. Чтение не создаёт пользователя.'
        row = self.connection.execute(
            "SELECT id, coins FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return None if row is None else dict(row)

    def get_order(self, order_id):
        'Словарь со всеми полями orders или None.'
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
        'Число единиц товара в created и picked_up, по всем размерам.'
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

    def create_order(self, user_id, product_id, size, quantity, total_price):
        'Записать заказ, баланс и остаток одной транзакцией. Вернуть заказ.'
        order_id = str(uuid.uuid4())

        # Контекст соединения фиксирует все три изменения вместе. Если любая
        # проверка rowcount ниже не проходит, исключение откатывает транзакцию.
        with self.connection:
            self.connection.execute(
                """
                INSERT INTO orders
                    (id, user_id, product_id, size, quantity, total_price, status)
                VALUES (?, ?, ?, ?, ?, ?, 'created')
                """,
                (order_id, user_id, product_id, size, quantity, total_price),
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
        'Вернуть переданную сумму и товар, поменять статус одной транзакцией.'
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
                (order["quantity"], order["product_id"], order["size"]),
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
        'Изменить только статус. Баланс и остаток уже уменьшены при покупке.'
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
