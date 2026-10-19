# Настройка окружения и работа с Git

Все команды выполняются из корня проекта — каталога, в котором находится `README.md`.

## 1. Клонирование и переход на `develop`

После клонирования:

```bash
cd D8T2_MCPcore_ID_1578301-Team_TL_jessblaz_55d6eb04_b9a2_4266-1
git fetch origin
git switch develop
git pull --ff-only origin develop
```

Если локальной ветки `develop` ещё нет:

```bash
git switch --track origin/develop
```

Строка вида `origin/develop` — имя ветки, а не самостоятельная команда.

## 2. Создание виртуального окружения

Папка `.venv` не хранится в Git, поэтому после каждого нового клонирования её нужно создать:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

После активации в начале строки терминала появится:

```text
(.venv)
```

Проверьте используемый Python:

```bash
which python
python --version
```

Путь должен содержать:

```text
.../.venv/bin/python
```

## 3. Установка зависимостей

```bash
python -m pip install --upgrade pip
python -m pip install fastmcp pytest
```

Используемые компоненты:

- `FastMCP` — MCP-сервер и клиент;
- `pytest` — запуск тестов;
- `Pydantic` устанавливается вместе с FastMCP;
- `sqlite3` входит в стандартную библиотеку Python и отдельно не устанавливается.

Не устанавливайте пакеты системно:

```bash
sudo pip install ...
pip install --break-system-packages ...
```

## 4. Проверка окружения

```bash
python check_environment.py
python client.py demo
```

Демонстрация должна показать товар `hoodie` и отказ `PRODUCT_NOT_FOUND`.

В каждом новом терминале окружение активируется повторно:

```bash
source .venv/bin/activate
```

Выход из окружения:

```bash
deactivate
```

## 5. Создание рабочей ветки

Работать напрямую в `develop` нельзя.

Сначала обновите `develop`:

```bash
git switch develop
git pull --ff-only origin develop
```

Затем создайте свою ветку:

```bash
git switch -c feature/ИМЯ-ВЕТКИ
```

Рекомендуемые ветки:

- `feature/storage` — weaselda;
- `feature/domain-rules` — mysariaw;
- `feature/order-handlers` — mothmane.

Если ветка уже существует локально:

```bash
git switch feature/ИМЯ-ВЕТКИ
```

## 6. Проверка перед коммитом

Сначала запустите свои тесты:

```bash
python -m pytest -q testing/ИМЯ_ТЕСТА.py
```

Затем все доступные тесты:

```bash
python -m pytest -q
```

`scenario` и `acceptance` могут не работать, пока не объединены все части проекта.

Проверьте изменения:

```bash
git status --short
git diff
git diff --check
```

Запрещено изменять:

- `checks/`;
- `data/seed.sql`.

Не добавляем в Git:

- `.venv/`;
- `.idea/`;
- `__pycache__/`;
- `.pytest_cache/`;
- `data/*.db`;
- промежуточный `logs/client.jsonl`.

## 7. Коммит

Добавляйте только свои конкретные файлы. Не используйте `git add .`.

Пример для хранилища:

```bash
git add src/storage.py testing/test_storage.py
git status
git commit -m "Implement storage operations and transactions"
```

Пример для правил:

```bash
git add src/domain.py testing/test_rules.py
git commit -m "Implement domain rules and tests"
```

Пример для обработчиков заказов:

```bash
git add src/order_handlers.py testing/test_orders.py
git commit -m "Implement order handlers and tests"
```

## 8. Первый push ветки

При первом push нужно назначить upstream:

```bash
git push -u origin feature/ИМЯ-ВЕТКИ
```

Следующие отправки выполняются короче:

```bash
git push
```

После push участник сообщает лиду:

- имя ветки;
- последний коммит;
- какие тесты запущены;
- результат тестов;
- какие файлы изменены.

Участники самостоятельно не сливают свои ветки в `develop`. Слияние выполняет тимлид.

## 9. Слияние — только для тимлида

Тимлид принимает по одной ветке:

```bash
git fetch origin
git switch develop
git pull --ff-only origin develop
git merge --no-ff origin/feature/ИМЯ-ВЕТКИ
```

После каждого слияния:

```bash
python -m pytest -q
git status
```

Если всё прошло:

```bash
git push origin develop
```

После объединения всех частей:

```bash
python client.py scenario
python checks/acceptance.py --project . --profile base
```

## 10. Если появилась ошибка Git

При конфликте, расхождении веток или ошибке `pull` остановитесь и отправьте лиду вывод:

```bash
git status
git branch -vv
git log --oneline --graph --decorate -10
```

Без согласования с лидом не выполняйте:

```bash
git reset --hard
git rebase
git push --force
```

Главное правило: код считается переданным команде только после коммита, push рабочей ветки и успешного слияния в `develop`.
