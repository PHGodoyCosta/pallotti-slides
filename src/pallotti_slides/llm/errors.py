"""Project exceptions raised by the LLM layer (ARQUITETURA §13).

Messages are always friendly, in Brazilian Portuguese.
"""

from pallotti_slides.domain.errors import PallottiError


class LLMError(PallottiError):
    """The language model could not be used (no key, network, refusal...)."""
