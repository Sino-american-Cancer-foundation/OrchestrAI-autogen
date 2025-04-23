# chat_agents.py
from autogen_core import RoutedAgent, MessageContext, AgentId, message_handler
from autogen_core.models import ChatCompletionClient, UserMessage, SystemMessage
from autogen_agentchat.messages import TextMessage
from messages import GroupChatMessage, GroupChatReply, ManagerSelectionRequest, ManagerSelectionResponse
import logging

class GroupChatParticipantAgent(RoutedAgent):
    """Agent that participates in group chat discussions"""
    
    name: str
    specialty: str
    model_client: any
    conversation_history: list
    model_client: ChatCompletionClient
    
    def __init__(self, description: str = ""):
        super().__init__(description)
        self.conversation_history = []
    
    @classmethod
    def create(cls, name: str, model_client, specialty: str):
        """Factory method to create a participant agent"""
        def factory():
            agent = cls(f"{name} - {specialty} specialist")
            agent.name = name
            agent.specialty = specialty
            agent.model_client = model_client
            return agent
        return factory
        
    @message_handler
    async def handle_group_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        # Record the incoming message
        # Ensure message has sender_name attribute before appending
        if hasattr(message, 'sender_name'):
            self.conversation_history.append({"sender": message.sender_name, "content": message.content})
        else:
            # Handle cases where sender_name might be missing, e.g., initial message
            # Or adjust message structure if sender_name is named differently
            self.conversation_history.append({"sender": "Unknown", "content": message.content})


        # Only respond if we're mentioned or it's our turn (determined by manager)
        # Check if message.sender_name exists before comparing
        sender_name = getattr(message, 'sender_name', 'Unknown')
        if self.name.lower() in message.content.lower() or sender_name == "GroupChatManager":
            # Generate a response using the model
            system_msg = SystemMessage(content=f"You are {self.name}, an expert in {self.specialty}. Answer questions related to your expertise.")

            # Construct history using appropriate LLMMessage types
            history_msgs = []
            for msg_data in self.conversation_history[-5:]:
                # Assuming UserMessage for non-agent messages and AssistantMessage for agent messages might be needed
                # Adjust based on actual message sources and desired LLM interaction pattern
                history_msgs.append(UserMessage(content=msg_data["content"], source=msg_data["sender"]))

            # Combine system message and history for the prompt
            llm_messages = [system_msg] + history_msgs
            # Log that this agent is starting to generate answer
            logging.info(f"Agent {self.name} starting to generate answer")
            # Add the current request/instruction as the last UserMessage if appropriate
            # This depends on how the flow is designed. If the incoming message IS the prompt, it's already in history.
            # If a specific response instruction is needed, add it here.
            # Example: llm_messages.append(UserMessage(content=f"Respond as {self.name}:", source="SystemInstruction"))


            # Generate response using the model client's create method which expects a list of LLMMessages
            response_completion = await self.model_client.create(messages=llm_messages)
            response_content = response_completion.content if hasattr(response_completion, 'content') else str(response_completion) # Adapt based on actual response structure


            # Publish the response back to the group chat
            await self.publish_message(
                GroupChatMessage(content=response_content, source=self.name),
                ctx.topic_id
            )


class GroupChatManagerAgent(RoutedAgent):
    """Agent that manages the flow of conversation in group chat"""
    
    model_client: ChatCompletionClient
    participants: list[str]
    participant_descriptions: list[str]
    conversation_history: list
    turn_count: int
    previous_participant: str | None

    def __init__(self, description: str = "", participant_descriptions: list[str] = None):
        super().__init__(description)
        self.conversation_history = []
        self.turn_count = 0
        self.participant_descriptions = participant_descriptions or []
        self.previous_participant = None

    @classmethod
    def create(cls, model_client, participants: list[str], participant_descriptions: list[str]):
        """Factory method to create a manager agent"""
        def factory():
            agent = cls("Group Chat Manager", participant_descriptions)
            agent.model_client = model_client
            agent.participants = participants
            return agent
        return factory
        
    @message_handler
    async def handle_group_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        self.conversation_history.append(message)
        self.turn_count += 1

        # Format message history
        messages = [f"{msg.source}: {msg.content}" for msg in self.conversation_history]
        history = "\n".join(messages)
        # Format roles
        roles = "\n".join(
            f"{topic}: {desc}".strip()
            for topic, desc in zip(self.participants, self.participant_descriptions)
            if topic != self.previous_participant
        )
        participants_left = [topic for topic in self.participants if topic != self.previous_participant]
        participants_str = str(participants_left)

        selector_prompt = f"""You are in a role play game. The following roles are available:\n{roles}.\nRead the following conversation. Then select the next role from {participants_str} to play. Only return the role.\n\n{history}\n\nRead the above conversation. Then select the next role from {participants_str} to play. if you think it's enough talking, let writer be the last speaker to generate the final report. Once the final report generated, return 'FINISH'.\n"""
        system_message = SystemMessage(content=selector_prompt)
        completion = await self.model_client.create([system_message])
        next_role = completion.content.strip() if hasattr(completion, 'content') else completion["content"].strip()

        if next_role.upper() == "FINISH":
            finish_msg = "I think it's enough iterations on the story! Thanks for collaborating!"
            await self.publish_message(
                GroupChatMessage(content=finish_msg, source="GroupChatManager"),
                ctx.topic_id
            )
            return

        selected_participant = None
        for topic in self.participants:
            if topic.lower() in next_role.lower():
                selected_participant = topic
                self.previous_participant = selected_participant
                break
        if not selected_participant:
            # fallback: pick the first
            selected_participant = self.participants[0]
            self.previous_participant = selected_participant
        await self.publish_message(
            GroupChatMessage(
                content=f"I'd like to hear from {selected_participant} on this topic.",
                source="GroupChatManager"
            ),
            ctx.topic_id
        )