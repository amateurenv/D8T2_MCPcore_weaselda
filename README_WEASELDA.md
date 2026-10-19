# Участок weaselda: SQLite, состояние и транзакции

Этот репозиторий — отдельная учебная копия для участка **weaselda**. Он не
заменяет командный GitLab. Готовый код нужно понять, проверить и перенести в
свою ветку учебного проекта.

## Что тебе принадлежит

Основной файл — `src/storage.py`. В нём реализованы семь методов:

| Метод | Что делает |
| --- | --- |
| `list_products()` | Возвращает каталог в порядке `id` вместе с остатками |
| `get_user(user_id)` | Возвращает `{"id": ..., "coins": ...}` либо `None` |
| `get_order(order_id)` | Возвращает все поля заказа либо `None` |
| `count_owned(user_id, product_id)` | Считает товар в заказах `created` и `picked_up` |
| `create_order(...)` | Создаёт заказ, списывает коины и уменьшает остаток одной транзакцией |
| `cancel_order(order, refund)` | Возвращает коины и товар, затем ставит `cancelled` одной транзакцией |
| `confirm_pickup(order_id)` | Меняет только статус заказа на `picked_up` |

Дополнительный файл `testing/test_storage.py` проверяет хранение отдельно от
MCP и обработчиков.

## Где находится твой код в общей архитектуре

Путь запроса выглядит так:

```text
client.py
  → src/mcp_adapter.py
  → src/read_handlers.py или src/order_handlers.py
  → src/domain.py (если требуется правило)
  → src/storage.py
  → SQLite
```

`storage.py` отвечает только за чтение и сохранение состояния. Он не выбирает
бизнес-код ошибки вроде `INSUFFICIENT_COINS`: это делают обработчики и функции
из `domain.py`. В обработчиках, наоборот, не должно быть SQL.

## Как устроены методы чтения

### `list_products`

Сначала выбираются идентификаторы товаров с `ORDER BY id`. Для каждого
идентификатора вызывается уже готовый `get_product`, который добавляет остатки
по размерам. Поэтому результат совпадает с форматом инструмента `get_product`,
а каталог имеет стабильный порядок.

### `get_user` и `get_order`

Используются параметризованные запросы с `?`:

```python
row = connection.execute("... WHERE id = ?", (value,)).fetchone()
```

Значение не склеивается со строкой SQL. Если строка не найдена, возвращается
`None`; чтение не создаёт пользователя или заказ.

### `count_owned`

Суммируется `quantity` только для состояний `created` и `picked_up`.
`cancelled` не учитывается, поэтому отмена освобождает пользовательский лимит.
`COALESCE(..., 0)` превращает пустую сумму в целое число `0`.

## Почему запись сделана транзакциями

Конструкция:

```python
with self.connection:
    ...несколько SQL-команд...
```

означает: либо фиксируются все команды, либо при исключении откатываются все.
Например, создание заказа меняет три таблицы:

1. `orders` — появляется заказ со статусом `created`;
2. `users` — уменьшается баланс;
3. `stock` — уменьшается остаток.

После `UPDATE` проверяется `rowcount`. Если пользователь, размер или достаточный
остаток внезапно не найдены, выбрасывается исключение и даже уже выполненный
`INSERT` откатывается. Это защитный второй рубеж; обычные бизнес-проверки должны
сработать раньше в `order_handlers.py` и `domain.py`.

Отмена тоже атомарна: коины, товар и статус изменяются вместе. Повторная отмена
не пройдёт условие `status = 'created'`; транзакция откатит предшествующие
изменения, поэтому двойного возврата не будет.

Выдача меняет только статус. Баланс и остаток были изменены при создании заказа,
поэтому повторно их трогать нельзя.

## Как перенести работу в учебный GitLab

Все команды выполняй из корня учебного репозитория. Не используй `sudo` и не
работай прямо в `master`.

```bash
git switch develop
git pull --ff-only origin develop
git switch -c feature/storage
```

Если ветка уже существует:

```bash
git switch feature/storage
```

Скопируй из этого GitHub-репозитория:

- обязательно `src/storage.py`;
- желательно `testing/test_storage.py`;
- не копируй `README_WEASELDA.md` в сдаваемый проект.

Перед коммитом:

```bash
python3 check_environment.py
python3 -m pytest -q
git diff --check
git status --short
```

Локальные базы `data/*.db`, `.venv`, `.idea` и кэши добавлять нельзя.

Затем:

```bash
git add src/storage.py testing/test_storage.py
git commit -m "Implement SQLite storage and transactions"
git push -u origin feature/storage
```

Отправь тимлиду:

- название ветки `feature/storage`;
- хеш из `git log -1 --oneline`;
- результат `python3 -m pytest -q`;
- формы значений, перечисленные в следующем разделе.

## Интерфейсы для команды

Сообщи `jessblaz` и `mothmane`:

```text
Storage.list_products() -> list[dict]
Storage.get_user(user_id) -> {"id": str, "coins": int} | None
Storage.get_order(order_id) -> dict со всеми полями orders | None
Storage.count_owned(user_id, product_id) -> int
Storage.create_order(...) -> dict созданного заказа
Storage.cancel_order(order, refund) -> dict отменённого заказа
Storage.confirm_pickup(order_id) -> dict выданного заказа
```

Обработчики должны передавать в `cancel_order` заказ, который ранее получили
через `get_order`, а сумму возврата — результат `domain.refund_amount`.

## Что проверить вместе с тимлидом

После объединения `feature/storage` в командную `develop`:

```bash
python3 client.py call list_products '{}'
python3 client.py call get_coin_balance '{"user_id":"student_01"}'
python3 client.py call get_coin_balance '{"user_id":"missing"}'
python3 client.py call get_order_status '{"order_id":"missing"}'
python3 -m pytest -q
```

Ожидания:

- каталог отсортирован по `id`;
- баланс `student_01` равен `1000` на новой базе;
- неизвестный пользователь даёт `USER_NOT_FOUND`;
- неизвестный заказ даёт `ORDER_NOT_FOUND`.

Когда будут готовы `domain.py` и `order_handlers.py`, запусти полную проверку:

```bash
python3 checks/acceptance.py --project . --profile base
```

## Что объяснить на защите

1. Почему SQL находится в `storage.py`, а правила покупки — в `domain.py`.
2. Почему параметры SQL передаются через `?`, а не вставляются в строку.
3. Какие три изменения входят в транзакцию создания заказа.
4. Почему исключение внутри `with connection:` откатывает частичные изменения.
5. Почему `count_owned` не считает отменённые заказы.
6. Почему выдача меняет только статус.
7. Как условие `status = 'created'` защищает от повторного действия.

## Чек-лист готовности участка

- [ ] Все семь методов `Storage` реализованы.
- [ ] В `src/storage.py` нет `TODO` и `NotImplementedError`.
- [ ] SQL использует параметры `?`.
- [ ] Создание и отмена выполняются транзакциями.
- [ ] Чтение неизвестных сущностей возвращает `None`.
- [ ] Отменённые заказы не занимают пользовательский лимит.
- [ ] Выдача не меняет баланс и остаток.
- [ ] Тесты проходят.
- [ ] В коммит не попали `.db`, `.venv`, `.idea` и кэши.
- [ ] Ветка отправлена в учебный GitLab и передана тимлиду.
