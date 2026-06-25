from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class SpeakerInfo:
    id: str
    name: str

    def __str__(self) -> str:
        return self.name


class Speaker(ABC):
    preferred_format: str = "mp3"

    @abstractmethod
    def discover(self) -> list[SpeakerInfo]:
        ...

    @abstractmethod
    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        ...

    @abstractmethod
    def stop(self, speaker: SpeakerInfo) -> None:
        ...
