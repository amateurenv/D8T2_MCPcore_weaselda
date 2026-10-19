"""Правила без SQL и MCP. Вся арифметика в целых коинах."""

def calculate_total(price, quantity):
    'Стоимость заказа.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("calculate_total")

def purchase_error(product, size, quantity, balance, already_owned, total):
    'Код отказа или None. Пользователь и товар уже найдены.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("purchase_error")

def refund_amount(total_price):
    'Сумма возврата по сохранённой стоимости заказа.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("refund_amount")

def can_cancel(order):
    'Можно ли отменить найденный заказ.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("can_cancel")

def can_pickup(order):
    'Можно ли выдать найденный заказ.'
    # TODO: закончите эту функцию.
    raise NotImplementedError("can_pickup")

