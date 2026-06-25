from speaker import Speaker, SpeakerInfo


class DlnaBackend(Speaker):
    def discover(self) -> list[SpeakerInfo]:
        raise NotImplementedError("DLNA backend not yet implemented")

    def play_url(self, speaker: SpeakerInfo, url: str) -> None:
        raise NotImplementedError("DLNA backend not yet implemented")

    def stop(self, speaker: SpeakerInfo) -> None:
        raise NotImplementedError("DLNA backend not yet implemented")
