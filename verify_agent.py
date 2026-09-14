import argparse
import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from uuid import UUID

from azure.identity import AzureCliCredential
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client


ROOT = Path(__file__).resolve().parent


async def ask(endpoint, credential, question):
    token = credential.get_token("https://api.fabric.microsoft.com/.default")
    async with asyncio.timeout(480):
        async with streamablehttp_client(
            endpoint, headers={"Authorization": f"Bearer {token.token}"},
            sse_read_timeout=timedelta(seconds=450),
        ) as (reader, writer, _):
            async with ClientSession(reader, writer, read_timeout_seconds=timedelta(seconds=450)) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                if len(tools) != 1 or set(tools[0].inputSchema.get("properties", {})) != {"userQuestion"}:
                    raise RuntimeError("Unexpected data agent tool contract")
                response = await session.call_tool(tools[0].name, {"userQuestion": question})
                answer = "\n".join(block.text for block in response.content if block.type == "text")
                if response.isError or not answer:
                    raise RuntimeError(f"Data agent failed: {answer}")
                return answer


async def verify(args):
    cases = json.loads((ROOT / "tests" / "acceptance-cases.json").read_text())
    endpoint = (f"https://api.fabric.microsoft.com/v1/mcp/workspaces/{args.workspace_id}"
                f"/dataagents/{args.agent_id}/agent")
    credential = AzureCliCredential(tenant_id=args.tenant_id)
    output = Path(args.output).expanduser()
    output = (output if output.is_absolute() else ROOT / output).resolve()
    if output.exists() and not args.resume:
        raise ValueError("Evidence file already exists; choose a new output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    selected = [case for case in cases["cases"] if case["id"] != "access"]
    if args.case:
        selected = [case for case in selected if case["id"] in args.case]
        if {case["id"] for case in selected} != set(args.case):
            raise ValueError("Unknown case or separate-identity case requested")
    report = {"scenario": args.scenario, "workspaceId": args.workspace_id,
              "dataAgentId": args.agent_id, "ontologyId": args.ontology_id,
              "graphRefreshId": args.graph_refresh_id, "liveRuns": [],
              "separateIdentityTest": "Not performed; requires a separate real authorized test identity"}
    if args.resume:
        previous = json.loads(output.read_text())
        for key in ("scenario", "workspaceId", "dataAgentId", "ontologyId", "graphRefreshId"):
            if previous.get(key) != report[key]:
                raise ValueError(f"Cannot resume evidence with a different {key}")
        report = previous
    completed = {(run["caseId"], run["repeat"]) for run in report["liveRuns"]}
    for case in selected:
        for repeat in range(1, args.repetitions + 1):
            if (case["id"], repeat) in completed:
                continue
            executed_at = datetime.now(timezone.utc).isoformat()
            answer = await ask(endpoint, credential, case["question"])
            report["liveRuns"].append({
                "caseId": case["id"], "scenario": args.scenario, "repeat": repeat,
                "identityAlias": "poc-admin", "executedAt": executed_at,
                "question": case["question"], "result": "pending-review", "actual": answer,
                "sourceEvidence": {
                    "transport": "Published Fabric data agent MCP",
                    "ontologyId": args.ontology_id, "graphRefreshId": args.graph_refresh_id,
                    "independentSession": True, "generatedQuery": "Not returned by MCP tool",
                },
            })
            output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
            print(json.dumps({"case": case["id"], "repeat": repeat, "answer": answer}, ensure_ascii=False), flush=True)
    credential.close()
    print(f"Recorded {len(report['liveRuns'])} independent responses in {output}; semantic review required")


def main():
    parser = argparse.ArgumentParser(description="Record independent live responses; requires an active paid Fabric capacity")
    parser.add_argument("--tenant-id", required=True, type=UUID)
    parser.add_argument("--workspace-id", required=True, type=UUID)
    parser.add_argument("--agent-id", required=True, type=UUID)
    parser.add_argument("--ontology-id", required=True, type=UUID)
    parser.add_argument("--graph-refresh-id", required=True, type=UUID)
    parser.add_argument("--scenario", required=True, choices=("initial", "replenished"))
    parser.add_argument("--repetitions", type=int, choices=(1, 2, 3), default=3)
    parser.add_argument("--case", action="append")
    parser.add_argument("--output", required=True)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    for name in ("tenant_id", "workspace_id", "agent_id", "ontology_id", "graph_refresh_id"):
        setattr(args, name, str(getattr(args, name)))
    asyncio.run(verify(args))


if __name__ == "__main__":
    main()