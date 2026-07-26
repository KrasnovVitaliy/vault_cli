import json
import os

import typer
from hvac import exceptions as hvac_exceptions

from app.commands.config import create_profile_template, get_app_version, profile_value, read_profile
from app.commands.output import ANSI_BLUE, ANSI_RESET, print_blue_separator, print_error, print_framed_lines, print_success, print_table, stringify
from app.services.kv_service import KVService
from app.services.policy_service import PolicyService
from app.services.token_service import TokenService
from app.services.vault_client import VaultClient


app = typer.Typer(
    add_completion=False,
    help="List Vault KV v2 secrets and delete a key from a secret.",
)
vault_client_service = VaultClient()


@app.callback()
def common_options(
    ctx: typer.Context,
    vault_addr: str | None = typer.Option(
        None,
        "--vault-addr",
        help="Vault address (can also come from VAULT_ADDR).",
    ),
    vault_token: str | None = typer.Option(
        None,
        "--vault-token",
        help="Vault token (can also come from VAULT_TOKEN).",
    ),
    profile: str | None = typer.Option(
        None,
        "--profile",
        help="Path to YAML profile with Vault connection settings.",
    ),
) -> None:
    profile_data: dict[str, str] = {}
    if profile:
        profile_data = read_profile(profile)

    env_addr = os.getenv("VAULT_ADDR")
    env_token = os.getenv("VAULT_TOKEN")

    profile_addr = profile_value(profile_data, "vault_addr", "VAULT_ADDR", "addr")
    profile_token = profile_value(profile_data, "vault_token", "VAULT_TOKEN", "token")

    ctx.obj = {
        "vault_addr": vault_addr or env_addr or profile_addr or "http://127.0.0.1:8200",
        "vault_token": vault_token or env_token or profile_token or "",
    }


@app.command("dump")
def dump(ctx: typer.Context) -> None:
    """List KV v2 secrets and show values in per-path tables."""
    client = vault_client_service.get_client(ctx)

    path_tables: dict[str, list[list[str]]] = {}

    for mount_point in vault_client_service.iter_kv2_mounts(client):
        for secret_path in vault_client_service.iter_paths(client, mount_point):
            full_path = f"{mount_point}/{secret_path}"
            try:
                secret_data = vault_client_service.read_secret(client, mount_point, secret_path)
                if not secret_data:
                    path_tables[full_path] = [["", "<empty>"]]
                    continue
                rows: list[list[str]] = []
                for key, value in secret_data.items():
                    rows.append([str(key), stringify(value)])
                path_tables[full_path] = rows
            except hvac_exceptions.Forbidden:
                path_tables[full_path] = [["", "<permission denied>"]]

    if not path_tables:
        print_error("No KV v2 secrets found or no access to list them.")
        return

    for index, full_path in enumerate(sorted(path_tables), start=1):
        print_table(
            title=f"{index}. {full_path}",
            headers=["key", "value"],
            rows=path_tables[full_path],
        )


@app.command("delete")
def delete(
    ctx: typer.Context,
    path: str = typer.Argument(
        ..., help="Full secret path in format <mount>/<path>, for example app_configs/app1"
    ),
    key: str = typer.Argument(..., help="Secret key to remove"),
) -> None:
    """Delete one key from a KV v2 secret."""
    client = vault_client_service.get_client(ctx)
    exit_code = KVService(client, vault_client_service).delete_key(path, key)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("set")
def set_secret(
    ctx: typer.Context,
    path: str = typer.Argument(
        ..., help="Full secret path in format <mount>/<path>, for example app_configs/app1"
    ),
    key: str = typer.Argument(..., help="Secret key to add or update"),
    value: str = typer.Argument(..., help="Secret value for the key"),
) -> None:
    """Add or update one key in a KV v2 secret and print updated table."""
    client = vault_client_service.get_client(ctx)
    exit_code = KVService(client, vault_client_service).upsert_key(path, key, value)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("upload")
