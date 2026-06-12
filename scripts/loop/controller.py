import json
import logging
import signal
import sys
import threading
import time
from pathlib import Path

import work_queue
import session
from watcher import WorkItemsHandler
from watchdog.observers import Observer

CONFIG_PATH = (
    Path.home() / ".config" / "superpowers" / "loop" / "config.json"
)
WORK_ITEMS_DIR = (
    Path.home() / ".config" / "superpowers" / "loop" / "work-items"
)
WORK_ITEMS_FILE = "work-items.json"

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


class Controller:
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
            item = work_queue.next_pending()
            if item is None:
                log.info("Queue empty, watching...")
                return
            if item["id"] in seen:
                log.warning(f"Item {item['id']} still pending after failure — skipping until next file change")
                return
            seen.add(item["id"])
            log.info(f"Processing item {item['id']}: {item['title']}")
            exit_code = session.run(
                item, claude_cmd=self._config.get("claude_cmd", "claude")
            )
            if exit_code != 0:
                reason = (
                    f"project_dir not found: {item['project_dir']}"
                    if exit_code == -1
                    else f"claude binary not found: {self._config.get('claude_cmd', 'claude')}"
                    if exit_code == -2
                    else f"claude exited with code {exit_code}"
                )
                log.warning(f"Item {item['id']} failed: {reason}")
                work_queue.write_needs_human(item, reason=reason)


def main():
    config = load_config()
    if not WORK_ITEMS_DIR.exists():
        log.error(f"work-items directory not found: {WORK_ITEMS_DIR}")
        sys.exit(1)

    controller = Controller(config)
    handler = WorkItemsHandler(WORK_ITEMS_FILE, controller.on_file_changed)
    observer = Observer()
    observer.schedule(handler, str(WORK_ITEMS_DIR), recursive=False)
    observer.start()
    log.info("Loop controller started. Watching work-items.json...")

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
