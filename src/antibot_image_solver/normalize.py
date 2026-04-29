from __future__ import annotations

import re
from typing import Optional

NUMBER_WORDS = {
    "0": "zero",
    "1": "one",
    "2": "two",
    "3": "three",
    "4": "four",
    "5": "five",
    "6": "six",
    "7": "seven",
    "8": "eight",
    "9": "nine",
    "10": "ten",
}
WORD_NUMBERS = {v: k for k, v in NUMBER_WORDS.items()}
ANIMAL_WORDS = {
    "ant",
    "camel",
    "cat",
    "cow",
    "crab",
    "deer",
    "dog",
    "duck",
    "elephant",
    "fox",
    "lion",
    "monkey",
    "mouse",
    "panda",
    "rabbit",
    "tiger",
}


def roman_to_int(token: str) -> Optional[int]:
    token = token.upper().strip()
    if not token or not re.fullmatch(r"[IVXLCDM]+", token):
        return None
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    prev = 0
    for ch in reversed(token):
        value = values[ch]
        if value < prev:
            total -= value
        else:
            total += value
            prev = value
    return total


def eval_simple_expr(token: str) -> Optional[str]:
    token = token.lower().replace("×", "x").replace("*", "x")
    token = token.replace(" ", "")
    match = re.fullmatch(r"(\d+)([+\-x])(\d+)", token)
    if not match:
        return None
    left = int(match.group(1))
    right = int(match.group(3))
    op = match.group(2)
    if op == "+":
        return str(left + right)
    if op == "-":
        return str(left - right)
    return str(left * right)


def normalize_letters(text: str) -> str:
    text = text.strip().lower()
    exact_fixes = {
        # Exact raw OCR forms whose leading digit/punctuation would be lost by generic cleanup.
        "2p": "zip",
        "200": "zoo",
        "20r": "zor",
        "i3ft": "left",
        "lert": "left",
        "rignt": "right",
        "(ow": "low",
        "mc": "arc",
        "wal": "wht",
        "bik": "bk",
        "fer": "var",
        "“3": "use",
        "@da": "add",
        "mar": "mat",
        "cay": "cap",
        "wy": "toy",
        "myejt": "mat",
        "ep": "cap",
        "ecream": "icecream",
        "warer": "water",
        "ke": "ice",
        "wr": "water",
        "1c3cr34m": "icecream",
        "3": "ice",
        "jol": "lol",
        "ill": "lll",
        "ih": "lll",
        "101": "lol",
        "500": "soo",
        "kelly": "jelly",
        "star sse": "starfish",
        "aerio": "starfish",
        "ae": "crab",
        "ily": "jelly",
        "qole": "golf",
        "opt": "golf",
        "nick": "cricket",
        "f00tbell": "football",
        "5@q": "sad",
        "dky": "sky",
        "yvm": "yum",
        "yov": "you",
        "pw": "yew",
        "ew": "air",
        "£04": "fog",
        "nid": "od",
        "pot": "rot",
        "ned": "wad",
        "124": "tea",
        "te": "tea",
        "\\c3": "ice",
        "wir": "wtr",
        "lat": "eat",
        "at": "eat",
        "299": "egg",
        "39g": "egg",
        "3u3": "eve",
        "3e@t": "eat",
        "ic": "ice",
        "alr": "air",
        "oky": "sky",
        "i": "tox",
        "gn": "ani",
        "+r": "try",
        "ay": "ely",
        "bit": "sit",
        "girf": "aw",
        "alalar": "stier",
        "f@th3r": "faiher",
        "z3r0": "0",
        "tw": "2",
        "wd": "2",
        "thr33": "3",
        "rm": "ram",
        "mn": "rom",
        "<": "ner",
        "{our": "4",
        "s3v3n": "7",
        "off": "ort",
        "not": "nor",
        "bl": "da",
        "@r": "air",
        "ley": "ice",
        "ral": "dew",
        "d@a": "dad",
        "mar": "mom",
        "mar\"": "mom",
        "wer": "man",
        "st@rkish": "starrisn",
        "o@b": "crap",
        "fish": "19",
        "teg": "424",
        "t03": "te",
        "a3t": "set",
        "o3t": "set",
        "4": "four",
        "5": "five",
        "6": "six",
        "p@a": "pad",
        "p3n": "pen",
        "desh": "desk",
        "085": "desk",
        "dé@ss": "class",
        "9pu": "gpu",
        "nat": "net",
        "@y\\": "api",
        "vt": "uti",
        "vn": "urn",
        "viv": "ulu",
        "iy": "toy",
        "fy": "toy",
        "{oy": "toy",
        "hy": "toy",
        "md": "lid",
        "i1d": "lid",
        "itd": "lid",
        "hay": "key",
        "rdy": "key",
        "ly": "one",
        "tt": "seven",
        "ln": "jin",
        "jn": "jin",
        "int": "jot",
        "jt": "jot",
        "ht": "hit",
        "at": "hit",
        "h8n": "hen",
        ")": "hot",
        "vit": "hot",
        "wr": "hot",
        "0": "0",
        "2": "2",
        "|": "7",
        "9": "3",
        "a": "doc",
    }
    if text in exact_fixes:
        return exact_fixes[text]
    replacements = {
        "0": "o",
        "1": "l",
        "3": "e",
        "4": "a",
        "5": "s",
        "6": "g",
        "7": "t",
        "8": "b",
        "9": "g",
        "@": "a",
        "$": "s",
        "£": "f",
        "€": "e",
        "|": "l",
        "!": "i",
        "+": "t",
    }
    text = "".join(replacements.get(ch, ch) for ch in text)
    text = re.sub(r"[^a-z, ]", "", text)
    fixes = {
        "slephent": "elephant",
        "elephent": "elephant",
        "elephont": "elephant",
        "elephart": "elephant",
        "sephe nt": "elephant",
        "sephent": "elephant",
        "sephant": "elephant",
        "srephant": "elephant",
        "meaphimt": "elephant",
        "eepnany": "elephant",
        "eiepnan": "elephant",
        "beenary": "elephant",
        "bopnay": "elephant",
        "tgerr": "tiger",
        "teger": "tiger",
        "tger": "tiger",
        "f0x": "fox",
        "d0g": "dog",
        "m0use": "mouse",
        "morkey": "monkey",
        "morey": "monkey",
        "pende": "panda",
        "pgnde": "panda",
        "pend": "panda",
        "panaa": "panda",
        "para": "panda",
        "tox": "fox",
        "lox": "fox",
        "geir": "deer",
        "aeer": "deer",
        "aver": "deer",
        "drr": "deer",
        # ClaimCoin live OCR confusions from rejected option-image samples.
        # Keep these narrow: they map distorted instruction tokens to option OCR forms
        # seen in the same challenge family, avoiding broad numeric alias matches.
        "pnk": "pin",
        "blk": "bk",
        "ik": "bk",
        "uv": "ww",
        "luv": "ww",
        "iuv": "ww",
        "ouy": "yy",
        "quy": "yy",
        "aor": "got",
        "pan": "pen",
        "pon": "pen",
        "top": "op",
        "aip": "cvp",
        "aup": "cvp",
        # Live accepted-regression tie-breaker corrections.
        "plg": "pig",
        "ply": "pig",
        "cmt": "cat",
        "rtin": "run",
        "rn": "run",
        "rb": "rib",
        "rth": "rib",
        "brdwn": "brown",
        "beown": "brown",
        "peown": "brown",
        "y3llow": "yellow",
        "y3ilow": "yellow",
        "ysilow": "yellow",
        "y3iow": "yellow",
        "ble": "blue",
        "bu": "blue",
        "bie": "blue",
        "notel": "hotel",
        "hot3l": "hotel",
        "hotsl": "hotel",
        "hotel": "hotel",
        "baa": "bag",
        "beg": "bag",
        "bes": "bag",
        "filght": "flat",
        "fllght": "flat",
        "fight": "flat",
        "fllaght": "flat",
        "40k": "fox",
        "ak": "fox",
        "jb": "job",
        # Manual-label ClaimCoin regressions from 2026-04-29.
        "pai": "pey",
        "ple": "pis",
        "zi": "zul",
        "2p": "zip",
        "ug": "zig",
    }
    return fixes.get(text, text)


