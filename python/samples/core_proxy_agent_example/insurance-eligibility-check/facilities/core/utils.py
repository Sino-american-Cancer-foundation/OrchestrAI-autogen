import logging
import os
from pathlib import Path
from typing import List, Type, Any, Iterable

import yaml
from autogen_core import MessageSerializer, try_get_known_serializers_for_type

from .types import AppConfig


def set_all_log_levels(level: int) -> None:
    """Set all log levels to the specified level."""
    for name in logging.root.manager.loggerDict:
        logging.getLogger(name).setLevel(level)


def load_config() -> AppConfig:
    """Load configuration from config.yaml file."""
    config_path = Path(__file__).parent.parent.parent / "samples" / "config.yaml"
    with open(config_path, "r") as f:
        config_dict = yaml.safe_load(f)

    # Replace environment variables
    for key in ["AZURE_OPENAI_ENDPOINT", "AZURE_OPENAI_API_KEY"]:
        if key in os.environ and "azure_model_config" in config_dict:
            config_dict["azure_model_config"][key.lower()] = os.environ[key]

    # Load phone call instruction file for TwilioProxyAgent system message
    if "proxy_agent" in config_dict:
        phone_instruction_path = Path(__file__).parent.parent.parent / "employees" / "twilio_proxy_agent" / "prompts" / "phone_call_instruction.txt"
        try:
            with open(phone_instruction_path, "r") as f:
                phone_call_instruction = f.read()
            config_dict["proxy_agent"]["system_message"] = phone_call_instruction
            print(f"✅ Loaded phone call instruction from {phone_instruction_path}")
        except FileNotFoundError:
            print(f"⚠️  Warning: {phone_instruction_path} not found, using default system message")

    return AppConfig(**config_dict)


def get_serializers(types: Iterable[Type[Any]]) -> List[MessageSerializer[Any]]:
    """Get message serializers for the given types."""
    serializers = []
    for type in types:
        serializers.extend(try_get_known_serializers_for_type(type))
    return serializers 