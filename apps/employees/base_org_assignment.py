from contextlib import contextmanager
from contextvars import ContextVar


_skip_base_org_assignment = ContextVar('skip_base_org_assignment', default=False)


def should_assign_base_org() -> bool:
    return not _skip_base_org_assignment.get()


@contextmanager
def skip_base_org_assignment():
    token = _skip_base_org_assignment.set(True)
    try:
        yield
    finally:
        _skip_base_org_assignment.reset(token)
