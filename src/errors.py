"""Ответы Лавки. Ошибки протокола обрабатывает FastMCP."""
def success(data):
    return {"ok": True, "data": data}

def failure(code, message):
    return {"ok": False, "error": {"code": code, "message": message}}

