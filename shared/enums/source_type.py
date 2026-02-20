from enum import Enum

class SourceType(str, Enum):
    MANUAL = "manual"
    WEB_CLIP = "web_clip"
    PDF = "pdf"
    AUDIO = "audio"