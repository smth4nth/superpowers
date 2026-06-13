from pathlib import Path

from watchdog.events import FileSystemEventHandler


class WorkItemsHandler(FileSystemEventHandler):
    def __init__(self, filename, callback):
        self._filename = filename
        self._callback = callback

    def _matches(self, path):
        return Path(path).name == self._filename

    def on_modified(self, event):
        if not event.is_directory and self._matches(event.src_path):
            self._callback()

    def on_created(self, event):
        if not event.is_directory and self._matches(event.src_path):
            self._callback()

    def on_moved(self, event):
        if not event.is_directory and self._matches(event.dest_path):
            self._callback()
