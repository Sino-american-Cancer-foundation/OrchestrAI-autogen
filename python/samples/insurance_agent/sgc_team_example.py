import asyncio
import os

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.insurance import InsuranceAgent
from autogen_ext.agents.web_surfer import MultimodalWebSurfer

async def main():
    # Create debug directory if it doesn't exist
    debug_dir = "./debug"
    os.makedirs(debug_dir, exist_ok=True)
    
    # Initialize the model client
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
    )
    
    # Create the three agents
    planning_agent = AssistantAgent(
        "PlanningAgent",
        model_client=model_client,
        description="A planning coordinator that breaks down complex tasks and delegates to specialized agents.",
        system_message="""You are a planning coordinator.
        Your team consists of:
        - InsuranceAgent: Specialized in insurance verification and processing claims
        - WebSurferAgent: Specialized in web browsing and information retrieval
        
        Break down complex tasks, assign appropriate subtasks to each agent based on their specialties.
        Always begin by analyzing the task and creating a clear plan.
        Use "TERMINATE" when the overall task is complete.
        """
    )
    
    insurance_agent = InsuranceAgent(
        "InsuranceAgent",
        model_client=model_client,
        sse_url="http://localhost:8000/sse",
        description="An agent specializing in insurance verification and eligibility checking.",
    )
    
    web_surfer_agent = MultimodalWebSurfer(
        "WebSurferAgent", 
        model_client=model_client,
        description="An agent that can browse the web to retrieve information.",
        headless=False,
        debug_dir=debug_dir,
    )
    
    selector_prompt = """Select the most appropriate agent to perform the current task step.
    
    {roles}
    
    Current conversation context:
    {history}
    
    Based on the above conversation, select one agent from {participants} to perform the next step.
    The PlanningAgent should start the task and provide coordination.
    The InsuranceAgent should handle tasks related to insurance verification and claims.
    The WebSurferAgent should handle tasks that require web browsing and information retrieval.
    
    Select only one agent based on the current needs of the task.
    """
    
    # Create the SelectorGroupChat
    team = SelectorGroupChat(
        [planning_agent, insurance_agent, web_surfer_agent],
        model_client=model_client,
        termination_condition=TextMentionTermination("TERMINATE"),
        selector_prompt=selector_prompt,
        allow_repeated_speaker=False,
    )
    
    try:
        # Example task
        task = """Investigate insurance options for a small business and compare available plans online. 
        The business has 15 employees and needs both health and liability coverage."""
        
        # Run the team
        await Console(team.run_stream(task=task))
    finally:
        # Make sure to close the web browser
        await web_surfer_agent.close()

if __name__ == "__main__":
    asyncio.run(main())