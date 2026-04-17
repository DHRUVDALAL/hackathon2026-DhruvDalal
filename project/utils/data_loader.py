import json
from pathlib import Path
from typing import Any, Dict, List


def _data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def _load_json(filename: str) -> Any:
    path = _data_dir() / filename
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_tickets() -> List[Dict[str, Any]]:
    return _load_json("tickets.json")


def load_orders() -> List[Dict[str, Any]]:
    return _load_json("orders.json")


def load_products() -> List[Dict[str, Any]]:
    return _load_json("products.json")


def load_knowledge() -> str:
    path = _data_dir() / "knowledge.md"
    return path.read_text(encoding="utf-8")


def load_customers() -> List[Dict[str, Any]]:
    return _load_json("customers.json")
