"""Готовый пример. Собственные тесты добавьте в другие файлы."""
from pathlib import Path
from src.storage import Storage
from src.read_handlers import get_product

def test_ready_get_product(tmp_path):
    seed = Path(__file__).resolve().parents[1] / "data/seed.sql"
    storage = Storage(tmp_path / "test.db", seed)
    try:
        result = get_product(storage, "hoodie")
        assert result["ok"] is True
        assert result["data"]["price_coins"] == 500
        assert result["data"]["stock"]["M"] == 5
    finally:
        storage.close()

