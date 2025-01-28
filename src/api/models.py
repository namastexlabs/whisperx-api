from enum import Enum


class LanguageEnum(str, Enum):
    ar = "ar"  # Arabic
    eu = "eu"  # Basque
    ca = "ca"  # Catalan
    zh = "zh"  # Chinese
    hr = "hr"  # Croatian
    cs = "cs"  # Czech
    da = "da"  # Danish
    nl = "nl"  # Dutch
    en = "en"  # English
    fi = "fi"  # Finnish
    fr = "fr"  # French
    gl = "gl"  # Galician
    ka = "ka"  # Georgian
    de = "de"  # German
    el = "el"  # Greek
    he = "he"  # Hebrew
    hi = "hi"  # Hindi
    hu = "hu"  # Hungarian
    it = "it"  # Italian
    ja = "ja"  # Japanese
    ko = "ko"  # Korean
    lv = "lv"  # Latvian
    ml = "ml"  # Malayalam
    no = "no"  # Norwegian (Bokmål)
    nn = "nn"  # Norwegian (Nynorsk)
    fa = "fa"  # Persian
    pl = "pl"  # Polish
    pt = "pt"  # Portuguese
    ro = "ro"  # Romanian
    ru = "ru"  # Russian
    sk = "sk"  # Slovak
    sl = "sl"  # Slovenian
    es = "es"  # Spanish
    te = "te"  # Telugu
    tr = "tr"  # Turkish
    uk = "uk"  # Ukrainian
    ur = "ur"  # Urdu
    vi = "vi"  # Vietnamese


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
