import asyncio
import logging

# Corrected imports to be relative when run_host is executed as a module
from ._types import HostConfig
from ._utils import load_config, set_all_log_levels
from autogen_ext.runtimes.grpc import GrpcWorkerAgentRuntimeHost
from rich.console import Console
from rich.markdown import Markdown

# Set log level
set_all_log_levels(logging.WARNING)

async def main(host_config: HostConfig):
    """Start the host runtime."""
    host = GrpcWorkerAgentRuntimeHost(address=host_config.address)
    host.start()

    console = Console()
    console.print(
        Markdown(f"**`Host`** is running and listening for connections at **`{host_config.address}`**")
    )
    await host.stop_when_signal()

if __name__ == "__main__":
    asyncio.run(main(load_config().host))