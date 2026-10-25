"""Project exceptions raised by the leaflet layer (ARQUITETURA §13).

Messages are always friendly, in Brazilian Portuguese.
"""

from pallotti_slides.domain.errors import PallottiError


class LeafletError(PallottiError):
    """The PDF could not be read as a liturgical leaflet."""
