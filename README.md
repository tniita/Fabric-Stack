# Fabric IQ: 受注・在庫の検証

架空データを Lakehouse に投入し、Ontology の関係をたどって引当不足の注文を調べる PoC です。Ontology を直接ソースにする Fabric data agent の設定・受入手順も含みます。単なる Lakehouse チャットを Ontology 検証の代替にはしません。

## 現在の状態

2026-09-14 時点。**West US 2 に最小 F2、専用ワークスペース、Lakehouse、Notebook、Data agent 本体を作成済みです。Spark の初期化・補充・リセット検証は成功しています。Ontology 作成は `FeatureNotAvailable` で未完了です。** [実行記録](.azure/infrastructure-plan.json)に承認内容、実ID、申請結果を保存しています。

[Fabric ワークスペースを開く](https://app.fabric.microsoft.com/groups/0d4ec7a2-c186-4a72-a06a-0aaa84b80256/list?ctid=063f059a-02d2-469a-bc31-fd396b37de0c)。停止中は容量の再開が必要です。

**終了時に F2 は `Paused`、プロビジョニング状態は `Succeeded` を Azure ARM API で確認しました。** データは初期状態で保持しています。停止後も保存料や停止時の使用量清算は発生し得ます。Ontology の作成・グラフ検証・Data agent の応答検証が残っており、Fabric IQ 全体の構築完了とは扱いません。

| 確認対象 | 結果 |
| --- | --- |
| データ生成・整合性・SQL照合・Notebook保護 | Ontology生成を含むローカル unittest 15件が合格 |
| Notebook | 生成元との一致、Pythonセルの構文とデータ生成を検証 |
| Spark / Delta / Fabric Notebook 実行 | 初期化、補充、リセットの3実行が `Completed`。各実行で5テーブルの読み戻しと固定正解への Spark SQL照合が成功 |
| 対象サブスクリプション | ME-M365CPI68039016-takuyaniita-1 (`675efb15-0e43-4df6-a16f-e0bae2e46738`) |
| 対象テナント | `063f059a-02d2-469a-bc31-fd396b37de0c` |
| 対象利用者 | `admin@M365CPI68039016.onmicrosoft.com` |
| Fabric API の利用資格 | 初回サインイン前の `UserNotLicensed` は解消。容量・ワークスペースの GET に成功 |
| Fabric 容量 | `fabiqylpmyb2qquiu6` / `F2` / West US 2 / ID `c5de6969-63bc-4b37-8f54-b669849379a6`。終了時 `Paused` を確認 |
| ワークスペース | `fabric-iq-poc` / `0d4ec7a2-c186-4a72-a06a-0aaa84b80256` |
| Lakehouse | `lh_supplychain_poc` / `2cc69c7b-ae39-448b-8bcb-aee06251b4cc` / 既定スキーマ `dbo` |
| Notebook | `01_seed_lakehouse` / `50aab273-c656-4459-b93c-9999adf7e3eb` |
| Data agent 本体 | `da_supplychain_poc` / `69ca22ee-968c-4648-9494-d8f93758e28c`。業務指示文の完全一致を実定義で確認。draft、Ontology未接続、未公開、未呼び出し |
| テナント設定 | `OntologyPreview` は専用グループのみ有効。Azure OpenAI Copilot と Fabric Copilot 容量指定は既存の有効設定を維持。クロスジオ処理・保存は変更なし |
| Azure what-if | West US 2 への変更後は既存リソースグループ `NoChange`、F2 容量 `Create`。コンパイル成功 |
| 実デプロイ | `fabric-iq-f2-westus2-20260914` は `Succeeded`。リソースグループのメタデータ所在地は East US 2 のまま |
| East US 2 クォータ | 使用0 CU / 上限0 CU。ポータルで2 CUを申請したが `Unsuccessful`、サポート問い合わせが必要 |
| West US 2 | 作成前に使用0 CU / 上限512 CUを確認。利用者の明示承認後にF2を作成 |
| 専用セキュリティグループ | `fabric-iq-poc-users-20260914` (`7cf0940b-4719-4deb-bd87-db356674cbe3`) を作成。対象管理者1名のみ所属を確認 |
| Ontology 設定変更 | グループ指定で保存成功。管理 API でも対象グループIDのみ有効と確認。作成APIは反映待ちの可能性があるため再確認が必要 |
| IaC セキュリティスキャン | Checkov 未導入のため未実施 |
| Ontology / Graph / Data agent応答 / 別利用者による権限試験 | 未実施。Lakehouse 接続だけで代用していない |

East US 2 のクォータ不足と2 CU申請の不成功後、West US 2 への変更を明示的に承認してもらい構築しました。今回、CLI の既定認証先変更、試用開始、容量拡大、全社設定変更は行っていません。ワークスペースには今回の処理では作成していない `Stocks_Eventhouse`、`Stocks_Database`、`Stocks_Eventstream` も確認できたため、変更・削除していません。容量の一時停止はそれらを含む同じ容量の全ワークロードへ影響します。

## F2 構成と再開

[Bicep](infra/main.bicep)は、専用リソースグループ `rg-fabric-iq-poc-20260914` と F2 容量だけを扱います。容量所在地 `location=westus2` とグループ所在地 `resourceGroupLocation=eastus2` は分離済みです。[容量モジュール](infra/modules/capacity.bicep)は SKU を `F2` に固定し、容量管理者を対象利用者だけに設定します。Bicep はワークスペース、テナント設定、セキュリティグループ、Fabric 項目、自動停止を作成・設定しません。

- 容量は承認済みの `westus2` に配置しました。Data agent の公式条件に基づき、米国配置では既存のクロスジオ設定を変更しません。
- [公式料金](https://azure.microsoft.com/en-us/pricing/details/microsoft-fabric/)の F2 基準表示は USD 262.80/月 (730時間換算で USD 0.36/時)。地域別料金 API は該当メーターを返さなかったため、契約価格として確認済みの見積もりではありません。OneLake 保存料、停止時に清算される繰越・未平準化使用分は別です。
- 予約購入・容量拡大・容量超過課金・Spark の追加従量課金は有効化していません。完了または障害時に専用容量を一時停止する方針は承認済みです。自動停止や課金のハード上限は未設定です。
- Ontology 作成は、管理者1名だけを含む専用セキュリティグループに限定して有効化済みです。再開時は同じグループを再利用し、所属メンバーを再検証します。全社有効化や既存セキュリティ設定の無効化は行いません。
- 秘密情報やセキュリティポリシー除外タグは含めていません。Fabric 容量は計算リソースであり、2023-11-01 の容量 ARM 定義には汎用的な `publicNetworkAccess`、マネージド ID、TLS 設定はありません。これらを未対応のプロパティとして追加せず、データアクセスは Fabric の Entra ID とワークスペース権限で制御します。Private Link が構成済みという意味ではありません。

実行済みの非作成検証です。Bicep の新バージョン通知は出ましたが、両コマンドは終了コード0でした。Azure の事前検証は、実際の容量割当や Fabric IQ の動作成功を保証しません。

```bash
az bicep build --file infra/main.bicep --outfile /tmp/fabric-iq-main-20260914.json
az deployment sub validate --name fabric-iq-preflight-20260914 \
	--location eastus2 --template-file infra/main.bicep \
	--subscription 675efb15-0e43-4df6-a16f-e0bae2e46738
```

再開時は対象テナントと利用者を再照合し、既存容量を再開します。容量やワークスペースを新規作成し直す必要はありません。Ontology の設定反映後に作成可否を再確認します。保存成功直後の `FeatureNotAvailable` だけでは恒久的な非対応と断定できません。15分以上後も利用できなければ、設定範囲・利用者のグループ所属・容量側の委任設定・製品提供状態を管理者に確認します。全社有効化で回避しません。

再試行前は、Azure validate だけでなく Fabric の `/subscriptions/{subscriptionId}/providers/Microsoft.Fabric/locations/{region}/usages?api-version=2023-11-01` で空きCUを確認します。今回 validate と what-if が成功しても実作成時にクォータを拒否されたためです。what-if でこのPoC以外のリソース変更がないことを確認後にデプロイし、以下の Lakehouse、Ontology、Data agent の手順へ進みます。実行後は専用容量の状態を再取得して停止を確認し、保存データを削除せずに残します。稼働継続を希望する場合は停止方針を明示的に変更してください。

## ローカルで確認

Python 3.10 以上、追加パッケージ不要です。今回の実行環境は Python 3.12.3 です。

```bash
python3 -m unittest discover -s tests -v
python3 build_notebook.py --check
```

生成元を変更した場合は `python3 build_notebook.py` で再生成します。[Notebook](notebooks/01_seed_lakehouse.ipynb) は [seed.py](seed.py)、[fabric_load.py](fabric_load.py)、[検証SQL](tests/validation.sql)、[正解データ](tests/acceptance-cases.json) を組み込んだ自己完結ファイルです。外部URLからコードをダウンロードしたり、資格情報を埋め込んだりしません。

ローカル SQL テストは SQLite 上で同じ照会を実行します。Spark SQL の実行成功を保証するものではありません。Notebook の最終セルは Spark SQL の結果を同じ固定正解と比較します。

## 構築前の必須確認

1. [Fabric ポータル](https://app.fabric.microsoft.com/)で構築先のテナントとアカウントを確認してください。VS Code、`az`、`azd`、Fabric ポータルの選択先を同一と推定しないでください。
2. 全工程には **有料 F2 以上、または Fabric 有効の Power BI Premium P1 以上**を用意します。これは Data agent の公式最低条件で、必要な性能を保証する SKU 推奨ではありません。PPU/試用だけで全工程が利用可能とは扱いません。まず既存容量の所有者に使用許可を確認してください。
3. 対象リージョンで必要機能を利用できること、容量とワークスペースへのアクセス、項目作成・データ読み取り権限を確認します。容量割当は管理者に依頼します。
4. 管理者に `Enable Ontology item (preview)` と Data agent の必須設定を確認します。Data agent の設定ページには Copilot/Azure OpenAI の利用、Fabric Copilot 容量の指定、条件付きのクロスジオ処理・保存設定があります。EU データ境界・米国の外の容量ではクロスジオ条件が適用されるため、対象地域と組織ポリシーに照らして承認を得ます。全社設定を一律に有効化しません。
5. Ontology のバインディング元には、**管理された Lakehouse テーブル**を使います。OneLake security が有効な Lakehouse は現在未対応です。既存のセキュリティ機能を無効化せず、許可された専用検証環境を用意します。許可できなければここで停止します。
6. 有料容量が新たに必要なら、SKU・リージョン・利用時間上限・保存費・終了日について承認を得てから作成します。Notebook や Ontology 定義生成スクリプトは容量を作成・拡張しません。容量の作成は別の Bicep デプロイです。

現行 CLI 認証での読み取り専用の再確認コマンドです。出力の `continuationUri` がある場合は続きも確認します。トークンの表示や `--debug` は不要です。

```bash
az account show --query '{tenantId:tenantId,subscription:name}' --output json
az rest --method get --url https://api.fabric.microsoft.com/v1/capacities --resource https://api.fabric.microsoft.com
az rest --method get --url https://api.fabric.microsoft.com/v1/workspaces --resource https://api.fabric.microsoft.com
```

## 1. Lakehouse に投入

以下は新規環境向けの手順です。今回の環境は REST API で作成・容量割当・Notebook 実行まで実施済みです。既存環境で `WRITE_MODE=create` を再実行すると既存テーブル保護で停止するため、再実行時は承認のうえ `replace-demo` を使用します。

1. 承認済み容量に専用ワークスペース `fabric-iq-poc` を作成します。同名が存在する場合は既存項目を再利用せず、一意な名前を使います。
2. 同じワークスペースに、**スキーマ有効**の Lakehouse `lh_supplychain_poc` を作成します。この Notebook は `dbo` スキーマを使用します。名前は英数字とアンダースコアにします。
3. [01_seed_lakehouse.ipynb](notebooks/01_seed_lakehouse.ipynb) を Fabric にインポートし、上記 Lakehouse を既定としてアタッチします。変更後は Spark セッションを再起動します。
4. パラメーターセルの `WORKSPACE_ID` と `LAKEHOUSE_ID` に、ポータルで確認した対象の実IDを設定します。実行時コンテキストと両方が一致しない場合は停止します。
5. 対象と費用を確認した後にだけ `CONFIRMATION = "WRITE_DEMO_TABLES"` を設定します。初回は `SCENARIO = "initial"`、`WRITE_MODE = "create"` のまま実行します。
6. 5テーブルの読み戻し検証と最後の SQL 照合が成功することを確認します。SQL の不足明細は下表の3件です。

| 注文 | 明細 | 商品 | 仕入先 | 不足数 |
| --- | --- | --- | --- | --- |
| O001 | OL001 | P01 | S01 | 4 |
| O002 | OL003 | P03 | S03 | 2 |
| O003 | OL005 | P05 | S02 | 3 |

5テーブルは `fiq_suppliers` (3件)、`fiq_products` (12件)、`fiq_inventory` (12件)、`fiq_orders` (8件)、`fiq_order_lines` (16件) です。決定的な固定データなので乱数 seed や実行日には依存しません。

## 2. Ontology と Data agent

[entity-mapping.md](entity-mapping.md) に、エンティティ定義、4関係のキー対応、画面での設定手順、Data agent の指示文をまとめています。

[build_ontology.py](build_ontology.py) はこの定義を公開 Ontology REST API の20パーツに変換します。クラウド呼び出しはせず、次のコマンドは作成要求 JSON を標準出力へ出すだけです。

```bash
python3 build_ontology.py \
	--workspace-id 0d4ec7a2-c186-4a72-a06a-0aaa84b80256 \
	--lakehouse-id 2cc69c7b-ae39-448b-8bcb-aee06251b4cc
```

同じワークスペースに `ont_supplychain_poc` を作成し、5テーブルをバインドします。Ontology に関連する Graph 項目は製品が提供する仕組みで作成されるため、作成後にそのIDと関係も記録します。別の任意 Graph を手作業で追加する必要はありません。

グラフで関係とデータを検証してから、`da_supplychain_poc` を作成し **Ontology 自体**をデータソースに指定します。外部 UI、Foundry、AI Search、Operations agent、Activator は追加しません。

## 3. 補充とリセット

1. 他の書き込み実行とグラフの更新スケジュールを止め、読み取り利用者にも検証中であることを知らせます。
2. `SCENARIO = "replenished"`、`WRITE_MODE = "replace-demo"` に変更して Notebook を再実行します。P01 の在庫が16から20、OL001 の引当が6から10になり、不足注文は O002・O003 の2件になります。
3. ワークスペースで Ontology に関連する Graph の `... > Schedule > Refresh now` を実行します。これは全量更新で容量を消費します。完了後に Ontology の値を確認します。
4. 新しい会話で Data agent の質問を再実行し、更新後の正解と照合します。
5. `SCENARIO = "initial"`、`WRITE_MODE = "replace-demo"` で初期状態に戻し、同じグラフ更新・照合を実施します。

**5テーブルをまたぐ更新は非原子的です。** 途中で失敗した場合、グラフの更新や利用を再開しないでください。原因を確認し、同じシナリオを `replace-demo` で再実行して全件の読み戻し検証が成功した後に再開します。未作成のテーブルは作成し、既存テーブルは所有属性 `fabric_iq_poc=supplychain_v1` を確認します。属性なし・外部テーブル・列マッピング有効・スキーマ不一致の場合は停止し、自動で削除・修復しません。

## 4. 実機での受入

[acceptance-cases.json](tests/acceptance-cases.json) の質問を各シナリオで3回、独立した会話で実行します。最初は英語の固定質問で比較し、必要に応じて日本語でも同じ正解に一致するか確認します。

- 「2026年9月14日以上、21日未満のUTC期間で、引当不足のある未完了注文と商品・仕入先・不足数を示して」
- 「同じ期間で、仕入先 S01 の商品に引当不足がある注文は？」
- 「仕入先 S01 が遅延した根本原因は？」については、原因データがないと答えること。

単純にノードや文章が表示されるだけでは合格にしません。ID・数値・関係を SQL と突合します。定量ケースに加えて、不明なID、期間が曖昧な質問、データにない原因も確認します。

`liveRuns` は現在空です。実測時は `caseId`、`scenario`、`repeat`、`identityAlias`、`executedAt`、`graphRefreshAt`、`result`、`actual`、`sourceEvidence` を記録します。証跡には製品が表示する生成クエリ・ソース・実行結果を使い、トークンや個人情報は残しません。別利用者による試験には実際に別の検証用IDを使います。プロンプトで権限のない利用者を演じることは権限試験になりません。試験用IDがない場合は未実施として残します。

## 費用と終了

今回の確認では F2 容量・ワークスペース・Lakehouse・Notebook・Data agent 本体を作成し、Spark を3回実行しました。容量の稼働・OneLake保存は課金対象です。実請求額は未取得です。Graph 全量更新や Data agent の応答検証は未実施です。対応SKUの最低条件と実際の性能・費用は別です。終了時の容量状態は実行記録に保存します。

共有容量を無断で停止しません。専用有料容量の停止は所有者の承認後に行い、停止後の保存費も確認します。削除する場合は Notebook、Data agent、Ontology、関連 Graph、Lakehouse と保存データ、ワークスペースを一覧にして承認を得てから、このPoCで作成したものだけを削除します。

## 確認した公式情報

確認日: 2026-09-14。Ontology は preview です。本文取得ツールが失敗したページは Microsoft Learn の `?accept=text/markdown` による直接取得で確認しました。

- [Ontology チュートリアルと前提条件](https://learn.microsoft.com/fabric/iq/ontology/tutorial-0-introduction)
- [OneLake からの Ontology 作成](https://learn.microsoft.com/fabric/iq/ontology/tutorial-1-create-ontology?pivots=onelake)
- [バインディングの制約](https://learn.microsoft.com/fabric/iq/ontology/how-to-bind-data#limitations-and-troubleshooting)
- [Ontology のテナント設定](https://learn.microsoft.com/fabric/iq/ontology/overview-tenant-settings)
- [Data agent の容量・データソース要件](https://learn.microsoft.com/fabric/data-science/concept-data-agent#prerequisites)
- [Data agent のテナント設定](https://learn.microsoft.com/fabric/data-science/data-agent-tenant-settings)
- [Ontology を Data agent に接続](https://learn.microsoft.com/fabric/iq/ontology/tutorial-4-create-data-agent)
- [グラフの更新](https://learn.microsoft.com/fabric/iq/ontology/how-to-view-entity-type-details#refresh-the-graph-model)
- [NotebookUtils の実行コンテキスト](https://learn.microsoft.com/fabric/data-engineering/notebookutils/notebookutils-runtime)
- [Spark による Lakehouse への書き込み](https://learn.microsoft.com/fabric/data-engineering/lakehouse-notebook-load-data#load-data-with-an-apache-spark-api)