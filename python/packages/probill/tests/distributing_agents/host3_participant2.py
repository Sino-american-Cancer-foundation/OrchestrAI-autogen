# host3_participant2.py
import asyncio
import logging
from autogen_core import TopicId, AgentId, TypeSubscription
from autogen_core import try_get_known_serializers_for_type
# Remove OpenAIChatCompletionClient import if AppConfig provides it
# from autogen_ext.models.openai import OpenAIChatCompletionClient 
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from chat_agents import GroupChatParticipantAgent
from messages import GroupChatMessage, GroupChatReply
from probill.utils import AppConfig # Assuming AppConfig is accessible

async def main():
    # Load configuration (similar to host1_manager.py)
    # Ensure config.yaml exists and is configured correctly
    config = AppConfig.load("./config.yaml") 
    print("Loaded configuration:", config.host.address, flush=True)

    # Connect to the central host server using config if available, otherwise keep localhost
    # host_address = config.host.address if hasattr(config, 'host') and hasattr(config.host, 'address') else "localhost:50051"
    host_address = "localhost:50051" # Keep localhost for now, adjust if needed based on config structure
    runtime = GrpcWorkerAgentRuntime(host_address=host_address)
    
    # Register message serializers
    for msg_type in [GroupChatMessage, GroupChatReply]:
        runtime.add_message_serializer(try_get_known_serializers_for_type(msg_type))
    
    # Start the runtime
    await runtime.start()
    model_client = OpenAIChatCompletionClient(**config.client_config)
    
    # Define the factory function for the participant agent
    agent_name = "ML Engineer"
    agent_specialty = "machine learning"
    agent_factory_id = "ml_engineer"
    agent_instance_id_type = "ml-participant"

    def participant_factory():
        agent = GroupChatParticipantAgent(description=f"{agent_name} - {agent_specialty} specialist")
        agent.name = agent_name
        agent.specialty = agent_specialty
        agent.model_client = model_client
        # Initialize other attributes if needed, e.g., agent.conversation_history = []
        return agent

    # Register the participant agent using the factory
    await runtime.register_factory(agent_factory_id, participant_factory)
    
    # Subscribe to the group chat topic using TypeSubscription
    group_chat_topic = TopicId("group-chat", "team-discussion")
    participant_agent_id = AgentId(agent_factory_id, agent_instance_id_type)
    
    # Use TypeSubscription, id is generated automatically
    await runtime.add_subscription(TypeSubscription(
        topic_type=group_chat_topic.type,
        agent_type=participant_agent_id.type
    ))
    
    print(f"{agent_name} agent is running and ready to participate")
    
    # Keep the runtime running
    await runtime.stop_when_signal()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())