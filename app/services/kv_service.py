import os

import hvac
import typer
import yaml
from hvac import exceptions as hvac_exceptions

from app.commands.output import compact, print_error, print_success, print_table, stringify
from app.services.vault_client import VaultClient


class KVService:
    def __init__(self, client: hvac.Client, vault_client_service: VaultClient | None = None) -> None:
        self.client = client
        self.vault_client_service = vault_client_service or VaultClient()

    def delete_key(self, full_path: str, key_name: str) -> int:
        if not key_name:
            print_error("Key cannot be empty")
            return 1

        try:
            mount_point, secret_path = self.vault_client_service.split_full_path(full_path)
        except ValueError as error:
            print_error(str(error))
            return 1

        try:
            secret_data = self.vault_client_service.read_secret(self.client, mount_point, secret_path)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot read {full_path}")
            return 1
        except hvac_exceptions.InvalidPath:
            print_error(f"Secret path not found: {full_path}")
            return 1

        if key_name not in secret_data:
            print_error(f"Key '{key_name}' not found in {full_path}")
            return 1

        del secret_data[key_name]

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                mount_point=mount_point,
                path=secret_path,
                secret=secret_data,
            )
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot update {full_path}")
            return 1

        print_success(f"Removed key '{key_name}' from {full_path}")
        return 0

    def upsert_key(self, full_path: str, key_name: str, key_value: str) -> int:
        if not key_name:
            print_error("Key cannot be empty")
            return 1

        try:
            mount_point, secret_path = self.vault_client_service.split_full_path(full_path)
        except ValueError as error:
            print_error(str(error))
            return 1

        secret_data: dict[str, object]
        try:
            secret_data = self.vault_client_service.read_secret(self.client, mount_point, secret_path)
        except hvac_exceptions.InvalidPath:
            secret_data = {}
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot read {full_path}")
            return 1

        secret_data[key_name] = key_value

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                mount_point=mount_point,
                path=secret_path,
                secret=secret_data,
            )
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot update {full_path}")
            return 1

        print_success(f"Set key '{key_name}' in {full_path}")
        rows = [[str(key), stringify(value)] for key, value in secret_data.items()]
        print_table(title=full_path, headers=["key", "value"], rows=rows)
        return 0

    def upload_secret(self, full_path: str, data: dict[str, object]) -> int:
        try:
            mount_point, secret_path = self.vault_client_service.split_full_path(full_path)
        except ValueError as error:
            print_error(str(error))
            return 1

        try:
            self.client.secrets.kv.v2.create_or_update_secret(
                mount_point=mount_point,
                path=secret_path,
                secret=data,
            )
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot update {full_path}")
            return 1
        except hvac_exceptions.InvalidRequest as error:
            print_error(compact(error))
            return 1

        print_success(f"Uploaded {len(data)} key(s) to {full_path}")
        rows = [[str(key), stringify(value)] for key, value in data.items()]
        if not rows:
            rows = [["", "<empty>"]]
        print_table(title=full_path, headers=["key", "value"], rows=rows)
        return 0

    def get_secret_rows(self, full_path: str) -> tuple[int, list[list[str]]]:
        try:
            mount_point, secret_path = self.vault_client_service.split_full_path(full_path)
        except ValueError as error:
            print_error(str(error))
            return 1, []

        try:
            secret_data = self.vault_client_service.read_secret(self.client, mount_point, secret_path)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot read {full_path}")
            return 1, []
        except hvac_exceptions.InvalidPath:
            print_error(f"Secret path not found: {full_path}")
            return 1, []

        if not secret_data:
            return 0, [["", "<empty>"]]

        rows = [[str(key), stringify(value)] for key, value in secret_data.items()]
        return 0, rows

    @staticmethod
    def read_upload_data(file_path: str) -> dict[str, object]:
        expanded_path = os.path.expanduser(file_path)

        try:
            with open(expanded_path, "r", encoding="utf-8") as file:
                content = yaml.safe_load(file)
        except FileNotFoundError:
            print_error(f"Input file not found: {file_path}")
            raise typer.Exit(code=1)
        except yaml.YAMLError as error:
            print_error(f"Invalid YAML in input file: {error}")
            raise typer.Exit(code=1)
        except OSError as error:
            print_error(f"Cannot read input file: {error}")
            raise typer.Exit(code=1)

        if content is None:
            return {}

        if not isinstance(content, dict):
            print_error("Input file must contain a YAML mapping of key/value pairs")
            raise typer.Exit(code=1)

        return {str(key): value for key, value in content.items()}


def delete_key(client: hvac.Client, full_path: str, key_name: str) -> int:
    return KVService(client).delete_key(full_path, key_name)


def upsert_key(client: hvac.Client, full_path: str, key_name: str, key_value: str) -> int:
    return KVService(client).upsert_key(full_path, key_name, key_value)


def read_upload_data(file_path: str) -> dict[str, object]:
    return KVService.read_upload_data(file_path)


def upload_secret(client: hvac.Client, full_path: str, data: dict[str, object]) -> int:
    return KVService(client).upload_secret(full_path, data)


def get_secret_rows(client: hvac.Client, full_path: str) -> tuple[int, list[list[str]]]:
    return KVService(client).get_secret_rows(full_path)
