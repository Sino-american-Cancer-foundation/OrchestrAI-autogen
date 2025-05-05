# host1_manager.py
import asyncio
import logging
from autogen_core import TopicId, AgentId, DefaultSubscription, TypeSubscription
from autogen_core import try_get_known_serializers_for_type
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime
from autogen_ext.models.openai import OpenAIChatCompletionClient
from chat_agents import GroupChatManagerAgent
from messages import GroupChatMessage, GroupChatReply
from probill.utils import AppConfig

async def main():

    # Load configuration
    config = AppConfig.load("./config.yaml")
    print("Loaded configuration:", config.host.address, flush=True)
    # Connect to the central host server
    runtime = GrpcWorkerAgentRuntime(host_address="localhost:50051")
    
    # Register message serializers
    for msg_type in [GroupChatMessage, GroupChatReply]:
        runtime.add_message_serializer(try_get_known_serializers_for_type(msg_type))
    
    # Start the runtime
    await runtime.start()
    
    # List of all participants (include ones from other hosts)
    participants = ["AI Expert", "ML Engineer", "Data Scientist", "Writer"]
    model_client = OpenAIChatCompletionClient(**config.client_config)
    # Create and register the manager agent
    # Define the factory function directly here instead of using the class method

    model_client

    def manager_factory():
        agent = GroupChatManagerAgent("Group Chat Manager")
        agent.model_client = model_client
        agent.participants = participants
        agent.conversation_history = []
        agent.turn_count = 0
        return agent
    
    await runtime.register_factory("manager", manager_factory)
    
    # Subscribe to the group chat topic
    group_chat_topic = TopicId("group-chat", "team-discussion")
    manager_agent_id = AgentId("manager", "group-chat-manager")
    # Use TypeSubscription directly, id is generated automatically
    await runtime.add_subscription(TypeSubscription( 
        topic_type=group_chat_topic.type,
        agent_type=manager_agent_id.type
    ))
    
    print("Manager agent is running and ready to coordinate the discussion")
    
    # Keep the runtime running
    await runtime.stop_when_signal()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())