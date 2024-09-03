from enum import Enum


class LanguageEnum(str, Enum):
    pt = "pt"
    en = "en"
    es = "es"
    fr = "fr"
    it = "it"
    de = "de"


class ModelEnum(str, Enum):
    tiny = "tiny"
    small = "small"
    base = "base"
    medium = "medium"
    largeV2 = "large-v2"
    largeV3 = "large-v3"


class ResponseTypeEnum(str, Enum):
    json = "json"
    file = "file"