def upload_secret_command(
    ctx: typer.Context,
    path: str = typer.Argument(
        ..., help="Full secret path in format <mount>/<path>, for example app_configs/app1"
    ),
    file: str = typer.Argument(..., help="YAML file with key/value pairs to upload"),
) -> None:
    """Upload all key/value pairs from YAML file to one KV v2 secret path."""
    client = vault_client_service.get_client(ctx)
    kv_service = KVService(client, vault_client_service)
    data = kv_service.read_upload_data(file)
    exit_code = kv_service.upload_secret(path, data)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("get")
def get_secret(
    ctx: typer.Context,
    path: str = typer.Argument(
        ..., help="Full secret path in format <mount>/<path>, for example app_configs/app1"
    ),
) -> None:
    """Show keys and values for one KV v2 secret path."""
    client = vault_client_service.get_client(ctx)
    exit_code, rows = KVService(client, vault_client_service).get_secret_rows(path)
    if exit_code:
        raise typer.Exit(code=exit_code)

    print_table(title=path, headers=["key", "value"], rows=rows)


@app.command("tokens")
def tokens(ctx: typer.Context) -> None:
    """Show available tokens only."""
    client = vault_client_service.get_client(ctx)
    token_service = TokenService(client)

    exit_code, token_rows = token_service.lookup_self_token_row()
    if exit_code:
        raise typer.Exit(code=exit_code)

    accessor_rows = token_service.lookup_accessors_rows()
    for row in accessor_rows:
        accessor = row[1]
        if accessor and all(existing[1] != accessor for existing in token_rows):
            token_rows.append(row)

    print_table(
        title="Tokens",
        headers=["display_name", "accessor", "ttl", "renewable", "policies"],
        rows=token_rows,
    )


@app.command("policies")
def policies(ctx: typer.Context) -> None:
    """Show policy name and JSON content."""
    client = vault_client_service.get_client(ctx)
    policy_service = PolicyService(client)
    policy_names = policy_service.list_policy_names()
    if not policy_names:
        print_error("No policies found or no access to list them")
        return

    printed_any = False

    for name in policy_names:
        try:
            policy_data = client.sys.read_policy(name)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot read policy '{name}'")
            continue
        except hvac_exceptions.InvalidPath:
            print_error(f"Policy not found: {name}")
            continue

        print_blue_separator()
        typer.echo(f"{ANSI_BLUE}{name}{ANSI_RESET}")
        typer.echo(json.dumps(policy_data, ensure_ascii=False, indent=2))
        print_blue_separator()
        typer.echo("")
        printed_any = True

    if not printed_any:
        print_error("No readable policies found")


@app.command("policy-create")
def policy_create(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Policy name to create."),
    rules: str = typer.Argument(..., help="Policy rules in HCL format."),
) -> None:
    """Create a new policy."""
    client = vault_client_service.get_client(ctx)
    exit_code = PolicyService(client).create_or_update_policy(name, rules, require_exists=False)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("policy-update")
def policy_update(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Policy name to update."),
    rules: str = typer.Argument(..., help="Policy rules in HCL format."),
) -> None:
    """Update an existing policy."""
    client = vault_client_service.get_client(ctx)
    exit_code = PolicyService(client).create_or_update_policy(name, rules, require_exists=True)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("policy-delete")
def policy_delete(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="Policy name to delete."),
) -> None:
    """Delete an existing policy."""
    client = vault_client_service.get_client(ctx)
    exit_code = PolicyService(client).delete_policy(name)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("token-create")
