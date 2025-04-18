# host3_participant2.py
import asyncio
import logging
from autogen_core import TopicId, AgentId
from autogen_core import try_get_known_serializers_for_type
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

from chat_agents import GroupChatParticipantAgent
from messages import GroupChatMessage, GroupChatReply

async def main():
    # Connect to the central host server
    runtime = GrpcWorkerAgentRuntime(host_address="central-server-ip:50051")
    
    # Register message serializers
    for msg_type in [GroupChatMessage, GroupChatReply]:
        runtime.add_message_serializer(try_get_known_serializers_for_type(msg_type))
    
    # Start the runtime
    await runtime.start()
    
    # Create model client
    model_client = OpenAIChatCompletionClient(model="gpt-4-turbo")
    
    # Create and register the participant agent
    participant = GroupChatParticipantAgent("ML Engineer", model_client, "machine learning")
    await runtime.register_factory("ml_engineer", lambda: participant)
    
    # Subscribe to the group chat topic
    group_chat_topic = TopicId("group-chat", "team-discussion")
    await runtime.add_subscription({
        "id": "ml-engineer-subscription",
        "topic_id": group_chat_topic,
        "recipient": AgentId("ml_engineer", "ml-participant")
    })
    
    print("ML Engineer agent is running and ready to participate")
    
    # Keep the runtime running
    await runtime.stop_when_signal()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())