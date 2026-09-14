import argparse
import base64
import json
from uuid import UUID, NAMESPACE_URL, uuid5

from fabric_load import SCHEMAS


ENTITIES = {
    "Suppliers": "suppliers",
    "Products": "products",
    "InventoryItems": "inventory",
    "SalesOrders": "orders",
    "OrderLines": "order_lines",
}
RELATIONSHIPS = [
    ("supplies", "Suppliers", "Products", "products", "supplierId", "productId"),
    ("has_inventory", "Products", "InventoryItems", "inventory", "productId", "inventoryId"),
    ("contains_line", "SalesOrders", "OrderLines", "order_lines", "orderId", "orderLineId"),
    ("refers_to", "OrderLines", "Products", "order_lines", "orderLineId", "productId"),
]
VALUE_TYPES = {"STRING": "String", "BIGINT": "BigInt", "TIMESTAMP": "DateTime"}


def build_ontology(workspace_id, lakehouse_id):
    workspace_id = str(UUID(workspace_id))
    lakehouse_id = str(UUID(lakehouse_id))
    logical_id = uuid5(NAMESPACE_URL, f"fabric-iq:{workspace_id}:{lakehouse_id}")
    parts = []

    def add_part(path, content):
        parts.append({
            "path": path,
            "payload": base64.b64encode(json.dumps(content).encode()).decode(),
            "payloadType": "InlineBase64",
        })

    def source_table(table):
        return {"sourceType": "LakehouseTable", "workspaceId": workspace_id,
                "itemId": lakehouse_id, "sourceSchema": "dbo",
                "sourceTableName": f"fiq_{table}"}

    add_part("definition.json", {})
    add_part(".platform", {
        "$schema": "https://developer.microsoft.com/json-schemas/fabric/gitIntegration/platformProperties/2.0.0/schema.json",
        "metadata": {"type": "Ontology", "displayName": "ont_supplychain_poc"},
        "config": {"version": "2.0", "logicalId": str(logical_id)},
    })
    entities = {}
    for entity_index, (name, table) in enumerate(ENTITIES.items(), start=1):
        entity_id = str(1000 + entity_index)
        properties = []
        for column_index, column in enumerate(SCHEMAS[table].split(","), start=1):
            column_name, column_type = column.split()
            properties.append({"id": str(int(entity_id) * 100 + column_index),
                               "name": column_name, "valueType": VALUE_TYPES[column_type]})
        entities[name] = {"id": entity_id, "key": properties[0]["id"]}
        add_part(f"EntityTypes/{entity_id}/definition.json", {
            "id": entity_id, "namespace": "usertypes", "name": name,
            "namespaceType": "Custom", "visibility": "Visible",
            "entityIdParts": [properties[0]["id"]],
            "displayNamePropertyId": properties[0]["id"], "properties": properties,
        })
        binding_id = str(uuid5(logical_id, f"binding:{name}"))
        add_part(f"EntityTypes/{entity_id}/DataBindings/{binding_id}.json", {
            "id": binding_id,
            "dataBindingConfiguration": {
                "dataBindingType": "NonTimeSeries",
                "sourceTableProperties": source_table(table),
                "propertyBindings": [{"sourceColumnName": prop["name"],
                                      "targetPropertyId": prop["id"]} for prop in properties],
            },
        })
    for relation_index, relation in enumerate(RELATIONSHIPS, start=1):
        name, source, target, table, source_column, target_column = relation
        relation_id = str(2000 + relation_index)
        add_part(f"RelationshipTypes/{relation_id}/definition.json", {
            "id": relation_id, "namespace": "usertypes", "namespaceType": "Custom",
            "name": name, "source": {"entityTypeId": entities[source]["id"]},
            "target": {"entityTypeId": entities[target]["id"]},
        })
        context_id = str(uuid5(logical_id, f"relationship:{name}"))
        add_part(f"RelationshipTypes/{relation_id}/Contextualizations/{context_id}.json", {
            "id": context_id, "dataBindingTable": source_table(table),
            "sourceKeyRefBindings": [{"sourceColumnName": source_column,
                                      "targetPropertyId": entities[source]["key"]}],
            "targetKeyRefBindings": [{"sourceColumnName": target_column,
                                      "targetPropertyId": entities[target]["key"]}],
        })
    return {"displayName": "ont_supplychain_poc",
            "description": "Synthetic supply-chain allocation ontology with five entities and four relationships.",
            "definition": {"parts": parts}}


def main():
    parser = argparse.ArgumentParser(description="Render the documented Fabric IQ ontology; does not call cloud APIs")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--lakehouse-id", required=True)
    args = parser.parse_args()
    print(json.dumps(build_ontology(args.workspace_id, args.lakehouse_id)))


if __name__ == "__main__":
    main()