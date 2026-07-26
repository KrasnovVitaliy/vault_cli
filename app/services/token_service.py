import hvac
from hvac import exceptions as hvac_exceptions

from app.commands.output import compact, print_error, print_success, stringify


class TokenService:
    def __init__(self, client: hvac.Client) -> None:
        self.client = client

    @staticmethod
    def token_ttl(ttl: object) -> str:
        try:
            ttl_int = int(ttl)
        except (TypeError, ValueError):
            return stringify(ttl)
        return f"{ttl_int}s"

    @staticmethod
    def token_policies(info: dict[str, object]) -> str:
        policies = info.get("token_policies") or info.get("policies") or []
        if not isinstance(policies, list):
            return stringify(policies)
        cleaned = [str(item) for item in policies if str(item).strip()]
        return ", ".join(cleaned)

    def lookup_self_token_row(self) -> tuple[int, list[list[str]]]:
        try:
            info = self.client.auth.token.lookup_self().get("data", {})
        except hvac_exceptions.Forbidden:
            print_error("Permission denied: cannot lookup current token")
            return 1, []

        row = [
            stringify(info.get("display_name", "self")) or "self",
            stringify(info.get("accessor", "")),
            self.token_ttl(info.get("ttl", "")),
            stringify(info.get("renewable", "")),
            self.token_policies(info),
        ]
        return 0, [row]

    def lookup_accessors_rows(self) -> list[list[str]]:
        rows: list[list[str]] = []
        try:
            accessors = self.client.auth.token.list_accessors().get("data", {}).get("keys", [])
        except hvac_exceptions.Forbidden:
            print_error("Permission denied: cannot list token accessors. Showing current token only.")
            return rows
        except hvac_exceptions.InvalidPath:
            return rows

        for accessor in accessors:
            try:
                info = self.client.auth.token.lookup_accessor(accessor).get("data", {})
                rows.append(
                    [
                        stringify(info.get("display_name", "")),
                        stringify(accessor),
                        self.token_ttl(info.get("ttl", "")),
                        stringify(info.get("renewable", "")),
                        self.token_policies(info),
                    ]
                )
            except hvac_exceptions.Forbidden:
                rows.append(["<forbidden>", stringify(accessor), "", "", ""])
        return rows

    def create_token(
        self,
        policies: list[str],
        ttl: str | None,
        display_name: str | None,
        renewable: bool | None,
        orphan: bool,
    ) -> tuple[int, dict[str, object]]:
        cleaned_policies = [policy.strip() for policy in policies if policy.strip()]
        create_kwargs: dict[str, object] = {
            "no_parent": orphan,
        }
        if cleaned_policies:
            create_kwargs["policies"] = cleaned_policies
        if ttl:
            create_kwargs["ttl"] = ttl
        if display_name is not None and display_name.strip():
            create_kwargs["display_name"] = display_name.strip()
        if renewable is not None:
            create_kwargs["renewable"] = renewable

        try:
            response = self.client.auth.token.create(**create_kwargs)
        except hvac_exceptions.Forbidden:
            print_error("Permission denied: cannot create token")
            return 1, {}

        auth = response.get("auth", {})
        if not isinstance(auth, dict):
            print_error("Unexpected Vault response while creating token")
            return 1, {}
        return 0, auth

    def lookup_created_token(self, token_value: str) -> dict[str, object]:
        try:
            response = self.client.auth.token.lookup(token_value)
        except hvac_exceptions.Forbidden:
            return {}
        data = response.get("data", {})
        return data if isinstance(data, dict) else {}

    def delete_token(self, token: str | None, accessor: str | None, revoke_self: bool) -> int:
        selected_modes = int(bool(token)) + int(bool(accessor)) + int(revoke_self)
        if selected_modes != 1:
            print_error("Choose exactly one mode: <token> OR --accessor OR --self")
            return 1

        try:
            if revoke_self:
                self.client.auth.token.revoke_self()
                print_success("Current token revoked")
                return 0

            if accessor:
                self.client.auth.token.revoke_accessor(accessor)
                print_success(f"Token revoked by accessor: {accessor}")
                return 0

            if token:
                self.client.auth.token.revoke(token)
                print_success("Token revoked")
                return 0
        except hvac_exceptions.Forbidden:
            print_error("Permission denied: cannot revoke token")
            return 1
        except hvac_exceptions.InvalidRequest as error:
            print_error(compact(error))
            return 1

        print_error("No revoke action was executed")
        return 1


def token_ttl(ttl: object) -> str:
    return TokenService.token_ttl(ttl)


def token_policies(info: dict[str, object]) -> str:
    return TokenService.token_policies(info)


def lookup_self_token_row(client: hvac.Client) -> tuple[int, list[list[str]]]:
    return TokenService(client).lookup_self_token_row()


def lookup_accessors_rows(client: hvac.Client) -> list[list[str]]:
    return TokenService(client).lookup_accessors_rows()


def create_token(
    client: hvac.Client,
    policies: list[str],
    ttl: str | None,
    display_name: str | None,
    renewable: bool | None,
    orphan: bool,
) -> tuple[int, dict[str, object]]:
    return TokenService(client).create_token(policies, ttl, display_name, renewable, orphan)


def lookup_created_token(client: hvac.Client, token_value: str) -> dict[str, object]:
    return TokenService(client).lookup_created_token(token_value)


def delete_token(
    client: hvac.Client,
    token: str | None,
    accessor: str | None,
    revoke_self: bool,
) -> int:
    return TokenService(client).delete_token(token, accessor, revoke_self)
