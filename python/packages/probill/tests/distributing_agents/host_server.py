# host_server.py
import asyncio
import logging
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntimeHost

async def main():
    # Initialize host server on a reachable address
    host = GrpcWorkerAgentRuntimeHost(address="0.0.0.0:50051")
    
    # Start the server
    host.start()
    print(f"Host server started at 0.0.0.0:50051")
    
    # Keep the server running until terminated
    try:
        await host.stop_when_signal()
    finally:
        await host.stop()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())