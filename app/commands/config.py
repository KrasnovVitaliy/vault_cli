import os
import tomllib
from importlib import metadata

import typer
import yaml

from app.commands.output import print_error, print_success, stringify


def get_app_version() -> str:
    try:
        return metadata.version("vault-cli")
    except metadata.PackageNotFoundError:
        pass

    try:
        with open("pyproject.toml", "rb") as file:
            pyproject_data = tomllib.load(file)
    except OSError:
        return "unknown"

    return stringify(pyproject_data.get("project", {}).get("version", "unknown"))


def read_profile(profile_path: str) -> dict[str, str]:
    try:
        with open(profile_path, "r", encoding="utf-8") as file:
            content = yaml.safe_load(file) or {}
    except FileNotFoundError:
        print_error(f"Profile file not found: {profile_path}")
        raise typer.Exit(code=1)
    except yaml.YAMLError as error:
        print_error(f"Invalid YAML profile: {error}")
        raise typer.Exit(code=1)
    except OSError as error:
        print_error(f"Cannot read profile file: {error}")
        raise typer.Exit(code=1)

    if not isinstance(content, dict):
        print_error("Profile must contain a YAML mapping of key/value pairs")
        raise typer.Exit(code=1)

    return {str(key): str(value) for key, value in content.items() if value is not None}


def create_profile_template(profile_path: str, overwrite: bool) -> int:
    if not profile_path.strip():
        print_error("Profile path cannot be empty")
        return 1

    normalized_path = os.path.expanduser(profile_path)
    parent_dir = os.path.dirname(normalized_path)

    try:
        if parent_dir:
            os.makedirs(parent_dir, exist_ok=True)
    except OSError as error:
        print_error(f"Cannot create directories for profile path: {error}")
        return 1

    if os.path.exists(normalized_path) and not overwrite:
        print_error("Profile file already exists. Use --overwrite to replace it.")
        return 1

    template_data = {
        "vault_addr": "http://127.0.0.1:8200",
        "vault_token": "",
    }

    try:
        with open(normalized_path, "w", encoding="utf-8") as file:
            yaml.safe_dump(template_data, file, sort_keys=False)
    except OSError as error:
        print_error(f"Cannot write profile template: {error}")
        return 1

    print_success(f"Profile template created: {normalized_path}")
    return 0


def profile_value(profile_data: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = profile_data.get(key)
        if value:
            return value
    return ""
