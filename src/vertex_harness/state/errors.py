"""Errors raised while reading or updating repository state."""


class StateError(RuntimeError):
    """Base class for repository-state failures."""


class StateNotFoundError(StateError):
    """Raised when a repository has not been initialized."""


class StateAlreadyExistsError(StateError):
    """Raised when initialization would replace existing state."""


class StateFormatError(StateError):
    """Raised when stored data cannot produce a valid domain model."""


class StateLockedError(StateError):
    """Raised when another writer holds the repository lock."""


class RevisionConflictError(StateError):
    """Raised when a caller attempts to update an outdated snapshot."""

    def __init__(self, expected: int, actual: int) -> None:
        super().__init__(f"state revision changed: expected {expected}, found {actual}")
        self.expected = expected
        self.actual = actual
