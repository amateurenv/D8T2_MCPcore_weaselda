"""Инструменты чтения. Здесь нет SQL."""
from .errors import success, failure

def get_product(storage, product_id):
    product = storage.get_product(product_id)
    if product is None:
        return failure("PRODUCT_NOT_FOUND", "Товар не найден")
    return success(product)

def list_products(storage):
    products = storage.list_products()
    return success({"products": products})

def get_coin_balance(storage, user_id):
    user = storage.get_user(user_id)
    if user is None:
        return failure("USER_NOT_FOUND", "Пользователь не найден")
    return success({"user_id": user["id"], "balance": user["coins"]})

def get_order_status(storage, order_id):
    order = storage.get_order(order_id)
    if order is None:
        return failure("ORDER_NOT_FOUND", "Заказ не найден")
    return success({"order_id": order["id"], "status": order["status"]})

