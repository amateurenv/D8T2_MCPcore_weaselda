"""Порядок работы с заказом. Правила в domain, SQL в storage."""
from . import domain
from .errors import success, failure

def create_order(storage, user_id, product_id, size, quantity):
    'Реализуйте по правилам Лавки и согласованным методам.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("create_order")

def cancel_order(storage, order_id):
    'Реализуйте по правилам Лавки и согласованным методам.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("cancel_order")

def confirm_pickup(storage, order_id):
    'Реализуйте по правилам Лавки и согласованным методам.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("confirm_pickup")

