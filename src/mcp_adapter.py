"""Готовая регистрация инструментов. Описания читаются из контракта."""
import json
from typing import Annotated
from pathlib import Path
from pydantic import Field
from fastmcp import FastMCP
from . import read_handlers as read
from . import order_handlers as orders

Text = Annotated[str, Field(strict=True, min_length=1)]
Quantity = Annotated[int, Field(strict=True, ge=1)]

def build_mcp_server(storage):
    root = Path(__file__).resolve().parents[1]
    contracts = json.loads((root / "contracts/tools_schemas.json").read_text(encoding="utf-8"))
    specs = {tool["name"]: tool for tool in contracts["tools"]}
    server = FastMCP("school21-lavka")

    def register(fn):
        spec = specs[fn.__name__]
        server.tool(fn, description=spec["description"], output_schema=spec["outputSchema"])
        return fn

    @register
    async def get_product(product_id: Text) -> dict:
        return read.get_product(storage, product_id)

    @register
    async def list_products() -> dict:
        return read.list_products(storage)

    @register
    async def get_coin_balance(user_id: Text) -> dict:
        return read.get_coin_balance(storage, user_id)

    @register
    async def get_order_status(order_id: Text) -> dict:
        return read.get_order_status(storage, order_id)

    @register
    async def create_order(user_id: Text, product_id: Text, size: Text, quantity: Quantity = 1) -> dict:
        return orders.create_order(storage, user_id, product_id, size, quantity)

    @register
    async def cancel_order(order_id: Text) -> dict:
        return orders.cancel_order(storage, order_id)

    @register
    async def confirm_pickup(order_id: Text) -> dict:
        return orders.confirm_pickup(storage, order_id)

    return server

