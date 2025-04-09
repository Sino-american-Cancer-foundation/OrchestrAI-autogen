import asyncio
import os

from typing import Sequence
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.ui import Console

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.agents.mcp_sse_agent import McpSseAgent

TEAM_GOAL = """
Goal:
Accurately verify insurance eligibility and, if confirmed, update the patient's verified information into the EMR/EHR system.

Process:
Insurance eligibility verification should follow this structured two-phase workflow:

Phase 1 (Initial Verification via Portals):
1.1: Log into the provided insurance portal(s) using given credentials and analyze screenshots or portal data to determine preliminary eligibility.
1.2: If the patient is clearly eligible (without IPA involvement), update the EMR/EHR system accordingly.
1.3: If eligibility is unclear or IPA involvement exists, proceed to Phase 2.

Phase 2 (Verification via Phone Call):
2.1: If IPA involvement is detected, you should contact IPA directly for verification. Otherwise, contact the insurance provider by phone to verify eligibility.
2.2: If the patient is eligible, update the EMR/EHR system with the verified information.
2.3: If the patient is not eligible, inform the user clearly that the patient is not eligible for the requested service.

Note: Always evaluate what information you currently have, identify what additional steps and tools are necessary, or confirm if the verification task is already complete."""

async def main():
    # Initialize the model client
    model_client = OpenAIChatCompletionClient(
        model="gpt-4o",
    )
    
    # 1. Planning Agent with team goal
    planning_agent = AssistantAgent(
        "PlanningAgent",
        model_client=model_client,
        description="A planning coordinator that decomposes tasks and assigns them to specialized agents.",
        system_message= TEAM_GOAL +"""
        
        You are a planning coordinator for a team of specialized agents.
        Your team consists of:
        - WebNavigationAgent: Specializes in web portal login and navigation
        - ImageAnalysisAgent: Specializes in analyzing insurance portal screenshots
        - HealthcareTaskAgent: Specializes in making verification calls and running EMR/EHR system tasks
        
        Break down complex tasks into clear subtasks and assign each to the most appropriate agent.
        Always begin by analyzing the task and creating a structured plan.
        Monitor progress and coordinate between agents when subtasks are interdependent.
        
        Ensure all team actions adhere to healthcare privacy standards and proper handling of sensitive information.
        
        Use "TERMINATE" when the overall task is complete, and only use it when the task is done.
        """
    )
    
    # 2. Web Navigation Agent (McpSseAgent) - Portal Login (Server 3)
    web_navigation_agent = McpSseAgent(
        "WebNavigationAgent",
        model_client=model_client,
        sse_url="http://10.101.22.241:8088/sse",  # Using port from sub_server_3.py
        description="An agent specialized in insurance portal logins and navigation.",
        system_message="""You are a web navigation specialist agent.
        Your primary capabilities include:
        - Logging into insurance portals with provided credentials
        - Capturing screenshots of member information pages
        
        When assigned a web navigation task:
        1. Always confirm the portal URL before proceeding
        2. Handle login credentials securely
        3. Return screenshot IDs that can be used by the ImageAnalysisAgent
        
        You have access to the following tool:
        - portal-login: Log into an insurance portal and capture a screenshot of the member information
        """
    )
    
    # 3. Image Analysis Agent (McpSseAgent) - Image Analysis (Server 2)
    image_analysis_agent = McpSseAgent(
        "ImageAnalysisAgent", 
        model_client=model_client,
        sse_url="http://10.101.22.241:8080/sse",  # Using port from sub_server_2.py
        description="An agent specialized in analyzing insurance portal screenshots.",
        system_message="""You are an image analysis specialist agent.
        Your primary capabilities include:
        - Analyzing insurance portal screenshots to determine eligibility for specific service dates
        - Extracting information about insurance providers, eligibility status, and contact information
        
        When assigned an image analysis task:
        1. Always request the screenshot ID (from WebNavigationAgent) and service date
        2. Provide detailed extracted information from the portal screenshot
        
        You have access to the following tool:
        - analyze-image: Analyze an insurance portal screenshot to determine eligibility for a specific service date
        """
    )
    
    # 4. Healthcare Task Agent (McpSseAgent) - Call and EMR tasks (Server 1)
    healthcare_task_agent = McpSseAgent(
        "HealthcareTaskAgent",
        model_client=model_client,
        sse_url="http://10.101.22.241:8087/sse",  # Using port from sub_server_1.py
        description="An agent specialized in making verification calls and handling EMR/EHR system tasks.",
        system_message="""You are a healthcare task specialist agent.
        Your primary capabilities include:
        - Making outgoing calls to verify insurance eligibility with providers
        - Retrieving results from completed verification calls
        - Running tasks on virtual machines to fill out information in EMR/EHR systems
        
        When assigned a healthcare task:
        1. For call verification tasks, use make-call first, then check results with get-call-results
        2. For EMR/EHR data entry, use run-vm-task with the appropriate task name
        3. Document all actions taken for audit purposes
        
        You have access to the following tools:
        - make-call: Initiate an outgoing call to verify insurance eligibility
        - get-call-results: Retrieve results from a completed verification call
        - run-vm-task: Run a background task on a VM to fill out information in EMR/EHR systems
        """
    )
    
    # Define selector prompt
    selector_prompt = """Select the most appropriate agent to perform the current task step.
    
    {roles}
    
    Current conversation context:
    {history}
    
    Based on the above conversation, select one agent from {participants} to perform the next step.
    
    Guidelines for agent selection:
    - PlanningAgent should start the task and provide coordination between other agents.
    - WebNavigationAgent should handle tasks involving insurance portal logins.
    - ImageAnalysisAgent should handle tasks involving analyzing insurance portal screenshots.
    - HealthcareTaskAgent should handle tasks involving verification calls and EMR/EHR system tasks.
    
    Always select the agent with the most relevant expertise for the immediate next step in the task.
    Select only one agent.
    """


    def selector_func(messages: Sequence[AgentEvent | ChatMessage]) -> str | None:
        if messages[-1].source != planning_agent.name:
            return planning_agent.name
        return None
    
    # Create the SelectorGroupChat
    team = SelectorGroupChat(
        [planning_agent, web_navigation_agent, image_analysis_agent, healthcare_task_agent],
        model_client=model_client,
        termination_condition=TextMentionTermination("TERMINATE"),
        selector_prompt=selector_prompt,
        allow_repeated_speaker=False,
        selector_func=selector_func,
    )

    try:
        # Example task
        task = """
        Do your job with the following information:
        1. Portal website url: https://www.brmsprovidergateway.com/provideronline/search.aspx
        2. Member ID (username): E01257465
        3. Date of Birth (password): 08/03/1988
        4. Patient Name: Liza Silina
        5. Service Date: 2024-01-15
        """
        task = "Hi, read all the MCP tool you can have and terminate the process."
        
        # Run the team and display the conversation
        await Console(team.run_stream(task=task))

        component_representation = team.dump_component()

        # Convert the component model to a dictionary first
        component_dict = component_representation.model_dump()

        import json
        json_output = json.dumps(component_dict, indent=2)
        with open("custom_team_config.json", "w") as f:
            f.write(json_output)
        # Print or save as needed
        print(json_output)
        
    except Exception as e:
        print(f"Error: {str(e)}")
        
    finally:
        # Perform any necessary cleanup
        print("Task completed or terminated")

# Run the team
if __name__ == "__main__":
    asyncio.run(main())