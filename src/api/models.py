from enum import Enum


class LanguageEnum(str, Enum):
    af = "af"  # Afrikaans
    ar = "ar"  # Arabic
    hy = "hy"  # Armenian
    az = "az"  # Azerbaijani
    be = "be"  # Belarusian
    bs = "bs"  # Bosnian
    bg = "bg"  # Bulgarian
    ca = "ca"  # Catalan
    zh = "zh"  # Chinese
    hr = "hr"  # Croatian
    cs = "cs"  # Czech
    da = "da"  # Danish
    nl = "nl"  # Dutch
    en = "en"  # English
    et = "et"  # Estonian
    fi = "fi"  # Finnish
    fr = "fr"  # French
    gl = "gl"  # Galician
    de = "de"  # German
    el = "el"  # Greek
    he = "he"  # Hebrew
    hi = "hi"  # Hindi
    hu = "hu"  # Hungarian
    is_ = "is"  # Icelandic
    id = "id"  # Indonesian
    it = "it"  # Italian
    ja = "ja"  # Japanese
    kn = "kn"  # Kannada
    kk = "kk"  # Kazakh
    ko = "ko"  # Korean
    lv = "lv"  # Latvian
    lt = "lt"  # Lithuanian
    mk = "mk"  # Macedonian
    ms = "ms"  # Malay
    mr = "mr"  # Marathi
    mi = "mi"  # Maori
    ne = "ne"  # Nepali
    no = "no"  # Norwegian
    fa = "fa"  # Persian
    pl = "pl"  # Polish
    pt = "pt"  # Portuguese
    ro = "ro"  # Romanian
    ru = "ru"  # Russian
    sr = "sr"  # Serbian
    sk = "sk"  # Slovak
    sl = "sl"  # Slovenian
    es = "es"  # Spanish
    sw = "sw"  # Swahili
    sv = "sv"  # Swedish
    tl = "tl"  # Tagalog
    ta = "ta"  # Tamil
    th = "th"  # Thai
    tr = "tr"  # Turkish
    uk = "uk"  # Ukrainian
    ur = "ur"  # Urdu
    vi = "vi"  # Vietnamese
    cy = "cy"  # Welsh


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
