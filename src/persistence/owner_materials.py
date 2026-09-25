"""Merge activated owner materials into Business DNA for AI wording only."""

from typing import Any, Mapping

from src.persistence.repositories import UnitOfWork


def merge_active_owner_materials(
    uow: UnitOfWork,
    business_id: str,
    configuration: Mapping[str, Any],
) -> dict[str, Any]:
    """Return a DNA copy. The packet is not dumped here.

    Presentation picks one activated item as a business fact. Putting the
    whole library into description would let the mouth invent creative.
    """
    del uow, business_id
    return _plain_map(configuration)


def _plain_map(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _plain_map(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_map(item) for item in value]
    return value
