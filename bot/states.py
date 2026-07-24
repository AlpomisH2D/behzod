from enum import IntEnum, auto


class State(IntEnum):
    WAITING_HUB_MENU = auto()
    WAITING_STYLE_CHOICE = auto()
    WAITING_FORMAT_CHOICE = auto()
    WAITING_SUBLANG_CHOICE = auto()
    WAITING_SCRIPT_SOURCE_CHOICE = auto()
    WAITING_SCRIPT_TEXT = auto()
    WAITING_TRANSCRIPT_CONFIRMATION = auto()
    WAITING_TRANSCRIPT_CORRECTION = auto()
