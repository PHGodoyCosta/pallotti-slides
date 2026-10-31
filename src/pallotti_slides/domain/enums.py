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
    "recessional": "Canto de Saída",
}

#: Prefix of the prayer id -> family name shown to the user (MODELO_PPTX.md §5).
_PRAYER_FAMILIES: dict[str, str] = {
    "R": "Reconciliação",
    "DC": "Diversas Circunstâncias",
    "C": "Crianças",
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
    """Eucharistic prayers available in the template.

    Values are the tag ids (MODELO_PPTX.md §5), with a space where the file name has ``_``:
    ``DC`` = "Diversas Circunstâncias", ``R`` = "Reconciliação", ``C`` = "Crianças".
    """

    I = "I"  # noqa: E741
    II = "II"
    III = "III"
    IV = "IV"
    V = "V"
    RECONCILIATION_I = "R I"
    RECONCILIATION_II = "R II"
    VARIOUS_NEEDS_I = "DC I"
    VARIOUS_NEEDS_II = "DC II"
    VARIOUS_NEEDS_III = "DC III"
    VARIOUS_NEEDS_IV = "DC IV"
    CHILDREN_I = "C I"
    CHILDREN_II = "C II"
    CHILDREN_III = "C III"

    @property
    def label(self) -> str:
        """Display text in Portuguese."""
        prefix, _, number = self.value.partition(" ")
        if not number:
            return self.value
        return f"{_PRAYER_FAMILIES[prefix]} {number}"


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
