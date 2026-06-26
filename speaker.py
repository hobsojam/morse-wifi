from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SpeakerInfo:
    id: str
    name: str

    def __str__(self) -> str:
        return self.name


class Speaker(ABC):
    preferred_format: str = "wav"

    @abstractmethod
    def discover(self) -> list["SpeakerInfo"]:
        ...

    @abstractmethod
    def play_url(self, speaker: "SpeakerInfo", url: str) -> None:
        ...

    @abstractmethod
    def stop(self, speaker: "SpeakerInfo") -> None:
        ...

    def get_transport_state(self, speaker: "SpeakerInfo") -> str:
        return "unknown"

    def get_debug_info(self, speaker: "SpeakerInfo") -> dict:
        return {}
