import asyncio
from probill.tools.mcp import create_mcp_client, SseServerParams
from typing import Dict, Any

async def main() -> None:
    """Example of using the NCCN MCP client."""
    
    # Configure the connection to the NCCN MCP server
    server_params = SseServerParams(
        base_url="http://localhost:9003",
        timeout=30.0
    )

    # Create an MCP client
    async with await create_mcp_client(server_params) as client:
        # List available tools
        tools = await client.list_tools()
        print("Available tools:", [tool.name for tool in tools])

        # List available resources
        resources = await client.list_resources()
        print("Available resources:", resources.resource_ids)

        # Get the decision tree resource
        decision_tree = await client.get_resource("decision_tree")
        print("Decision tree metadata:", decision_tree.metadata)

        # List available prompts
        prompts = await client.list_prompts()
        print("Available prompts:", prompts.prompt_ids)

        # Get the evaluation prompt
        evaluation_prompt = await client.get_prompt("evaluation")
        print("Evaluation prompt template:", evaluation_prompt.template)

        # Example evaluation request
        evaluation_request = {
            "patient_id": "PATIENT123",
            "start_page_id": "BREAST-1",
            "neo4j_uri": "neo4j://localhost:7687",
            "neo4j_user": "neo4j",
            "neo4j_password": "password"
        }

        # Get the evaluate_patient_guidelines tool
        tools = await client.get_tools()
        evaluate_tool = next(t for t in tools if t.name == "evaluate_patient_guidelines")

        # Evaluate patient
        result = await evaluate_tool.invoke(**evaluation_request)
        print("\nEvaluation result:", result)

        # Check evaluation state
        if result["status"] == "success":
            eval_id = result["evaluation"]["evaluation_id"]
            state_tool = next(t for t in tools if t.name == "get_evaluation_state")
            state = await state_tool.invoke(evaluation_id=eval_id)
            print("\nEvaluation state:", state)


if __name__ == "__main__":
    asyncio.run(main())