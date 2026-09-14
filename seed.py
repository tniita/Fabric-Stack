from collections import Counter
from datetime import datetime, timedelta, timezone


BASE_TIME = datetime(2026, 9, 14, tzinfo=timezone.utc)
WINDOW_START = "2026-09-14T00:00:00Z"
WINDOW_END = "2026-09-21T00:00:00Z"
TABLE_KEYS = {
    "suppliers": "supplierId",
    "products": "productId",
    "inventory": "inventoryId",
    "orders": "orderId",
    "order_lines": "orderLineId",
}


def build_tables(scenario="initial"):
    if scenario not in ("initial", "replenished"):
        raise ValueError("scenario must be initial or replenished")
    suppliers = [
        {"supplierId": f"S{number:02}", "supplierName": f"Demo Supplier {number}",
         "leadTimeDays": number + 1}
        for number in range(1, 4)
    ]
    products = [
        {"productId": f"P{number:02}", "supplierId": f"S{(number - 1) % 3 + 1:02}",
         "productName": f"Demo Product {number:02}"}
        for number in range(1, 13)
    ]
    orders = [
        {"orderId": f"O{number:03}", "status": "Open",
         "dueAt": (BASE_TIME + timedelta(days=number - 1, hours=12)).strftime("%Y-%m-%dT%H:%M:%SZ")}
        for number in range(1, 9)
    ]
    deficits = {1: 4, 3: 2, 5: 3}
    lines = [
        {"orderLineId": f"OL{number:03}", "orderId": f"O{(number - 1) // 2 + 1:03}",
         "productId": f"P{(number - 1) % 12 + 1:02}", "requestedQty": 10,
         "allocatedQty": 10 - deficits.get(number, 0)}
        for number in range(1, 17)
    ]
    allocated = Counter()
    for line in lines:
        allocated[line["productId"]] += line["allocatedQty"]
    inventory = [
        {"inventoryId": f"I{number:03}", "productId": product["productId"],
         "warehouseId": "W01", "onHandQty": allocated[product["productId"]],
         "snapshotAt": WINDOW_START}
        for number, product in enumerate(products, 1)
    ]
    if scenario == "replenished":
        lines[0]["allocatedQty"] += 4
        inventory[0]["onHandQty"] += 4
        inventory[0]["snapshotAt"] = "2026-09-14T01:00:00Z"
    for line in lines:
        line["shortageQty"] = max(line["requestedQty"] - line["allocatedQty"], 0)
    tables = dict(suppliers=suppliers, products=products, inventory=inventory,
                  orders=orders, order_lines=lines)
    validate_tables(tables)
    return tables


def validate_tables(tables):
    identifiers = {}
    for table_name, key in TABLE_KEYS.items():
        rows = tables[table_name]
        values = [row[key] for row in rows]
        if len(values) != len(set(values)) or any(not value for value in values):
            raise ValueError(f"Invalid or duplicate key: {table_name}.{key}")
        if any(value is None for row in rows for value in row.values()):
            raise ValueError(f"Null value in {table_name}")
        identifiers[table_name] = set(values)
    for source, column, target in (
        ("products", "supplierId", "suppliers"),
        ("inventory", "productId", "products"),
        ("order_lines", "productId", "products"),
        ("order_lines", "orderId", "orders"),
    ):
        if any(row[column] not in identifiers[target] for row in tables[source]):
            raise ValueError(f"Orphan reference: {source}.{column}")
    stock = {}
    for row in tables["inventory"]:
        quantity = row["onHandQty"]
        if type(quantity) is not int or quantity < 0 or row["productId"] in stock:
            raise ValueError("Invalid inventory quantity or duplicate product")
        stock[row["productId"]] = quantity
    allocated = Counter()
    open_orders = {row["orderId"] for row in tables["orders"] if row["status"] == "Open"}
    for line in tables["order_lines"]:
        quantities = [line[key] for key in ("requestedQty", "allocatedQty", "shortageQty")]
        if any(type(quantity) is not int or quantity < 0 for quantity in quantities):
            raise ValueError("Invalid order line quantity")
        if line["allocatedQty"] > line["requestedQty"]:
            raise ValueError("Allocation exceeds request")
        if line["shortageQty"] != line["requestedQty"] - line["allocatedQty"]:
            raise ValueError("Incorrect shortage quantity")
        if line["orderId"] in open_orders:
            allocated[line["productId"]] += line["allocatedQty"]
    if any(quantity > stock.get(product_id, 0) for product_id, quantity in allocated.items()):
        raise ValueError("Total allocations exceed stock")