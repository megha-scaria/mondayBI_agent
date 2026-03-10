"""
Monday.com API client. Fetches data dynamically from Monday.com only — no local file paths.
"""
import requests
from typing import Any, Optional
from config import MONDAY_API_TOKEN, MONDAY_API_URL, WORK_ORDERS_BOARD_ID, DEALS_BOARD_ID


def _headers() -> dict:
    return {
        "Authorization": MONDAY_API_TOKEN,
        "Content-Type": "application/json",
        "API-Version": "2024-01",
    }


def _graphql(query: str, variables: Optional[dict] = None) -> dict:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables
    resp = requests.post(MONDAY_API_URL, json=payload, headers=_headers(), timeout=60)
    resp.raise_for_status()
    data = resp.json()
    if "errors" in data and data["errors"]:
        raise RuntimeError(f"Monday.com API error: {data['errors']}")
    return data.get("data", {})


def get_board_columns(board_id: str) -> list[dict]:
    """Fetch column id and title for a board."""
    q = """
    query getBoardColumns($boardId: ID!) {
      boards(ids: [$boardId]) {
        columns { id title type }
      }
    }
    """
    data = _graphql(q, {"boardId": str(board_id)})
    boards = data.get("boards") or []
    if not boards:
        return []
    return boards[0].get("columns") or []


def _parse_column_value(cv: dict) -> str:
    """Extract display text from a column value. Handles different column types."""
    if not cv:
        return ""
    text = cv.get("text")
    if text is not None and str(text).strip() != "":
        return str(text).strip()
    value = cv.get("value")
    if value is None:
        return ""
    try:
        import json
        obj = json.loads(value) if isinstance(value, str) else value
        if isinstance(obj, dict):
            return obj.get("text") or obj.get("label") or str(value)
        return str(obj)
    except Exception:
        return str(value)


def fetch_board_items(board_id: str, limit: int = 500) -> list[dict]:
    """
    Fetch all items from a board with their column values.
    Returns list of dicts: { "column_title": "value", ... }.
    No local paths — data comes only from Monday.com API.
    """
    col_map = {}  # id -> title
    for col in get_board_columns(board_id):
        col_map[col["id"]] = col.get("title") or col["id"]

    if not col_map:
        return []

    all_items = []
    cursor = None
    # First page: boards.items_page
    query_first = """
    query getBoardItemsFirst($boardId: ID!) {
      boards(ids: [$boardId]) {
        items_page(limit: 500) {
          cursor
          items {
            id
            name
            column_values {
              id
              text
              value
            }
          }
        }
      }
    }
    """
    # Next pages: root-level next_items_page
    query_next = """
    query getNextItems($cursor: String!) {
      next_items_page(cursor: $cursor, limit: 500) {
        cursor
        items {
          id
          name
          column_values {
            id
            text
            value
          }
        }
      }
    }
    """

    # First page
    data = _graphql(query_first, {"boardId": str(board_id)})
    boards = data.get("boards") or []
    if not boards:
        return all_items
    page = boards[0].get("items_page") or {}
    items = page.get("items") or []
    for it in items:
        row = {"_item_id": it.get("id"), "_item_name": it.get("name") or ""}
        for cv in it.get("column_values") or []:
            cid = cv.get("id")
            title = col_map.get(cid, cid)
            row[title] = _parse_column_value(cv)
        all_items.append(row)
    cursor = page.get("cursor")

    # Next pages
    while cursor and len(items) == limit:
        data = _graphql(query_next, {"cursor": cursor})
        page = data.get("next_items_page") or {}
        items = page.get("items") or []
        for it in items:
            row = {"_item_id": it.get("id"), "_item_name": it.get("name") or ""}
            for cv in it.get("column_values") or []:
                cid = cv.get("id")
                title = col_map.get(cid, cid)
                row[title] = _parse_column_value(cv)
            all_items.append(row)
        cursor = page.get("cursor")

    return all_items


def fetch_work_orders() -> list[dict]:
    """Fetch Work Orders board data from Monday.com (dynamic, no local paths)."""
    if not WORK_ORDERS_BOARD_ID:
        raise ValueError("MONDAY_WORK_ORDERS_BOARD_ID is not set. Create a Work Orders board and set the env var.")
    if not MONDAY_API_TOKEN:
        raise ValueError("MONDAY_API_TOKEN is not set.")
    return fetch_board_items(WORK_ORDERS_BOARD_ID)


def fetch_deals() -> list[dict]:
    """Fetch Deals board data from Monday.com (dynamic, no local paths)."""
    if not DEALS_BOARD_ID:
        raise ValueError("MONDAY_DEALS_BOARD_ID is not set. Create a Deals board and set the env var.")
    if not MONDAY_API_TOKEN:
        raise ValueError("MONDAY_API_TOKEN is not set.")
    return fetch_board_items(DEALS_BOARD_ID)
