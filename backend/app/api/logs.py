import logging
import multiprocessing
from collections import deque
from logging.handlers import QueueHandler, QueueListener
from threading import Lock
from fastapi import APIRouter

router = APIRouter(prefix="/logs", tags=["logs"])

_lock = Lock()
_buf: deque = deque(maxlen=500)
_seq = 0

# Queue for subprocess → parent log forwarding
_log_queue: multiprocessing.Queue = multiprocessing.Queue(-1)
_listener: QueueListener | None = None


class BufferHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        global _seq
        try:
            msg = self.format(record)
            with _lock:
                _seq += 1
                _buf.append({
                    "id": _seq,
                    "t": round(record.created, 3),
                    "level": record.levelname,
                    "logger": record.name.replace("app.", "").replace("app", "root"),
                    "msg": msg,
                })
        except Exception:
            pass


_handler = BufferHandler()
_handler.setFormatter(logging.Formatter("%(message)s"))


def setup_log_buffer() -> None:
    global _listener
    logging.getLogger("app").addHandler(_handler)
    # Forward log records sent from scan subprocesses via queue
    _listener = QueueListener(_log_queue, _handler, respect_handler_level=True)
    _listener.start()


def get_log_queue() -> multiprocessing.Queue:
    """Return the shared queue subprocesses should send log records to."""
    return _log_queue


@router.get("")
def get_logs(since: int = 0):
    with _lock:
        return [e for e in _buf if e["id"] > since]
