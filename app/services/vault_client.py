from typing import Iterator

import hvac
import typer
from hvac import exceptions as hvac_exceptions

from app.commands.output import print_error


class VaultClient:
    def get_client(self, ctx: typer.Context) -> hvac.Client:
        vault_addr = ctx.obj.get("vault_addr", "http://127.0.0.1:8200")
        vault_token = ctx.obj.get("vault_token", "")

        if not vault_token:
            print_error("Set --vault-token or VAULT_TOKEN before running vault_dump.py")
            raise typer.Exit(code=1)

        client = hvac.Client(url=vault_addr, token=vault_token)
        if not client.is_authenticated():
            print_error("Vault auth failed")
            raise typer.Exit(code=1)

        return client

    def iter_kv2_mounts(self, client: hvac.Client) -> Iterator[str]:
        mounts = client.sys.list_mounted_secrets_engines().get("data", {})
        for mount_name, mount_data in mounts.items():
            mount_point = mount_name.rstrip("/")
            if mount_data.get("type") != "kv":
                continue
            if mount_data.get("options", {}).get("version") != "2":
                continue
            yield mount_point

    def iter_paths(self, client: hvac.Client, mount_point: str, prefix: str = "") -> Iterator[str]:
        try:
            response = client.secrets.kv.v2.list_secrets(mount_point=mount_point, path=prefix)
        except hvac_exceptions.InvalidPath:
            return

        for key in response.get("data", {}).get("keys", []):
            full_path = f"{prefix}{key}"
            if key.endswith("/"):
                yield from self.iter_paths(client, mount_point, full_path)
            else:
                yield full_path

    def read_secret(self, client: hvac.Client, mount_point: str, path: str) -> dict:
        response = client.secrets.kv.v2.read_secret_version(
            mount_point=mount_point,
            path=path,
            raise_on_deleted_version=True,
        )
        return response.get("data", {}).get("data", {})

    @staticmethod
    def split_full_path(full_path: str) -> tuple[str, str]:
        if "/" not in full_path.strip("/"):
            raise ValueError("Path must be in format <mount>/<path>, for example app_configs/app1")
        mount_point, secret_path = full_path.strip("/").split("/", 1)
        return mount_point, secret_path


def get_client(ctx: typer.Context) -> hvac.Client:
    return VaultClient().get_client(ctx)


def iter_kv2_mounts(client: hvac.Client) -> Iterator[str]:
    return VaultClient().iter_kv2_mounts(client)


def iter_paths(client: hvac.Client, mount_point: str, prefix: str = "") -> Iterator[str]:
    return VaultClient().iter_paths(client, mount_point, prefix)


def read_secret(client: hvac.Client, mount_point: str, path: str) -> dict:
    return VaultClient().read_secret(client, mount_point, path)


def split_full_path(full_path: str) -> tuple[str, str]:
    return VaultClient.split_full_path(full_path)
