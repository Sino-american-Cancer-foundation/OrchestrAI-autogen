import yaml
import logging
import os
from typing import Any, Iterable, Type, List
import uuid

from autogen_core import MessageSerializer, try_get_known_serializers_for_type
from _types import AppConfig


def load_config(file_path: str = os.path.join(os.path.dirname(__file__), "config.yaml")) -> AppConfig:
    with open(file_path, "r") as file:
        config_data = yaml.safe_load(file)
        app_config = AppConfig(**config_data)
    return app_config


def get_serializers(types: Iterable[Type[Any]]) -> List[MessageSerializer[Any]]:
    serializers = []
    for type in types:
        serializers.extend(try_get_known_serializers_for_type(type))
    return serializers


def is_call_id(id_str: str) -> bool:
    """Check if a string is a valid UUID (used to identify call scenarios)"""
    try:
        uuid.UUID(id_str)
        return True
    except ValueError:
        return False


def set_all_log_levels(log_level: int):
    """Helper to set log levels for all loggers"""
    for _, logger in logging.root.manager.loggerDict.items():
        if isinstance(logger, logging.Logger):
            logger.setLevel(log_level)