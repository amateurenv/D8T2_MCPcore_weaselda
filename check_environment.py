"""Проверка готовности АРМа. Ничего не устанавливает и не меняет."""
import importlib
import importlib.metadata
import sqlite3
import sys

print("Команда: python3")
print("Интерпретатор:", sys.executable)
print("Версия:", sys.version.split()[0])
errors = []
for name in ("fastmcp", "pytest"):
    try:
        importlib.import_module(name)
        print(name + ":", importlib.metadata.version(name))
    except Exception as exc:
        errors.append(name + ": " + str(exc))
try:
    from fastmcp import Client, FastMCP
    from fastmcp.client.transports import StdioTransport
    from pydantic import Field
    with sqlite3.connect(":memory:") as con:
        con.execute("SELECT 1").fetchone()
except Exception as exc:
    errors.append("Проверка возможностей: " + str(exc))
if errors:
    print("Окружение не готово. Передайте стаффу этот вывод:")
    print("\n".join(errors))
    raise SystemExit(1)
print("Необходимые модули доступны. Запустите python3 client.py demo.")

