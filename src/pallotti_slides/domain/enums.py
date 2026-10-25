"""Domain enums. Stored values (JSON, database) are English and lowercase."""

from enum import StrEnum

_MOMENT_LABELS: dict[str, str] = {
    "mantra": "Mantra",
    "entrance": "Canto de Entrada",
    "penitential_act": "Ato Penitencial",
    "gloria": "Glória",
    "acclamation": "Aclamação",
    "offertory": "Ofertório",
    "communion": "Comunhão",
    "post_communion": "Pós-Comunhão",
    "recessional": "Saída",
}


class LiturgicalSeason(StrEnum):
    """Liturgical season of the celebration."""

    ADVENT = "advent"
    CHRISTMAS = "christmas"
    LENT = "lent"
    PASCHAL_TRIDUUM = "paschal_triduum"
    EASTER = "easter"
    ORDINARY_TIME = "ordinary_time"


class SongMoment(StrEnum):
    """Moments of the Mass that take a song. Declaration order = order in the Mass."""

    MANTRA = "mantra"
    ENTRANCE = "entrance"
    PENITENTIAL_ACT = "penitential_act"
    GLORIA = "gloria"
    ACCLAMATION = "acclamation"
    OFFERTORY = "offertory"
    COMMUNION = "communion"
    POST_COMMUNION = "post_communion"
    RECESSIONAL = "recessional"

    @property
    def label(self) -> str:
        """User-facing label in Portuguese (the one printed on the slides)."""
        return _MOMENT_LABELS[self.value]


class EucharisticPrayer(StrEnum):
    """Eucharistic prayers available in the template."""

    I = "I"  # noqa: E741
    II = "II"
    III = "III"
    IV = "IV"


class StanzaType(StrEnum):
    """Kind of stanza of a song."""

    VERSE = "verse"
    CHORUS = "chorus"


class SongSource(StrEnum):
    """Where the lyrics came from."""

    LETRAS_MUS = "letras_mus"
    CIFRA_CLUB = "cifra_club"
    MANUAL = "manual"
    OTHER = "other"
