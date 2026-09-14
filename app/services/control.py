class SiftCancelled(Exception):
    """Cooperative stop at a safe boundary, without undoing completed actions."""


def check_cancelled(cancel):
    if cancel is not None and cancel.is_set():
        raise SiftCancelled()
