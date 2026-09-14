from datetime import datetime
import re
from uuid import UUID


OWNER_PROPERTY = "fabric_iq_poc"
OWNER_VALUE = "supplychain_v1"
SCHEMAS = {
    "suppliers": "supplierId STRING, supplierName STRING, leadTimeDays BIGINT",
    "products": "productId STRING, supplierId STRING, productName STRING",
    "inventory": "inventoryId STRING, productId STRING, warehouseId STRING, onHandQty BIGINT, snapshotAt TIMESTAMP",
    "orders": "orderId STRING, status STRING, dueAt TIMESTAMP",
    "order_lines": "orderLineId STRING, orderId STRING, productId STRING, requestedQty BIGINT, allocatedQty BIGINT, shortageQty BIGINT",
}


def target_namespace(context, workspace_id, lakehouse_id, confirmation):
    if confirmation != "WRITE_DEMO_TABLES":
        raise ValueError("Set confirmation to WRITE_DEMO_TABLES after approving the target")
    expected_workspace = UUID(workspace_id)
    expected_lakehouse = UUID(lakehouse_id)
    for key in ("currentWorkspaceId", "defaultLakehouseWorkspaceId"):
        if UUID(context.get(key) or "") != expected_workspace:
            raise ValueError(f"Unexpected {key}")
    if UUID(context.get("defaultLakehouseId") or "") != expected_lakehouse:
        raise ValueError("Unexpected defaultLakehouseId")
    name = context.get("defaultLakehouseName") or ""
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
        raise ValueError("Use an alphanumeric demo lakehouse name without spaces")
    return f"`{name}`.`dbo`"


def check_existing_table(mode, table_type, detail):
    if mode == "create":
        raise ValueError("Target table already exists; create mode never overwrites")
    properties = detail.get("properties") or {}
    if (table_type != "MANAGED" or detail.get("format") != "delta"
            or properties.get(OWNER_PROPERTY) != OWNER_VALUE
            or properties.get("delta.columnMapping.mode", "none") != "none"):
        raise ValueError("Refusing to replace an unowned, external or incompatible table")


def write_fabric_tables(spark, tables, context, workspace_id, lakehouse_id,
                        confirmation="", mode="create"):
    if mode not in ("create", "replace-demo"):
        raise ValueError("mode must be create or replace-demo")
    if set(tables) != set(SCHEMAS):
        raise ValueError("Only the five demo tables can be written")
    namespace = target_namespace(context, workspace_id, lakehouse_id, confirmation)
    spark.sql(f"SHOW TABLES IN {namespace}").collect()
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    frames = {}
    existing = set()
    for table_name, schema in SCHEMAS.items():
        target = f"{namespace}.`fiq_{table_name}`"
        rows = [dict(row) for row in tables[table_name]]
        for row in rows:
            for field in ("dueAt", "snapshotAt"):
                if field in row:
                    row[field] = datetime.fromisoformat(row[field].replace("Z", "+00:00"))
        frame = spark.createDataFrame(rows, schema=schema)
        frames[table_name] = frame
        if spark.catalog.tableExists(target):
            table_type = spark.catalog.getTable(target).tableType
            detail = spark.sql(f"DESCRIBE DETAIL {target}").first().asDict()
            check_existing_table(mode, table_type, detail)
            if spark.table(target).schema.simpleString() != frame.schema.simpleString():
                raise ValueError(f"Schema mismatch: {target}")
            existing.add(table_name)
    for table_name, frame in frames.items():
        target = f"{namespace}.`fiq_{table_name}`"
        if table_name not in existing:
            spark.sql(
                f"CREATE TABLE {target} ({SCHEMAS[table_name]}) USING DELTA "
                f"TBLPROPERTIES ('{OWNER_PROPERTY}' = '{OWNER_VALUE}', "
                "'delta.columnMapping.mode' = 'none')"
            )
        frame.write.mode("overwrite").insertInto(target)
        loaded = spark.table(target)
        if (loaded.count() != frame.count()
                or loaded.exceptAll(frame).limit(1).count()
                or frame.exceptAll(loaded).limit(1).count()):
            raise RuntimeError(f"Read-back mismatch: {target}")
        loaded.createOrReplaceTempView(f"fiq_{table_name}")
    return namespace