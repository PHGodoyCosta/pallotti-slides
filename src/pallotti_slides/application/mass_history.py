"""Mass history use cases (SPEC F13): list saved Masses and load one back."""

from pallotti_slides.db.repositories import MassRepository, MassSummary
from pallotti_slides.domain.models import Mass

__all__ = ["MassHistory", "MassSummary"]


class MassHistory:
    """Read side of the Mass repository, as the History page needs it."""

    def __init__(self, repo: MassRepository) -> None:
        self._repo = repo

    def list(self, limit: int = 50) -> list[MassSummary]:
        return self._repo.list(limit)

    def get(self, mass_id: int) -> Mass:
        return self._repo.get(mass_id)
