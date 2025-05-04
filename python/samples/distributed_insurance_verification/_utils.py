import logging
import os
from typing import Any, Iterable, Type

import yaml
from _types import AppConfig
from autogen_core import MessageSerializer, try_get_known_serializers_for_type
from autogen_ext.models.openai.config import OpenAIClientConfiguration


def load_config(file_path: str = os.path.join(os.path.dirname(__file__), "config.yaml")) -> AppConfig:
    with open(file_path, "r") as file:
        config_data = yaml.safe_load(file)
        model_client = config_data["client_config"]
        del config_data["client_config"]
        app_config = AppConfig(**config_data)
    
    app_config.client_config = OpenAIClientConfiguration(**model_client)
    return app_config


def get_serializers(types: Iterable[Type[Any]]) -> list[MessageSerializer[Any]]:
    serializers = []
    for type in types:
        serializers.extend(try_get_known_serializers_for_type(type))
    return serializers


def set_all_log_levels(log_level: int):
    for _, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.setLevel(log_level)