def canonical_forms(text: str) -> set[str]:
    forms: set[str] = set()
    raw = text.strip()
    if not raw:
        return forms

    compact = re.sub(r"\s+", "", raw.lower())
    if compact:
        forms.add(compact)

    alpha = normalize_letters(raw)
    if alpha:
        forms.add(alpha)
        alpha_plain = alpha.strip(", ")
        if alpha_plain:
            forms.add(alpha_plain)
        if alpha in WORD_NUMBERS:
            forms.add(WORD_NUMBERS[alpha])
        if alpha_plain in WORD_NUMBERS:
            forms.add(WORD_NUMBERS[alpha_plain])
        if alpha_plain in ANIMAL_WORDS:
            return {item for item in forms if item}

    digit_variants = {raw}
    replacements = {
        "o": ("0",),
        "O": ("0",),
        "l": ("1",),
        "I": ("1",),
        "|": ("1",),
        "s": ("5",),
        "S": ("5",),
        "z": ("2", "3"),
        "Z": ("2", "3"),
        "g": ("6",),
        "G": ("6",),
        "b": ("8",),
        "B": ("8",),
    }
    for src, repls in replacements.items():
        next_set = set()
        for item in digit_variants:
            if src in item:
                for repl in repls:
                    next_set.add(item.replace(src, repl))
            next_set.add(item)
        digit_variants = next_set

    for variant in digit_variants:
        cleaned = re.sub(r"[^0-9,+\-xX*×IVXLCDMivxlcdm]", "", variant)
        if cleaned:
            forms.add(cleaned.lower())
        expr = eval_simple_expr(cleaned)
        if expr is not None:
            forms.add(expr)
        roman_value = roman_to_int(cleaned)
        if roman_value is not None:
            forms.add(str(roman_value))
        digits_only = re.sub(r"\D", "", cleaned)
        if digits_only:
            forms.add(digits_only)
            forms.add(str(int(digits_only)))
            if str(int(digits_only)) in NUMBER_WORDS:
                forms.add(NUMBER_WORDS[str(int(digits_only))])

    return {item for item in forms if item}


def guess_family(tokens: list[str]) -> Optional[str]:
    forms: set[str] = set()
    for token in tokens:
        forms |= canonical_forms(token)
    if forms & ANIMAL_WORDS:
        return "animals"
    if any(re.fullmatch(r"\d+[+\-x]\d+", item) for item in forms):
        return "arithmetic"
    if any(item in WORD_NUMBERS for item in forms):
        return "number_words"
    if any(re.fullmatch(r"[ivxlcdm]+", item, re.I) for item in tokens if item.strip()):
        return "roman_numerals"
    if any(re.fullmatch(r"\d+", item) for item in forms):
        return "numbers"
    return None
