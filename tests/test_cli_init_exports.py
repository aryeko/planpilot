from __future__ import annotations

from planpilot.cli.init import validate_board_url as package_validate_board_url
from planpilot.cli.init.validation import validate_board_url as module_validate_board_url


def test_cli_init_re_exports_validate_board_url() -> None:
    assert package_validate_board_url is module_validate_board_url


def test_cli_init_validate_board_url_wrapper_behavior() -> None:
    assert module_validate_board_url("https://github.com/orgs/acme/projects/1") is True
    assert module_validate_board_url("not-a-board-url") is not True
