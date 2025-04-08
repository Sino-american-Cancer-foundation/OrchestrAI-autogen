from typing import Any, Dict
import yaml
from autogen_core import Component
from autogen_core.models import (
    ChatCompletionClient,
)
from autogen_ext.models.openai import OpenAIChatCompletionClient


def create_oai_client(config: Dict[str, Any]) -> ChatCompletionClient:
    """
    Creates a chat completion client from OpenAI.
    """
    client = OpenAIChatCompletionClient(
        model=config["model"],
        base_url=config["base_url"],
        api_key=config["api_key"],
        model_info=config["model_info"],
        max_tokens=config["max_completion_tokens"],
        max_retries=config["max_retries"],
        temperature=config["temperature"],
        presence_penalty=config["presence_penalty"],
        frequency_penalty=config["frequency_penalty"],
        top_p=config["top_p"],
    )
    return client


def create_stdio_server(config: Dict[str, Any]) -> Any:
    """
    Creates a StdioServerParams instance for command-line MCP tools.
    
    Args:
        config: Dictionary containing stdio server configuration with StdioServerParams section.
        
    Returns:
        StdioServerParams instance configured from the config.
    """
    from autogen_ext.tools.mcp import StdioServerParams
    
    return StdioServerParams(
        command=config.get("command"),
        args=config.get("args", []),
        env=config.get("env", {})
    )


def export_component(c: Component)->Dict:
    try:
        _component = c.dump_component()
        _component.label = _component.config["name"]
        _component.description = _component.config["description"]
        return _component
    except Exception as e:
        print(f"ERROR: {e}")
        return None

def load_yaml_file(file_path: str) -> Any:
    """
    Opens a file and returns its contents.
    """
    with open(file_path, "r") as file:
        return yaml.load(file, Loader=yaml.FullLoader)

