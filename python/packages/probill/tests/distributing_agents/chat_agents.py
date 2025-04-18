# chat_agents.py
from autogen_core import RoutedAgent, MessageContext, AgentId, message_handler
from messages import GroupChatMessage, GroupChatReply, ManagerSelectionRequest, ManagerSelectionResponse

class GroupChatParticipantAgent(RoutedAgent):
    """Agent that participates in group chat discussions"""
    
    def __init__(self, name: str, model_client, specialty: str):
        super().__init__(f"{name} - {specialty} specialist")
        self.model_client = model_client
        self.name = name
        self.specialty = specialty
        self.conversation_history = []
        
    @message_handler
    async def handle_group_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        # Record the incoming message
        self.conversation_history.append(message)
        
        # Only respond if we're mentioned or it's our turn (determined by manager)
        if self.name.lower() in message.content.lower() or message.sender_name == "GroupChatManager":
            # Generate a response using the model
            system_msg = f"You are {self.name}, an expert in {self.specialty}. Answer questions related to your expertise."
            prompt = f"Conversation history:\n" + "\n".join([f"{msg.sender_name}: {msg.content}" for msg in self.conversation_history[-5:]])
            prompt += f"\nRespond as {self.name}:"
            
            response = await self.model_client.generate(system_msg, prompt)
            
            # Publish the response back to the group chat
            await self.publish_message(
                GroupChatMessage(content=response, sender_name=self.name), 
                ctx.topic_id
            )

class GroupChatManagerAgent(RoutedAgent):
    """Agent that manages the flow of conversation in group chat"""
    
    def __init__(self, model_client, participants: list[str]):
        super().__init__("Group Chat Manager")
        self.model_client = model_client
        self.participants = participants
        self.conversation_history = []
        self.turn_count = 0
        
    @message_handler
    async def handle_group_message(self, message: GroupChatMessage, ctx: MessageContext) -> None:
        # Record the message
        self.conversation_history.append(message)
        self.turn_count += 1
        
        # Use the model to determine who should speak next
        if self.turn_count < 20:  # Limit conversation length
            system_msg = "You are a group chat manager. Select the next person who should speak."
            participant_list = ", ".join(self.participants)
            prompt = f"Conversation history:\n" + "\n".join([f"{msg.sender_name}: {msg.content}" for msg in self.conversation_history[-5:]])
            prompt += f"\nBased on the conversation, who should speak next? Choose from: {participant_list}"
            
            next_speaker = await self.model_client.generate(system_msg, prompt)
            
            # Clean up the response to get just the name
            for participant in self.participants:
                if participant.lower() in next_speaker.lower():
                    next_speaker = participant
                    break
            
            # Direct the conversation to the next speaker
            await self.publish_message(
                GroupChatMessage(
                    content=f"I'd like to hear from {next_speaker} on this topic.", 
                    sender_name="GroupChatManager"
                ), 
                ctx.topic_id
            )
        else:
            # End the conversation after maximum turns
            await self.publish_message(
                GroupChatMessage(
                    content="Thank you all for the discussion. Let's conclude here.", 
                    sender_name="GroupChatManager"
                ), 
                ctx.topic_id
            )