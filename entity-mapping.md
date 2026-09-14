# Ontology の設定と受入契約

この定義は実装用の設定表です。[build_ontology.py](build_ontology.py) が対応する公開 Ontology REST 定義を生成します。2026-09-14時点で Lakehouse と5テーブル、Data agent の draft と指示文は作成済みですが、Ontology の登録は `FeatureNotAvailable` で未完了です。UI操作は[公式 OneLake チュートリアル](https://learn.microsoft.com/fabric/iq/ontology/tutorial-1-create-ontology?pivots=onelake)に基づきます。

## データの意味

- 基準日時: `2026-09-14T00:00:00Z`。評価期間: 同時刻以上、`2026-09-21T00:00:00Z` 未満。
- すべて架空、単一倉庫 `W01`。注文と仕入先の実際の配送イベントはありません。
- `status = Open` を未完了とします。`shortageQty = max(requestedQty - allocatedQty, 0)` は引当不足であり、配送遅延の確定予測ではありません。
- 商品ごとの未完了明細の引当数合計は、在庫を超えません。各注文に在庫全量を重複して割り当てる計算はしません。
- O008 は評価期間外です。参照データには含めますが、この期間の不足照会には含めません。
- 初期不足は O001/OL001/P01/S01:4、O002/OL003/P03/S03:2、O003/OL005/P05/S02:3。補充後は O001 だけ解消します。

## エンティティとプロパティ

Lakehouse 内の `dbo` にある管理テーブルを使用します。下表のキーはすべて非null・一意な文字列です。同じ名前のプロパティは各エンティティで同じ型を使用します。`Products` は GQL 予約語 `PRODUCT` を避ける名前です。

| Entity type | Source table | Entity type key | 行数 |
| --- | --- | --- | --- |
| Suppliers | fiq_suppliers | supplierId | 3 |
| Products | fiq_products | productId | 12 |
| InventoryItems | fiq_inventory | inventoryId | 12 |
| SalesOrders | fiq_orders | orderId | 8 |
| OrderLines | fiq_order_lines | orderLineId | 16 |

プロパティ名と列名は同一にし、自動検出される型を保持します。列ごとの Spark 型は [fabric_load.py](fabric_load.py) の `SCHEMAS` が正です。

| エンティティ | 文字列 | 整数 (BIGINT) | UTC日時 (TIMESTAMP) |
| --- | --- | --- | --- |
| Suppliers | supplierId, supplierName | leadTimeDays | なし |
| Products | productId, supplierId, productName | なし | なし |
| InventoryItems | inventoryId, productId, warehouseId | onHandQty | snapshotAt |
| SalesOrders | orderId, status | なし | dueAt |
| OrderLines | orderLineId, orderId, productId | requestedQty, allocatedQty, shortageQty | なし |

`snapshotAt` と `dueAt` も今回は静的プロパティです。時系列バインディングは作成しません。Lakehouse の Delta 列マッピングは `none` とし、外部テーブル・Decimal・特殊文字の列名は使用しません。

## 関係型

1行が1関係を表せるテーブルを関係のデータソースにします。Matched source/target はエンティティのキー値と対応する列を指定します。

| Relationship | Source entity | Target entity | 関係の元テーブル | Matched source column | Matched target column | 期待辺数 |
| --- | --- | --- | --- | --- | --- | --- |
| supplies | Suppliers | Products | fiq_products | supplierId | productId | 12 |
| has_inventory | Products | InventoryItems | fiq_inventory | productId | inventoryId | 12 |
| contains_line | SalesOrders | OrderLines | fiq_order_lines | orderId | orderLineId | 16 |
| refers_to | OrderLines | Products | fiq_order_lines | orderLineId | productId | 16 |

例えば S01 から `supplies` で商品に進み、`refers_to` を逆方向にたどって明細、`contains_line` を逆方向にたどって注文を特定します。グラフの矢印と逆に探索する場合にも向きを取り違えないでください。重複キーで辺を増殖させないことを確認します。

## ポータルでの設定

1. 専用ワークスペースの `+ New item > Ontology (preview)` で `ont_supplychain_poc` を作成します。
2. `Add entity type` で上表の5種類を作成します。
3. 各エンティティの `... > Bind data > Add data binding > Lakehouse table` から対応する `fiq_` テーブルを選びます。
4. プロパティ名を元の列名と一致させ、`Define entity type key` で上表のキーを指定して保存します。主キーがプロパティとソース列の両方に正しくマッピングされていることを確認します。
5. 各 source entity の `Configure` から関係型を追加し、上表の target entity、関係の元テーブル、Matched列を指定して保存します。
6. Entity type details のグラフで行数・辺・値を確認します。P01 に関連する在庫は W01/16、O001 の不足は4です。仕入先 S01 に関連する期間内の不足注文は O001 だけです。
7. 初期バインディング完了後とデータ更新後に、関連 Graph の更新状態を確認します。外部データの変更には `... > Schedule > Refresh now` が必要です。初回のフル更新後にのみ受入照会を始めます。

## Data agent の設定

1. 同じワークスペースで `+ New item > Data agent` から `da_supplychain_poc` を作成します。
2. `Add a data source` で **ont_supplychain_poc** を選択します。生の Lakehouse を代わりに選択しないでください。
3. Explorer に Ontology と5エンティティが表示されることを確認します。
4. `Agent instructions` に次の業務定義を設定します。正解のIDや件数は指示文に入れず、実データから取得させます。

```text
You answer questions about a fictional single-warehouse allocation dataset.
Use the connected ontology as the data source. Respond in the user's language.
The entity types are Suppliers, Products, InventoryItems, SalesOrders and OrderLines.
The relationships are supplies, has_inventory, contains_line and refers_to.
The fixed demo reference time is 2026-09-14T00:00:00Z.
Unless the user specifies another period, state explicitly that the demo window is
2026-09-14T00:00:00Z inclusive to 2026-09-21T00:00:00Z exclusive (UTC).
An open order has status equal to Open. Allocation shortage is
max(requestedQty - allocatedQty, 0) per order line, exposed as shortageQty.
An order has an allocation shortage if any of its lines has shortageQty > 0.
Do not confuse insufficient allocation with proof of delivery delay.
Do not reuse the entire on-hand stock separately for every order.
For shortage questions include orderId, orderLineId, productId, supplierId and shortageQty.
Use the defined relationships to resolve supplier identity from each product.
If an ID does not exist, report it as not found. Never substitute a similar ID.
If the question needs delivery events or root causes, explain that those data are absent.
Clarify ambiguous terms when they cannot be resolved from these definitions.
Support group by in GQL
```

最後の行は[公式チュートリアル](https://learn.microsoft.com/fabric/iq/ontology/tutorial-4-create-data-agent#provide-agent-instructions)にある集計問題への対処です。モデルの回答を正解扱いせず、必ず固定正解と比較します。

5. [acceptance-cases.json](tests/acceptance-cases.json) の質問を実行します。初期化直後のエラーと、ソースや権限の設定不備を区別してください。
6. 共有が必要なら、検証対象者だけを対象に製品の公開・共有手順を実施し、Data agent と各ソースの権限を確認します。別利用者の実セッションで肯定・否定の権限試験を行います。権限をプロンプトだけで表現しないでください。

## 完了条件

ローカル unittest、Fabric Notebook の読み戻し・Spark SQL照合、Ontology の関係照合、Data agent の3回反復、更新/リセット、実IDによる権限試験を区別して記録します。未実施の層があれば、その層まで動作確認済みとは報告しません。