# start_group_chat.py
import asyncio
import logging
from autogen_core import TopicId
from autogen_core import try_get_known_serializers_for_type
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntime

from messages import GroupChatMessage, GroupChatReply

async def main():
    # Connect to the central host server
    runtime = GrpcWorkerAgentRuntime(host_address="central-server-ip:50051")
    
    # Register message serializers
    for msg_type in [GroupChatMessage, GroupChatReply]:
        runtime.add_message_serializer(try_get_known_serializers_for_type(msg_type))
    
    # Start the runtime
    await runtime.start()
    
    # Define the topic
    group_chat_topic = TopicId("group-chat", "team-discussion")
    
    # Initial message to start the discussion
    initial_message = GroupChatMessage(
        content="Let's discuss how machine learning can improve healthcare systems. What are the most promising applications?",
        sender_name="Human"
    )
    
    # Publish the message to start the discussion
    print("Starting group chat discussion...")
    await runtime.publish_message(
        initial_message,
        topic_id=group_chat_topic
    )
    
    print("Initial message sent! The agents will now discuss the topic.")
    
    # Wait a bit before shutting down
    await asyncio.sleep(5)
    await runtime.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())