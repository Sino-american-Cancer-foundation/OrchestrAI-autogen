from typing import Any, Dict
import yaml
from autogen_core import Component
from autogen_core.models import (
    ChatCompletionClient,
)
from autogen_ext.models.openai import OpenAIChatCompletionClient
import logging
import os
from typing import Any, Iterable, Type
from pydantic import BaseModel
import yaml

from autogen_core import MessageSerializer, try_get_known_serializers_for_type
from autogen_ext.models.openai.config import AzureOpenAIClientConfiguration
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from ._types import (
    GroupChatMessage,
    MessageChunk,
    RequestToSpeak,
    HostConfig,
    GroupChatManagerConfig,
    ChatAgentConfig,
    UIAgentConfig,
)

class AppConfig(BaseModel):
    host: HostConfig
    group_chat_manager: GroupChatManagerConfig
    ui_agent: UIAgentConfig
    client_config: AzureOpenAIClientConfiguration = None  # type: ignore[assignment] # This was required to do custom instantiation in `load_config`
    """Configuration model for the application."""
    class Config:
        extra = "allow"  # Allow extra fields not defined in the model

    @classmethod
    def load(cls, file_path: str = os.path.join(os.path.dirname(__file__), "config.yaml")) -> "AppConfig":
        with open(file_path, "r") as file:
            config_data = yaml.safe_load(file)
            if "app_config" not in config_data:
                raise ValueError("Config file must contain 'app_config' section")
            
            config_section = config_data["app_config"]
            
            cls.model_client = config_section["client_config"]
            del config_section["client_config"]

            cls.host = HostConfig(**config_section["host"])
            del config_section["host"]

            cls.group_chat_manager = GroupChatManagerConfig(**config_section["group_chat_manager"])
            del config_section["group_chat_manager"]
            cls.ui_agent = UIAgentConfig(**config_section["ui_agent"])
            del config_section["ui_agent"]
            # This was required as it couldn't automatically instantiate AzureOpenAIClientConfiguration
            aad_params = {}
            if len(cls.model_client.get("api_key", "")) == 0:
                aad_params["azure_ad_token_provider"] = get_bearer_token_provider(
                    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default"
                )
            cls.client_config = AzureOpenAIClientConfiguration(**cls.model_client, **aad_params)  # type: ignore[typeddict-item]
            # Remove the client_config from the config_section
            # Create a new instance with the config data
            return cls.model_validate(config_section)



def get_serializers(types: Iterable[Type[Any]]) -> list[MessageSerializer[Any]]:
    serializers = []
    for type in types:
        serializers.extend(try_get_known_serializers_for_type(type))  # type: ignore
    return serializers  # type: ignore [reportUnknownVariableType]


# TODO: This is a helper function to get rid of a lot of logs until we find exact loggers to properly set log levels ...
def set_all_log_levels(log_leve: int):
    # Iterate through all existing loggers and set their levels
    for _, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):  # Ensure it's actually a Logger object
            logger.setLevel(log_leve)  # Adjust to DEBUG or another level as needed


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
        env=config.get("env", {}),
        read_timeout_seconds=config.get("read_timeout_seconds", 5),
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