def token_create(
    ctx: typer.Context,
    policy: list[str] = typer.Option(
        [], "--policy", "-p", help="Policy name to attach. Can be repeated."
    ),
    ttl: str | None = typer.Option(
        None, "--ttl", help="Optional token TTL, e.g. 1h, 24h."
    ),
    display_name: str | None = typer.Option(
        None, "--display-name", help="Optional display name for the new token."
    ),
    renewable: bool | None = typer.Option(
        None,
        "--renewable/--no-renewable",
        help="Optional renewable flag. Omit to use Vault defaults.",
    ),
    orphan: bool = typer.Option(
        False,
        "--orphan",
        help="Create orphan token without parent dependency.",
    ),
) -> None:
    """Create a Vault token."""
    client = vault_client_service.get_client(ctx)
    token_service = TokenService(client)
    exit_code, auth = token_service.create_token(policy, ttl, display_name, renewable, orphan)
    if exit_code:
        raise typer.Exit(code=exit_code)

    token_value = stringify(auth.get("client_token", ""))
    accessor_value = stringify(auth.get("accessor", ""))

    looked_up = token_service.lookup_created_token(token_value) if token_value else {}
    info = looked_up or auth

    policies_value = token_service.token_policies(info)
    renewable_value = stringify(info.get("renewable", ""))
    ttl_value = token_service.token_ttl(info.get("ttl", auth.get("lease_duration", "")))
    if display_name is not None and display_name.strip():
        display_name_value = display_name.strip()
    else:
        display_name_value = stringify(info.get("display_name", ""))

    print_success("Token created")
    print_table(
        title="Created token",
        headers=["token", "display_name", "accessor", "ttl", "renewable", "policies"],
        rows=[[
            token_value,
            display_name_value,
            accessor_value,
            ttl_value,
            renewable_value,
            policies_value,
        ]],
    )


@app.command("token-delete")
def token_delete(
    ctx: typer.Context,
    token: str | None = typer.Argument(
        None,
        help="Token value to revoke. Omit when using --accessor or --self.",
    ),
    accessor: str | None = typer.Option(
        None,
        "--accessor",
        help="Revoke token by accessor instead of token value.",
    ),
    revoke_self: bool = typer.Option(
        False,
        "--self",
        help="Revoke the token used for current authentication.",
    ),
) -> None:
    """Delete (revoke) a Vault token."""
    client = vault_client_service.get_client(ctx)
    exit_code = TokenService(client).delete_token(token, accessor, revoke_self)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("profile-template")
def profile_template(
    path: str = typer.Argument(
        ..., help="Path to output YAML profile template, for example ./local.yaml"
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help="Overwrite file if it already exists.",
    ),
) -> None:
    """Create YAML profile template with Vault connection parameters."""
    exit_code = create_profile_template(path, overwrite)
    if exit_code:
        raise typer.Exit(code=exit_code)


@app.command("help")
def help_command() -> None:
    """Show quick help for vault_dump commands."""
    version = get_app_version()
    help_lines = [
        f"Version: {version}",
        "",
        "Available commands:",
        "  dump                 List secrets in per-path tables",
        "  get <path>           Show all keys/values for one secret path",
        "  set <path> <key> <value>  Add or update one key in a secret",
        "  upload <path> <file> Upload key/value pairs from YAML file",
        "  delete <path> <key>  Delete one key from a secret",
        "  tokens               Show available tokens only",
        "  policies             Show policy name and JSON payload",
        "  policy-create        Create a new policy from HCL rules",
        "  policy-update        Update an existing policy from HCL rules",
        "  policy-delete        Delete an existing policy",
        "  token-create         Create a new Vault token",
        "  token-delete         Revoke token by value, accessor or self",
        "  profile-template     Create YAML profile template at path",
        "  help                 Show this help",
        "",
        "Global options:",
        "  --vault-addr <url>   Vault URL (default: http://127.0.0.1:8200)",
        "  --vault-token <tok>  Vault token (or use VAULT_TOKEN)",
        "  --profile <path>     YAML profile with Vault connection parameters",
        "",
        "Tip: use --help for detailed options, for example:",
        "  vault_cli --help",
        "  vault_cli dump --help",
        "  vault_cli get --help",
        "  vault_cli set --help",
        "  vault_cli upload --help",
        "  vault_cli delete --help",
        "  vault_cli token-create --help",
        "  vault_cli token-delete --help",
        "  vault_cli tokens --help",
        "  vault_cli policies --help",
        "  vault_cli policy-create --help",
        "  vault_cli policy-update --help",
        "  vault_cli policy-delete --help",
        "  vault_cli profile-template --help",
    ]
    print_framed_lines("Help", help_lines, ANSI_BLUE)
