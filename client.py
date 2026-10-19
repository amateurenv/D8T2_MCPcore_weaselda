"""Готовый локальный клиент. Не использует модель и интернет."""
import argparse
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from fastmcp import Client
from fastmcp.client.transports import StdioTransport

ROOT = Path(__file__).resolve().parent

async def run(args):
    # Автоматические сценарии по умолчанию используют отдельную временную базу.
    # Ручные call сохраняют изменения в data/lavka.db между вызовами.
    with tempfile.TemporaryDirectory(prefix="lavka-demo-") as temp:
        db = args.db or (str(Path(temp) / "demo.db") if args.command in ("demo", "scenario")
                         else str(ROOT / "data/lavka.db"))
        transport = StdioTransport(
            command=sys.executable, args=["-m", "src.server", "--db", db], cwd=str(ROOT)
        )
        log = ROOT / "logs/client.jsonl"
        log.parent.mkdir(exist_ok=True)
        async with Client(transport, timeout=15) as client:
            async def call(name, arguments):
                result = await client.call_tool(name, arguments, raise_on_error=False)
                data = result.structured_content
                if data is None:
                    data = {"protocol_error": result.is_error,
                            "content": [getattr(x, "text", str(x)) for x in result.content]}
                event = {"time": datetime.now(timezone.utc).isoformat(),
                         "tool": name, "arguments": arguments, "result": data}
                with log.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(event, ensure_ascii=False) + "\n")
                print(name, json.dumps(arguments, ensure_ascii=False))
                print(json.dumps(data, ensure_ascii=False, indent=2))
                return data

            if args.command == "list":
                for tool in await client.list_tools():
                    print(tool.name, "—", tool.description)
            elif args.command == "call":
                arguments = json.loads(args.arguments)
                if not isinstance(arguments, dict):
                    raise ValueError("Аргументы должны быть JSON-объектом")
                await call(args.name, arguments)
            elif args.command == "demo":
                await call("get_product", {"product_id": "hoodie"})
                await call("get_product", {"product_id": "missing"})
            else:
                await call("get_coin_balance", {"user_id": "student_01"})
                await call("get_product", {"product_id": "bottle"})
                order = await call("create_order", {
                    "user_id": "student_01", "product_id": "bottle", "size": "one_size"})
                if order.get("ok"):
                    order_id = order["data"]["order_id"]
                    await call("get_order_status", {"order_id": order_id})
                    await call("cancel_order", {"order_id": order_id})
                    await call("cancel_order", {"order_id": order_id})
                await call("get_coin_balance", {"user_id": "student_01"})
                await call("get_product", {"product_id": "bottle"})
        print("Журнал:", log.relative_to(ROOT))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", help="Путь к базе; существующая база сохраняет состояние")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("demo", "scenario", "list"):
        sub.add_parser(name)
    call = sub.add_parser("call")
    call.add_argument("name")
    call.add_argument("arguments", nargs="?", default="{}")
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except Exception as exc:
        print("Не удалось выполнить запрос:", exc, file=sys.stderr)
        raise SystemExit(1)

if __name__ == "__main__":
    main()

