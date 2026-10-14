import os
import signal
import subprocess
import threading
from collections.abc import Callable


class ProcessRunner:
    def __init__(self) -> None:
        self._process: subprocess.Popen[str] | None = None
        self._cancel = threading.Event()
        self._lock = threading.Lock()

    def start(
        self,
        argv: list[str],
        on_line: Callable[[str], None],
        on_exit: Callable[[int], None],
    ) -> None:
        self._cancel.clear()
        threading.Thread(
            target=self._run,
            args=(argv, on_line, on_exit),
            daemon=True,
        ).start()

    def cancel(self) -> None:
        self._cancel.set()
        self._terminate()

    def _terminate(self) -> None:
        with self._lock:
            process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (ProcessLookupError, PermissionError, OSError):
            try:
                process.terminate()
            except OSError:
                return

    def _run(
        self,
        argv: list[str],
        on_line: Callable[[str], None],
        on_exit: Callable[[int], None],
    ) -> None:
        code = -1
        try:
            process = subprocess.Popen(
                argv,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
        except OSError as exc:
            on_line(f"Failed to start: {exc}\n")
            on_exit(-1)
            return
        with self._lock:
            self._process = process
        assert process.stdout is not None
        try:
            for line in process.stdout:
                on_line(line)
                if self._cancel.is_set():
                    break
            if self._cancel.is_set():
                self._terminate()
            code = process.wait()
        except Exception as exc:
            on_line(f"\nError while reading output: {exc}\n")
            self._terminate()
            code = process.wait()
        finally:
            with self._lock:
                if self._process is process:
                    self._process = None
        on_exit(code)
