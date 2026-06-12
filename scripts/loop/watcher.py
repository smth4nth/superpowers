from watchdog.events import FileSystemEventHandler


class WorkItemsHandler(FileSystemEventHandler):
    def __init__(self, filename, callback):
        self._filename = filename
        self._callback = callback

    def on_modified(self, event):
        if not event.is_directory and event.src_path.endswith(self._filename):
            self._callback()
