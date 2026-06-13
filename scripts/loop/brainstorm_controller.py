import json
import logging
import signal
import sys
import threading
from pathlib import Path

import todo_queue
import work_queue
import brainstorm_session
from watcher import WorkItemsHandler
from watchdog.observers import Observer

CONFIG_PATH = (
    Path.home() / ".config" / "superpowers" / "loop" / "config.json"
)
TODO_ITEMS_DIR = (
    Path.home() / ".config" / "superpowers" / "loop" / "todo-items"
)
TODO_ITEMS_FILE = "todo-items.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
log = logging.getLogger(__name__)


def load_config():
    if not CONFIG_PATH.exists():
        log.error(
            f"Config not found at {CONFIG_PATH}. "
            'Create it with: {"claude_cmd": "claude"}'
        )
        sys.exit(1)
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        log.error(f"Config at {CONFIG_PATH} is not valid JSON: {e}")
        sys.exit(1)


class BrainstormController:
    def __init__(self, config):
        self._config = config
        self._wake = threading.Event()

    def on_file_changed(self):
        self._wake.set()

    def run(self):
        self._wake.set()  # process any pending items at startup
        while True:
            self._wake.wait()
            self._wake.clear()
            self._drain_queue()

    def _drain_queue(self):
        seen = set()
        while True:
            item = todo_queue.next_pending()
            if item is None:
                log.info("Todo queue empty, watching...")
                return
            if item["id"] in seen:
                log.warning(
                    f"Item {item['id']} still pending after abandoned session "
                    "— skipping until next file change"
                )
                return
            seen.add(item["id"])
            log.info(f"Brainstorming item {item['id']}: {item['title']}")
            session_id = brainstorm_session.run(
                item, claude_cmd=self._config.get("claude_cmd", "claude")
            )
            if session_id:
                work_queue.add_item(item, session_id)
                todo_queue.write_done(item)


def main():
    config = load_config()
    if not TODO_ITEMS_DIR.exists():
        log.error(f"todo-items directory not found: {TODO_ITEMS_DIR}")
        sys.exit(1)

    controller = BrainstormController(config)
    handler = WorkItemsHandler(TODO_ITEMS_FILE, controller.on_file_changed)
    observer = Observer()
    observer.schedule(handler, str(TODO_ITEMS_DIR), recursive=False)
    observer.start()
    log.info("Brainstorm controller started. Watching todo-items.json...")

    def shutdown(sig, frame):
        log.info("Shutting down...")
        observer.stop()
        observer.join()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    controller.run()


if __name__ == "__main__":
    main()
