# chat_agents.py
from autogen_core import RoutedAgent, MessageContext, AgentId, message_handler
from messages import GroupChatMessage, GroupChatReply, ManagerSelectionRequest, ManagerSelectionResponse

class GroupChatParticipantAgent(RoutedAgent):
    """Agent that participates in group chat discussions"""
    
    name: str
    specialty: str
    model_client: any
    conversation_history: list
    
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
    
    model_client: any
    participants: list[str]
    conversation_history: list
    turn_count: int
    
    def __init__(self, description: str = ""):
        super().__init__(description)
        self.conversation_history = []
        self.turn_count = 0
    
    @classmethod
    def create(cls, model_client, participants: list[str]):
        """Factory method to create a manager agent"""
        def factory():
            agent = cls("Group Chat Manager")
            agent.model_client = model_client
            agent.participants = participants
            return agent
        return factory
        
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