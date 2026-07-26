import hvac
from hvac import exceptions as hvac_exceptions

from app.commands.output import compact, print_error, print_success, stringify


class PolicyService:
    def __init__(self, client: hvac.Client) -> None:
        self.client = client

    def list_policy_names(self) -> list[str]:
        try:
            policies = self.client.sys.list_policies().get("data", {}).get("policies", [])
        except hvac_exceptions.Forbidden:
            print_error("Permission denied: cannot list policies")
            return []
        except hvac_exceptions.InvalidPath:
            return []
        return sorted(stringify(name) for name in policies if stringify(name))

    def read_policy(self, name: str) -> tuple[int, dict[str, object]]:
        try:
            data = self.client.sys.read_policy(name)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot read policy '{name}'")
            return 1, {}
        except hvac_exceptions.InvalidPath:
            return 2, {}

        return 0, data if isinstance(data, dict) else {}

    def create_or_update_policy(self, name: str, rules: str, *, require_exists: bool | None) -> int:
        cleaned_name = name.strip()
        if not cleaned_name:
            print_error("Policy name cannot be empty")
            return 1

        cleaned_rules = rules.strip()
        if not cleaned_rules:
            print_error("Policy rules cannot be empty")
            return 1

        read_code, _ = self.read_policy(cleaned_name)
        exists = read_code == 0

        if require_exists is True and not exists:
            print_error(f"Policy not found: {cleaned_name}")
            return 1
        if require_exists is False and exists:
            print_error(f"Policy already exists: {cleaned_name}")
            return 1
        if read_code == 1:
            return 1

        try:
            self.client.sys.create_or_update_policy(name=cleaned_name, policy=cleaned_rules)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot write policy '{cleaned_name}'")
            return 1
        except hvac_exceptions.InvalidRequest as error:
            print_error(compact(error))
            return 1

        action = "updated" if require_exists else "created"
        print_success(f"Policy {action}: {cleaned_name}")
        return 0

    def delete_policy(self, name: str) -> int:
        cleaned_name = name.strip()
        if not cleaned_name:
            print_error("Policy name cannot be empty")
            return 1

        read_code, _ = self.read_policy(cleaned_name)
        if read_code == 1:
            return 1
        if read_code == 2:
            print_error(f"Policy not found: {cleaned_name}")
            return 1

        try:
            self.client.sys.delete_policy(cleaned_name)
        except hvac_exceptions.Forbidden:
            print_error(f"Permission denied: cannot delete policy '{cleaned_name}'")
            return 1
        except hvac_exceptions.InvalidRequest as error:
            print_error(compact(error))
            return 1

        print_success(f"Policy deleted: {cleaned_name}")
        return 0


def list_policy_names(client: hvac.Client) -> list[str]:
    return PolicyService(client).list_policy_names()


def read_policy(client: hvac.Client, name: str) -> tuple[int, dict[str, object]]:
    return PolicyService(client).read_policy(name)


def create_or_update_policy(
    client: hvac.Client,
    name: str,
    rules: str,
    *,
    require_exists: bool | None,
) -> int:
    return PolicyService(client).create_or_update_policy(name, rules, require_exists=require_exists)


def delete_policy(client: hvac.Client, name: str) -> int:
    return PolicyService(client).delete_policy(name)
