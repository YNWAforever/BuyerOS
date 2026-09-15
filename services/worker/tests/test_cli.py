import pytest

from buyeros_worker import cli


def test_parser_requires_a_command():
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args([])


def test_parser_accepts_dispatch_and_sweep():
    dispatch = cli.build_parser().parse_args(["dispatch", "--limit", "3", "--owner", "me"])
    assert dispatch.command == "dispatch"
    assert dispatch.limit == 3
    assert dispatch.owner == "me"

    sweep = cli.build_parser().parse_args(["sweep"])
    assert sweep.command == "sweep"
    assert sweep.limit is None
    assert sweep.owner is None


def test_main_runs_the_selected_command(monkeypatch, capsys):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda command, limit, owner: calls.append((command, limit, owner)) or ["job:1"])
    assert cli.main(["dispatch", "--limit", "2", "--owner", "me"]) == 0
    assert calls == [("dispatch", 2, "me")]
    assert "dispatch: published 1 intents" in capsys.readouterr().out


def test_main_defaults_the_owner_from_the_command(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "_run", lambda command, limit, owner: calls.append((command, limit, owner)) or [])
    cli.main(["sweep"])
    assert calls == [("sweep", None, "buyeros-sweep")]
