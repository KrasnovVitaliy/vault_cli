# vault-cli

Production-ready CLI for working with HashiCorp Vault KV v2 secrets, tokens, and policies.

## Features

- Read and list KV v2 secrets
- Set, delete, and upload key/value pairs from YAML
- Create, update, and delete Vault policies
- Create and revoke Vault tokens
- Use CLI flags, environment variables, or a YAML profile for configuration

## Requirements

- Python 3.14+
- uv
- Access to a running Vault instance

## Installation

From the vault_cli directory:

```bash
uv sync
```

Optional editable install:

```bash
make install-editable
```

## Quick Start

Run help:

```bash
make run
```

Or directly:

```bash
uv run python3 -m app.main --help
```

You can also use the generated script names:

```bash
vault_cli --help
vault-cli --help
```

## Configuration

The CLI reads connection settings in this priority order:

1. Command options
2. Environment variables
3. YAML profile file

Global options:

- --vault-addr
- --vault-token
- --profile

Environment variables:

- VAULT_ADDR
- VAULT_TOKEN

Create a profile template:

```bash
uv run python3 -m app.main profile-template ./local.yaml
```

## Common Commands

```bash
# List all KV v2 secrets
uv run python3 -m app.main dump

# Read one secret
uv run python3 -m app.main get app_configs/app1

# Set one key
uv run python3 -m app.main set app_configs/app1 KAFKA_USERNAME demo

# Upload all key/value pairs from YAML
uv run python3 -m app.main upload app_configs/app1 ./config.yml

# Delete one key
uv run python3 -m app.main delete app_configs/app1 KAFKA_USERNAME

# List tokens and policies
uv run python3 -m app.main tokens
uv run python3 -m app.main policies
```

## Development

Useful Make targets:

- make help
- make run
- make build
- make clean
- make install
- make uninstall
- make reinstall
- make set-version VERSION=0.2.0

Build artifacts are written to dist/.

## Project Layout

```text
vault_cli/
	app/
		commands/
		services/
		main.py
	Makefile
	pyproject.toml
```

## Notes

- The package entrypoints are configured in pyproject.toml as app.main:app.
- For local development, prefer module execution with uv run python3 -m app.main.