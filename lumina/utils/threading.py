import threading
from collections.abc import Callable

from gi.repository import GLib


def run_in_thread(
    work: Callable[[], object],
    on_success: Callable[[object], None],
    on_error: Callable[[BaseException], None],
) -> None:
    def worker() -> None:
        try:
            result = work()
        except Exception as exc:
            idle(on_error, exc)
            return
        idle(on_success, result)

    threading.Thread(target=worker, daemon=True).start()


def idle(callback: Callable[..., None], *args: object) -> None:
    def wrapper() -> bool:
        callback(*args)
        return False

    GLib.idle_add(wrapper)
