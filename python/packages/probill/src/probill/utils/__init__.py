"""
Utility modules for probill package.
"""

# Import and re-export all utility functions
from ._utils import (
    get_serializers,
    set_all_log_levels,
    create_oai_client,
    create_stdio_server,
    export_component,
    load_yaml_file,
    AppConfig,
)

from ._types import (
    GroupChatMessage, 
    RequestToSpeak,
    MessageChunk,
    HostConfig,
    GroupChatManagerConfig,
    ChatAgentConfig,
    UIAgentConfig,
)

# Import check_and_create_server_params from _mcp_utils but handle circular import
# We'll import it in a function to avoid circular imports at module load time
def check_and_create_server_params(server_params):
    """
    Wrapper to avoid circular imports.
    
    Determine the type of server_params and create the appropriate object if it's a dict.
    
    Args:
        server_params: Can be StdioServerParams, SseServerParams, dict, or None
        
    Returns:
        The correct server_params object based on the input type
    """
    from ._mcp_utils import check_and_create_server_params as _check_and_create_server_params
    return _check_and_create_server_params(server_params)

def create_sse_server(config):
    """
    Creates an SseServerParams instance for SSE-based MCP services.
    
    Args:
        config: Dictionary containing SSE server configuration.
        
    Returns:
        SseServerParams instance configured from the config.
    """
    from autogen_ext.tools.mcp import SseServerParams
    
    # Make sure type is set for Pydantic validation
    config_copy = config.copy()
    if "type" not in config_copy:
        config_copy["type"] = "SseServerParams"
    
    return SseServerParams(
        url=config_copy.get("url"),
        headers=config_copy.get("headers"),
        timeout=config_copy.get("timeout", 5.0),
        sse_read_timeout=config_copy.get("sse_read_timeout", 300.0),
    )

# Define __all__ to explicitly state what's available when doing `from probill.utils import *`
__all__ = [
    # From _utils.py
    'get_serializers',
    'set_all_log_levels',
    'create_oai_client',
    'create_stdio_server',
    'export_component',
    'load_yaml_file',
    'AppConfig',
    
    # From _types.py
    'GroupChatMessage',
    'RequestToSpeak',
    'MessageChunk',
    'HostConfig',
    'GroupChatManagerConfig',
    'ChatAgentConfig',
    'UIAgentConfig',
    
    # Functions defined here
    'check_and_create_server_params',
    'create_sse_server',
]
