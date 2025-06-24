from typing import List

from autogen_core import (
    RoutedAgent, 
    MessageContext, 
    DefaultTopicId,
    message_handler,
    CancellationToken
)
from autogen_core.models import UserMessage, AssistantMessage, LLMMessage, SystemMessage, ChatCompletionClient
from rich.console import Console
from rich.markdown import Markdown

from facilities.core.types import GroupChatMessage, RequestToSpeak, UIAgentConfig, ConversationFinished
from facilities.core.publishing import publish_message_to_ui


class OrchestratorAgent(RoutedAgent):
    """Orchestrator that manages conversation flow - follows GroupChatManager pattern."""
    
    def __init__(
        self,
        model_client: ChatCompletionClient,
        participant_topic_types: List[str],
        participant_descriptions: List[str],
        ui_config: UIAgentConfig,
        max_rounds: int = 10,
    ) -> None:
        super().__init__("Orchestrator Agent")
        self._model_client = model_client
        self._num_rounds = 0
        self._participant_topic_types = participant_topic_types
        self._chat_history: List[LLMMessage] = []
        self._max_rounds = max_rounds
        self.console = Console()
        self._participant_descriptions = participant_descriptions
        self._previous_participant_topic_type: str | None = None
        self._ui_config = ui_config
        self._plan_created = False  # Track if plan has been created
    
    @message_handler
    async def handle_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        """Handle group chat messages - orchestrate next speaker"""
        assert isinstance(message.body, UserMessage)

        self._chat_history.append(message.body)
        
        # If this is the first user message and no plan created yet, create a complete plan first
        if not self._plan_created and isinstance(message.body, UserMessage) and message.body.source == "User":
            await self._create_complete_plan(ctx.cancellation_token)
            self._plan_created = True

        # Format message history
        messages: List[str] = []
        for msg in self._chat_history:
            if isinstance(msg.content, str):
                messages.append(f"{msg.source}: {msg.content}")
            elif isinstance(msg.content, list):
                messages.append(f"{msg.source}: {', '.join(msg.content)}")
        history = "\n".join(messages)
        
        # Format roles (allow all participants, including previous speaker)
        roles = "\n".join(
            [
                f"{topic_type}: {description}".strip()
                for topic_type, description in zip(
                    self._participant_topic_types, self._participant_descriptions, strict=True
                )
            ]
        )
        participants = str(self._participant_topic_types)

        # Check if we have a plan in the history
        plan_messages = [msg for msg in self._chat_history if isinstance(msg, AssistantMessage) and msg.source == "Orchestrator" and msg.content.startswith("Plan:")]
        plan_context = ""
        if plan_messages:
            plan_context = f"\nExecuting plan: {plan_messages[0].content[5:]}\n"  # Remove "Plan: " prefix

        selector_prompt = f"""You are orchestrating a conversation between agents:
{roles}.
{plan_context}
Read the following conversation. Then select the next agent from {participants} to respond based on the plan above and conversation flow. Only return the agent name.

{history}

CRITICAL INSTRUCTIONS:
1. You MUST strictly follow the established plan. Do not deviate from the plan unless absolutely necessary.
2. Before selecting the next agent, check which steps of the plan have been completed and which are still pending.
3. Select the agent that should handle the NEXT step in the plan that hasn't been completed yet.
4. Only return "FINISH: [REASON]" when ALL steps in the plan have been successfully completed AND the user's original request has been fully addressed.
5. Do NOT return "FINISH" just because agents have spoken - ensure the plan's objectives are actually accomplished.
6. If you exceed {self._max_rounds} rounds limit, return "FINISH: [REASON]" but only as a last resort.

Read the above conversation. If the plan is complete, return "FINISH: [REASON]". Otherwise, select the next agent from {participants} to respond. Follow the established plan strictly and ensure all plan steps are completed before finishing.
"""
        system_message = SystemMessage(content=selector_prompt)
        
        completion = await self._model_client.create([system_message], cancellation_token=ctx.cancellation_token)

        assert isinstance(
            completion.content, str
        ), f"Completion content must be a string, but is: {type(completion.content)}"

        # Log what the LLM decided
        await publish_message_to_ui(
            runtime=self, 
            source="Orchestrator_Debug", 
            user_message=f"🤖 **LLM DECISION**: '{completion.content.strip()}'", 
            ui_config=self._ui_config
        )

        if completion.content.upper().startswith("FINISH"):
            # Parse the finish reason from "FINISH: reason" format
            if ":" in completion.content:
                finish_msg = completion.content.split(":", 1)[1].strip()
            else:
                finish_msg = "The conversation has concluded. Thank you for using our assistant system!"
            
            manager_message = f"\n{'-'*80}\n Orchestrator ({id(self)}): {finish_msg}"
            await publish_message_to_ui(
                runtime=self, source=self.id.type, user_message=finish_msg, ui_config=self._ui_config
            )
            self.console.print(Markdown(manager_message))
            
            # Notify all participant agents that the conversation is finished
            conversation_finished_msg = ConversationFinished(reason=finish_msg)
            for participant_topic_type in self._participant_topic_types:
                await self.publish_message(conversation_finished_msg, DefaultTopicId(type=participant_topic_type))
            
            return

        selected_topic_type: str
        for topic_type in self._participant_topic_types:
            if topic_type.lower() in completion.content.lower():
                selected_topic_type = topic_type
                self._previous_participant_topic_type = selected_topic_type
                
                self.console.print(
                    Markdown(f"\n{'-'*80}\n Orchestrator ({id(self)}): Asking `{selected_topic_type}` to speak")
                )
                await self.publish_message(RequestToSpeak(), DefaultTopicId(type=selected_topic_type))
                return
        raise ValueError(f"Invalid agent selected: {completion.content}")
    
    async def _create_complete_plan(self, cancellation_token: CancellationToken) -> None:
        """Create a complete plan for handling the user's request."""
        # Get the user's request
        user_request = self._chat_history[-1].content
        
        # Format available agents and their capabilities
        agent_capabilities = "\n".join(
            [
                f"- {topic_type}: {description}"
                for topic_type, description in zip(
                    self._participant_topic_types, self._participant_descriptions, strict=True
                )
            ]
        )
        
        planning_prompt = f"""You are an orchestrator for a assistant system. Create a concise step by step plan to address the user's request.

Available agents:
{agent_capabilities}

User request: {user_request}

Create a structured plan with numbered steps. Each step should:
1. Specify which agent should handle it
2. Clearly define what that agent needs to accomplish
3. Be specific about the expected outcome

Format your plan as:
Step 1: [Specific task/objective]
Step 2: [Specific task/objective]
Step 3: [Specific task/objective] (if needed)

Provide a brief plan with clear steps. Be concise and focus only on the essential actions needed.
"""
        
        system_message = SystemMessage(content=planning_prompt)
        completion = await self._model_client.create([system_message], cancellation_token=cancellation_token)
        
        assert isinstance(completion.content, str)
        
        # Present the plan to the user
        plan_message = f"**Plan**: {completion.content}\n\n---\n\nExecuting plan..."
        
        await publish_message_to_ui(
            runtime=self, 
            source="Orchestrator", 
            user_message=plan_message, 
            ui_config=self._ui_config
        )
        
        self.console.print(Markdown(f"\n{'-'*80}\n**Orchestrator Plan**: {completion.content}"))
        
        # Store the plan in chat history for future reference
        self._chat_history.append(AssistantMessage(content=f"Plan: {completion.content}", source="Orchestrator")) 