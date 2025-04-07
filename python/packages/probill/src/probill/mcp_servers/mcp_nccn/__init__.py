from . import server
import asyncio
import argparse
import os
import signal
import sys

def main():
    """Main entry point for the package."""
    parser = argparse.ArgumentParser(description="Neo4j Cypher MCP Server")
    parser.add_argument("--db-url", help="Neo4j connection URL")
    parser.add_argument("--username", help="Neo4j username")
    parser.add_argument("--password", help="Neo4j password")
    parser.add_argument("--database", help="Neo4j database name")

    args = parser.parse_args()
    print(f"Connecting to Neo4j at {args.db_url} with user {args.username}", flush=True)
    print(f"Using database {args.database}", flush=True)

    server.main(args.db_url, args.username, args.password, args.database)
    
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)

    # # Create shutdown event and flags
    # shutdown_event = asyncio.Event()
    # shutdown_initiated = False
    # force_shutdown = False

    # def handle_force_exit():
    #     """Force exit the program"""
    #     try:
    #         sys.stderr.flush()
    #         sys.stdout.flush()
    #         os._exit(1)
    #     except:
    #         os._exit(1)

    # def signal_handler():
    #     nonlocal shutdown_initiated, force_shutdown
    #     if not shutdown_initiated:
    #         print("\nShutting down gracefully... (press Ctrl+C again to force)", flush=True)
    #         shutdown_initiated = True
    #         shutdown_event.set()
    #     else:
    #         print("\nForced shutdown initiated...", flush=True)
    #         force_shutdown = True
    #         # Stop the event loop but ensure we don't get stuck
    #         try:
    #             loop.stop()
    #             # Set a short timeout to allow for minimal cleanup
    #             loop.call_later(2, handle_force_exit)
    #         except:
    #             handle_force_exit()

    # # Set up signal handlers
    # loop.add_signal_handler(signal.SIGINT, signal_handler)
    # loop.add_signal_handler(signal.SIGTERM, signal_handler)

    # try:
    #     server.main(args.db_url, args.username, args.password, args.database, shutdown_event)
    # except (KeyboardInterrupt, RuntimeError) as e:
    #     # Handle both KeyboardInterrupt and RuntimeError from forced shutdown
    #     if not shutdown_initiated or force_shutdown:
    #         print("\nForced shutdown initiated...", flush=True)
    # except Exception as e:
    #     print(f"Error: {e}", flush=True)
    #     return 1
    # finally:
    #     try:
    #         # Cancel all running tasks
    #         pending = asyncio.all_tasks(loop)
    #         for task in pending:
    #             task.cancel()
            
    #         # Allow a short time for tasks to clean up
    #         if pending:
    #             loop.run_until_complete(asyncio.wait(pending, timeout=1.0))
    #     except:
    #         pass
    #     finally:
    #         loop.close()
    #         # If this was a force shutdown, exit directly
    #         if force_shutdown:
    #             handle_force_exit()

    # return 0

# Optionally expose other important items at package level
__all__ = ["main", "server"]