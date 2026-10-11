"""Always attempt every teardown for resources created by the owned capture."""
import json


def cleanup_all(actions):
    failures = []
    for action in actions:
        try:
            action()
        except BaseException as exc:
            failures.append(exc)
    if failures:
        raise failures[0]


def capture_then_cleanup(folder, capture, actions):
    try:
        with (folder / 'capture.json').open('x', encoding='utf-8') as file:
            json.dump(capture, file, indent=2, allow_nan=False)
            file.write('\n')
    finally:
        cleanup_all(actions)
