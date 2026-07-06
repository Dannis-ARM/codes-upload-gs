"""Configuration loader for migration API checker."""

import os
import re
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

import yaml
from dotenv import load_dotenv


@dataclass
class GlobalConfig:
    """Global configuration."""
    common_headers: Dict[str, str] = field(default_factory=dict)
    timeout: int = 30
    retries: int = 0


@dataclass
class ApiCase:
    """API test case configuration."""
    name: str
    method: str
    before: str
    after: str
    headers: Dict[str, str] = field(default_factory=dict)
    params: Dict[str, Any] = field(default_factory=dict)
    body: Optional[Dict[str, Any]] = None
    ignore_fields: List[str] = field(default_factory=list)


@dataclass
class Config:
    """Full configuration."""
    global_config: GlobalConfig
    apis: List[ApiCase]


def _expand_env_vars(value: str) -> str:
    """Expand environment variables in string like ${VAR}."""
    pattern = re.compile(r'\$\{([^}^{]+)\}')

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))

    return pattern.sub(replace_var, value)


def _expand_env_in_dict(data: Any) -> Any:
    """Recursively expand environment variables in dict/list/string."""
    if isinstance(data, str):
        return _expand_env_vars(data)
    elif isinstance(data, dict):
        return {k: _expand_env_in_dict(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_expand_env_in_dict(item) for item in data]
    return data


def load_config(config_path: str = "cfgs.yaml") -> Config:
    """
    Load and parse configuration from YAML file.

    Args:
        config_path: Path to YAML configuration file.

    Returns:
        Parsed Config object.
    """
    # Load .env file if exists
    load_dotenv()

    with open(config_path, "r", encoding="utf-8") as f:
        raw_data = yaml.safe_load(f)

    # Expand environment variables
    data = _expand_env_in_dict(raw_data)

    # Parse global config
    global_raw = data.get("global", {})
    global_config = GlobalConfig(
        common_headers=global_raw.get("common_headers", {}),
        timeout=global_raw.get("timeout", 30),
        retries=global_raw.get("retries", 0),
    )

    # Parse API cases
    apis: List[ApiCase] = []
    for api_raw in data.get("apis", []):
        apis.append(ApiCase(
            name=api_raw.get("name", f"API-{len(apis)+1}"),
            method=api_raw.get("method", "GET").upper(),
            before=api_raw["before"],
            after=api_raw["after"],
            headers=api_raw.get("headers", {}),
            params=api_raw.get("params", {}),
            body=api_raw.get("body"),
            ignore_fields=api_raw.get("ignore_fields", []),
        ))

    return Config(global_config=global_config, apis=apis)
