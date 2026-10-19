"""Исходная проверка. Запускайте неизменённую копию проверяющего."""
import argparse
import asyncio
import json
import sqlite3
import sys
import tempfile
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport
from jsonschema import validate

HERE = Path(__file__).resolve().parent
REFERENCE = json.loads((HERE / "tools_reference.json").read_text(encoding="utf-8"))
SPECS = {t["name"]: t for t in REFERENCE["tools"]}
SEED = HERE / "fixture.sql"
TABLES = ("products", "stock", "users", "orders")

def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k,v in value.items()
                if k not in ("title", "$schema") and not (k == "required" and v == [])}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value

def snapshot(db):
    with sqlite3.connect(db) as con:
        return {t: sorted(con.execute("SELECT * FROM " + t).fetchall()) for t in TABLES}

def reset(db):
    with sqlite3.connect(db) as con:
        con.executescript(
            "DELETE FROM orders; DELETE FROM stock; DELETE FROM users; DELETE FROM products;"
        )
        con.executescript(SEED.read_text(encoding="utf-8"))

def sql(db, command, args=()):
    with sqlite3.connect(db) as con:
        return con.execute(command, args).fetchall()

async def check(project, profile):
    contract = json.loads((project / "contracts/tools_schemas.json").read_text(encoding="utf-8"))
    submitted = {t["name"]:t for t in contract["tools"]}
    assert len(contract["tools"]) == 7 and set(submitted) == set(SPECS), "Нужны семь уникальных инструментов"
    for name, spec in SPECS.items():
        text = submitted[name]["description"]
        assert isinstance(text,str) and text.strip() and "TODO" not in text, name + ": заполните описание"
        for field in ("inputSchema", "outputSchema"):
            assert normalized(submitted[name][field]) == normalized(spec[field]), name + ": изменён контракт"

    calls = 0
    with tempfile.TemporaryDirectory(prefix="lavka-check-") as temp:
        db = Path(temp) / "check.db"
        server_log = Path(temp) / "server.log"
        def connection():
            return Client(StdioTransport(
                command=sys.executable, args=["-m", "src.server", "--db", str(db), "--seed", str(SEED)],
                cwd=str(project), log_file=server_log), timeout=15)

        try:
            async with connection() as client:
                remote = {t.name:t for t in await client.list_tools()}
                assert set(remote) == set(SPECS), "На сервере должны быть ровно семь обязательных инструментов"
                for name, tool in remote.items():
                    assert normalized(tool.inputSchema) == normalized(SPECS[name]["inputSchema"]), name + ": схема входа сервера"
                    assert normalized(tool.outputSchema) == normalized(SPECS[name]["outputSchema"]), name + ": схема ответа сервера"
                    assert tool.description == submitted[name]["description"], name + ": описание не дошло до клиента"
                print("OK — семь контрактов опубликованы сервером")

                async def call(name, args=None):
                    nonlocal calls
                    calls += 1
                    result = await client.call_tool(name,args or {},raise_on_error=False)
                    assert not result.is_error, name + ": " + str(result.content)
                    data = result.structured_content
                    validate(data, SPECS[name]["outputSchema"])
                    return data

                async def ok(name, args=None):
                    answer = await call(name,args)
                    assert answer["ok"], name + ": " + str(answer)
                    return answer["data"]

                async def refused(name, args, code):
                    before = snapshot(db)
                    answer = await call(name,args)
                    assert answer["ok"] is False and answer["error"]["code"] == code, name + ": ожидался " + code + ", получено " + str(answer)
                    assert snapshot(db) == before, name + ": после отказа изменились данные"

                def purchase(user="student_01", product="bottle", size="one_size", quantity=1):
                    return {"user_id":user,"product_id":product,"size":size,"quantity":quantity}

                before = snapshot(db)
                products = (await ok("list_products"))["products"]
                assert [x["id"] for x in products] == ["bottle","hoodie","stickers","tote","tshirt"], 'Каталог неполон или нарушен порядок товаров'
                hoodie = await ok("get_product",{"product_id":"hoodie"})
                assert hoodie["price_coins"] == 500 and hoodie["stock"]["M"] == 5, 'Исходная цена или остаток худи неверны'
                assert (await ok("get_coin_balance",{"user_id":"student_01"}))["balance"] == 1000, 'Начальный баланс student_01 должен быть 1000'
                assert snapshot(db) == before, "Чтение изменило данные"
                await refused("get_product",{"product_id":"missing"},"PRODUCT_NOT_FOUND")
                await refused("get_coin_balance",{"user_id":"missing"},"USER_NOT_FOUND")
                for name in ("get_order_status","cancel_order","confirm_pickup"):
                    await refused(name,{"order_id":"missing"},"ORDER_NOT_FOUND")
                print("OK — чтение и неизвестные идентификаторы")

                order = await ok("create_order", {"user_id":"student_01","product_id":"bottle","size":"one_size"})
                assert order["status"] == "created" and order["total_price"] == 150, 'Бутылка должна создать заказ created стоимостью 150'
                oid = order["order_id"]
                assert sql(db,"SELECT coins FROM users WHERE id='student_01'")[0][0] == 850, 'После покупки бутылки баланс должен быть 850'
                assert sql(db,"SELECT quantity FROM stock WHERE product_id='bottle'")[0][0] == 11, 'После покупки одной бутылки остаток должен быть 11'
                assert sql(db,"SELECT total_price,status FROM orders WHERE id=?",(oid,))[0] == (150,"created"), 'Заказ не записан со стоимостью 150 и статусом created'
                assert (await ok("get_order_status",{"order_id":oid}))["status"] == "created", 'Новый заказ должен иметь статус created'
                await ok("cancel_order",{"order_id":oid})
                refund = 135 if profile == "E3" else 150
                assert sql(db,"SELECT coins FROM users WHERE id='student_01'")[0][0] == 850+refund, 'Неверный баланс после отмены для выбранного профиля'
                assert sql(db,"SELECT quantity FROM stock WHERE product_id='bottle'")[0][0] == 12, 'Отмена должна полностью вернуть остаток бутылок до 12'
                await refused("cancel_order",{"order_id":oid},"ORDER_STATUS_ERROR")
                await refused("confirm_pickup",{"order_id":oid},"ORDER_STATUS_ERROR")
                print("OK — покупка, отмена и однократный возврат")

                reset(db)
                oid = (await ok("create_order",purchase()))["order_id"]
                before_money = sql(db,"SELECT coins FROM users ORDER BY id")
                before_stock = sql(db,"SELECT * FROM stock ORDER BY product_id,size")
                await ok("confirm_pickup",{"order_id":oid})
                assert (await ok("get_order_status",{"order_id":oid}))["status"] == "picked_up", 'После выдачи статус должен быть picked_up'
                assert sql(db,"SELECT coins FROM users ORDER BY id") == before_money, 'Выдача повторно изменила баланс'
                assert sql(db,"SELECT * FROM stock ORDER BY product_id,size") == before_stock, 'Выдача повторно изменила остатки'
                await refused("confirm_pickup",{"order_id":oid},"ORDER_STATUS_ERROR")
                await refused("cancel_order",{"order_id":oid},"ORDER_STATUS_ERROR")
                print("OK — выдача без повторного списания")

                reset(db)
                for args, code in [
                    (purchase(user="missing"),"USER_NOT_FOUND"),
                    (purchase(product="missing"),"PRODUCT_NOT_FOUND"),
                    (purchase(product="hoodie",size="XXL"),"OUT_OF_STOCK"),
                    (purchase(quantity=100),"OUT_OF_STOCK"),
                    (purchase(user="student_poor"),"INSUFFICIENT_COINS"),
                    (purchase(product="hoodie",size="M",quantity=2),"USER_LIMIT_EXCEEDED"),
                ]:
                    await refused("create_order",args,code)
                oid = (await ok("create_order",purchase(product="hoodie",size="S")))["order_id"]
                await ok("confirm_pickup",{"order_id":oid})
                await refused("create_order",purchase(product="hoodie",size="M"),"USER_LIMIT_EXCEEDED")
                reset(db)
                await ok("create_order",purchase(product="hoodie",size="XL"))
                await refused("create_order",purchase(user="student_02",product="hoodie",size="XL"),"OUT_OF_STOCK")
                print("OK — баланс, склад и лимит по всем размерам")

                reset(db)
                invalid = [purchase(quantity=q) for q in (0,-1,1.5,"2",True)]
                invalid += [{"product_id":"bottle","size":"one_size"},
                            {**purchase(),"extra":"unknown"},purchase(user=""),
                            {**purchase(),"product_id":12}]
                for args in invalid:
                    before = snapshot(db)
                    calls += 1
                    result = await client.call_tool("create_order",args,raise_on_error=False)
                    assert result.is_error, "Неверный вход принят: " + str(args)
                    assert snapshot(db) == before, "Неверный вход изменил данные"
                print("OK — неверные типы, количество и поля запроса")

                # Отмена использует сохранённую стоимость и возвращает товар полностью.
                reset(db)
                sql(db,"UPDATE products SET price_coins=151 WHERE id='bottle'")
                oid = (await ok("create_order",purchase()))["order_id"]
                sql(db,"UPDATE products SET price_coins=9999 WHERE id='bottle'")
                await ok("cancel_order",{"order_id":oid})
                expected = 1000-151+(151*9//10 if profile == "E3" else 151)
                assert sql(db,"SELECT coins FROM users WHERE id='student_01'")[0][0] == expected, 'Возврат неверен: используйте сохранённую стоимость и правило профиля'
                assert sql(db,"SELECT quantity FROM stock WHERE product_id='bottle'")[0][0] == 12, 'Отмена должна полностью вернуть остаток бутылок до 12'

                reset(db)
                sql(db,"UPDATE users SET coins=180 WHERE id='student_01'")
                if profile == "E1":
                    await refused("create_order",purchase(),"INSUFFICIENT_COINS")
                else:
                    await ok("create_order",purchase())
                reset(db)
                sql(db,"UPDATE users SET coins=200 WHERE id='student_01'")
                await ok("create_order",purchase())
                assert sql(db,"SELECT coins FROM users WHERE id='student_01'")[0][0] == 50, 'Покупка на границе остатка 50 коинов рассчитана неверно'

                reset(db)
                if profile == "E2":
                    await refused("create_order",purchase(product="stickers",quantity=3),"USER_LIMIT_EXCEEDED")
                else:
                    order = await ok("create_order",purchase(product="stickers",quantity=3))
                    assert order["total_price"] == (135 if profile == "E4" else 150), 'Цена трёх наборов стикеров не соответствует профилю'
                reset(db)
                order = await ok("create_order",purchase(product="stickers",quantity=2))
                assert order["total_price"] == 100, 'Два набора стикеров должны стоить 100'
                if profile == "E4":
                    reset(db)
                    sql(db,"UPDATE products SET price_coins=51 WHERE id='stickers'")
                    order = await ok("create_order",purchase(product="stickers",quantity=3))
                    assert order["total_price"] == 137, 'E4: стоимость 3 единиц по 51 должна округлиться до 137'
                    assert sql(db,"SELECT coins FROM users WHERE id='student_01'")[0][0] == 863, 'E4: списание не совпадает с ценой со скидкой'
                reset(db)
                oid = (await ok("create_order",purchase(product="hoodie",size="M")))["order_id"]
                if profile == "E5":
                    await refused("cancel_order",{"order_id":oid},"ORDER_STATUS_ERROR")
                else:
                    await ok("cancel_order",{"order_id":oid})
                    # Отмена освобождает лимит, включая другой размер.
                    await ok("create_order",purchase(product="hoodie",size="S"))
                print("OK — правила профиля " + profile)

                # Искусственный сбой записи проверяет откат уже начатой транзакции.
                reset(db)
                sql(db,"CREATE TRIGGER check_fail BEFORE INSERT ON orders BEGIN SELECT RAISE(ABORT,'test rollback'); END")
                before = snapshot(db)
                calls += 1
                failed = await client.call_tool("create_order",purchase(),raise_on_error=False)
                assert failed.is_error, "Искусственный сбой записи должен быть виден клиенту"
                assert snapshot(db) == before, "Частично записанная покупка после сбоя"
                sql(db,"DROP TRIGGER check_fail")
                print("OK — откат неполной записи")

                reset(db)
                saved_order = (await ok("create_order",purchase()))["order_id"]
                before_restart = snapshot(db)
            async with connection() as restarted:
                result = await restarted.call_tool("get_order_status",{"order_id":saved_order})
                calls += 1
                assert result.structured_content["data"]["status"] == "created", 'После перезапуска новый заказ не найден в состоянии created'
                assert snapshot(db) == before_restart, "Перезапуск сбросил состояние"
            print("OK — состояние переживает перезапуск")
        except Exception:
            print("Проверьте первый не прошедший сценарий и выбранный профиль.",file=sys.stderr)
            raise
    print("PASS — профиль " + profile + ", вызовов инструментов: " + str(calls))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project",required=True,type=Path)
    parser.add_argument("--profile",choices=["base","E1","E2","E3","E4","E5"],default="base")
    args = parser.parse_args()
    try:
        asyncio.run(check(args.project.resolve(),args.profile))
    except Exception as exc:
        print("FAIL — " + str(exc),file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()

