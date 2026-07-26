import typer


ANSI_BLUE = "\033[34m"
ANSI_RED = "\033[31m"
ANSI_GREEN = "\033[32m"
ANSI_RESET = "\033[0m"


def stringify(value: object) -> str:
    if value is None:
        return ""
    return str(value)


def compact(value: object) -> str:
    return stringify(value).replace("\n", " ").strip()


def print_framed_lines(title: str, lines: list[str], color: str) -> None:
    content_lines = lines or [""]
    content_width = max(len(line) for line in content_lines)

    # Keep a single consistent inner width for both title and content.
    inner_width = max(content_width, len(title) + 2)
    border_fill_len = max(inner_width - len(title) - 1, 1)

    top_border = "╭─ " + title + " " + ("─" * border_fill_len) + "╮"
    bottom_border = "╰" + ("─" * (len(top_border) - 2)) + "╯"

    typer.echo(f"{color}{top_border}{ANSI_RESET}")
    for line in content_lines:
        typer.echo(f"{color}│ {line.ljust(inner_width)} │{ANSI_RESET}")
    typer.echo(f"{color}{bottom_border}{ANSI_RESET}")


def print_box(title: str, message: str, color: str) -> None:
    print_framed_lines(title, [message], color)


def print_error(message: str) -> None:
    print_box("Error", message, ANSI_RED)


def print_success(message: str) -> None:
    print_box("Succes", message, ANSI_GREEN)


def print_blue_separator(width: int = 80) -> None:
    typer.echo(f"{ANSI_BLUE}{'─' * width}{ANSI_RESET}")


def print_table(title: str, headers: list[str], rows: list[list[str]]) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        for idx, cell in enumerate(row):
            widths[idx] = max(widths[idx], len(cell))

    def format_row(row: list[str]) -> str:
        parts = [row[idx].ljust(widths[idx]) for idx in range(len(headers))]
        return "  ".join(parts)

    separator = "  ".join("-" * width for width in widths)
    table_lines = [format_row(headers), separator]
    table_lines.extend(format_row(row) for row in rows)

    print_framed_lines(title, table_lines, ANSI_BLUE)
