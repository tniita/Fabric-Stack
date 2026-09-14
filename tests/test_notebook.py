import base64
import json
import unittest
from unittest.mock import MagicMock

from build_notebook import build_notebook
from build_ontology import build_ontology, ENTITIES, RELATIONSHIPS
from fabric_load import check_existing_table, target_namespace, write_fabric_tables
from seed import build_tables


WORKSPACE = "11111111-1111-4111-8111-111111111111"
LAKEHOUSE = "22222222-2222-4222-8222-222222222222"
CONTEXT = {"currentWorkspaceId": WORKSPACE, "defaultLakehouseWorkspaceId": WORKSPACE,
           "defaultLakehouseId": LAKEHOUSE, "defaultLakehouseName": "lh_supplychain_poc"}


class NotebookTests(unittest.TestCase):
    def test_ontology_definition_matches_source_keys(self):
        payload = build_ontology(WORKSPACE, LAKEHOUSE)
        self.assertEqual(payload, build_ontology(WORKSPACE, LAKEHOUSE))
        parts = {part["path"]: json.loads(base64.b64decode(part["payload"]))
                 for part in payload["definition"]["parts"]}
        self.assertEqual(len(parts), 20)
        entities = {part["name"]: part for path, part in parts.items()
                    if path.startswith("EntityTypes/") and path.endswith("/definition.json")}
        self.assertEqual(set(entities), set(ENTITIES))
        identifiers = [prop["id"] for entity in entities.values() for prop in entity["properties"]]
        self.assertEqual(len(identifiers), len(set(identifiers)))
        for path, part in parts.items():
            if "/DataBindings/" in path:
                binding = part["dataBindingConfiguration"]
                source = binding["sourceTableProperties"]
                self.assertEqual((source["workspaceId"], source["itemId"], source["sourceSchema"]),
                                 (WORKSPACE, LAKEHOUSE, "dbo"))
                self.assertEqual(binding["dataBindingType"], "NonTimeSeries")
        for name, source, target, table, source_column, target_column in RELATIONSHIPS:
            relation_path, relation = next((path, part) for path, part in parts.items()
                                           if path.startswith("RelationshipTypes/")
                                           and part.get("name") == name)
            self.assertEqual(relation["source"]["entityTypeId"], entities[source]["id"])
            self.assertEqual(relation["target"]["entityTypeId"], entities[target]["id"])
            prefix = relation_path.removesuffix("definition.json") + "Contextualizations/"
            context = next(part for path, part in parts.items() if path.startswith(prefix))
            self.assertEqual(context["dataBindingTable"]["sourceTableName"], f"fiq_{table}")
            for direction, entity_name, column in (("source", source, source_column),
                                                    ("target", target, target_column)):
                key = entities[entity_name]["entityIdParts"][0]
                self.assertEqual(context[f"{direction}KeyRefBindings"],
                                 [{"sourceColumnName": column, "targetPropertyId": key}])
        with self.assertRaises(ValueError):
            build_ontology("not-a-uuid", LAKEHOUSE)

    def test_target_is_explicit(self):
        self.assertEqual(target_namespace(CONTEXT, WORKSPACE, LAKEHOUSE, "WRITE_DEMO_TABLES"),
                         "`lh_supplychain_poc`.`dbo`")
        for workspace, lakehouse, confirmation in (
            ("", LAKEHOUSE, "WRITE_DEMO_TABLES"),
            (WORKSPACE, WORKSPACE, "WRITE_DEMO_TABLES"),
            (WORKSPACE, LAKEHOUSE, ""),
        ):
            with self.subTest(workspace=workspace, lakehouse=lakehouse, confirmation=confirmation):
                with self.assertRaises(ValueError):
                    target_namespace(CONTEXT, workspace, lakehouse, confirmation)

    def test_cross_workspace_and_unsafe_name_rejected(self):
        for change in ({"defaultLakehouseWorkspaceId": LAKEHOUSE},
                       {"currentWorkspaceId": LAKEHOUSE},
                       {"defaultLakehouseName": "demo`; DROP TABLE data"}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    target_namespace(CONTEXT | change, WORKSPACE, LAKEHOUSE, "WRITE_DEMO_TABLES")

    def test_replacement_requires_managed_owned_delta(self):
        owned = {"format": "delta", "properties": {"fabric_iq_poc": "supplychain_v1"}}
        check_existing_table("replace-demo", "MANAGED", owned)
        for mode, table_type, detail in (
            ("create", "MANAGED", owned),
            ("replace-demo", "EXTERNAL", owned),
            ("replace-demo", "MANAGED", {"format": "delta", "properties": {}}),
            ("replace-demo", "MANAGED", {"format": "parquet", "properties": owned["properties"]}),
            ("replace-demo", "MANAGED", {"format": "delta", "properties": {
                **owned["properties"], "delta.columnMapping.mode": "name"}}),
        ):
            with self.subTest(mode=mode, table_type=table_type, detail=detail):
                with self.assertRaises(ValueError):
                    check_existing_table(mode, table_type, detail)

    def test_unconfirmed_execution_never_calls_spark(self):
        spark = MagicMock()
        with self.assertRaises(ValueError):
            write_fabric_tables(spark, build_tables(), CONTEXT, WORKSPACE, LAKEHOUSE)
        self.assertEqual(spark.mock_calls, [])

    def test_all_targets_checked_before_writing(self):
        spark = MagicMock()
        spark.catalog.tableExists.side_effect = [False, True]
        with self.assertRaises(ValueError):
            write_fabric_tables(spark, build_tables(), CONTEXT, WORKSPACE, LAKEHOUSE, "WRITE_DEMO_TABLES")
        self.assertFalse(any("CREATE TABLE" in str(call) for call in spark.sql.call_args_list))
        spark.createDataFrame.return_value.write.mode.assert_not_called()

    def test_generated_cells_compile_and_preview_without_fabric(self):
        notebook = build_notebook()
        namespace = {}
        for cell in notebook["cells"]:
            if cell["cell_type"] != "code":
                continue
            code = compile("".join(cell["source"]), f"cell:{cell['id']}", "exec")
            if cell["id"] in ("parameters", "dataset", "writer", "preview"):
                exec(code, namespace)
        self.assertEqual(len(namespace["tables"]["orders"]), 8)
        self.assertEqual(namespace["CONFIRMATION"], "")
        self.assertEqual(namespace["WORKSPACE_ID"], "")
        self.assertEqual(namespace["WRITE_MODE"], "create")


if __name__ == "__main__":
    unittest.main()