"""
Utility functions for MCP server parameter handling and type checking.
"""

from typing import Dict, Any, Optional, Union

def check_and_create_server_params(server_params: Any) -> Any:
    """
    Determine the type of server_params and create the appropriate object if it's a dict.
    
    Args:
        server_params: Can be StdioServerParams, SseServerParams, dict, or None
        
    Returns:
        The correct server_params object based on the input type
    """
    from autogen_ext.tools.mcp import StdioServerParams, SseServerParams
    
    # If already correct type, return as is
    if server_params is None:
        return None
    elif hasattr(server_params, '__class__') and server_params.__class__.__name__ in ('StdioServerParams', 'SseServerParams'):
        return server_params
    elif isinstance(server_params, dict):
        # Make a copy to avoid modifying the original
        params_dict = server_params.copy()
        
        # Check if the type is specified
        if "type" not in params_dict:
            if "command" in params_dict:
                params_dict["type"] = "StdioServerParams"
            elif "url" in params_dict:
                params_dict["type"] = "SseServerParams"
            else:
                raise ValueError(f"Cannot determine server_params type from dict: {server_params}")
        
        # Create the appropriate object based on type
        if params_dict["type"] == "StdioServerParams":
            return StdioServerParams(
                command=params_dict["command"],
                args=params_dict.get("args", []),
                env=params_dict.get("env", {}),
                read_timeout_seconds=params_dict.get("read_timeout_seconds", 5.0)
            )
        elif params_dict["type"] == "SseServerParams":
            return SseServerParams(
                url=params_dict["url"],
                headers=params_dict.get("headers"),
                timeout=params_dict.get("timeout", 5.0),
                sse_read_timeout=params_dict.get("sse_read_timeout", 300.0)
            )
        else:
            raise ValueError(f"Unknown server_params type: {params_dict['type']}")
    else:
        raise TypeError(f"Unsupported server_params type: {type(server_params)}")
