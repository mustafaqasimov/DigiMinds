"""Explainable suggestions, never an automatic dispatch or severity assessment."""
import re
import unicodedata


def normalize(text):
    return unicodedata.normalize('NFC', text).lower().replace('i\u0307', 'i').translate(
        str.maketrans('əıöüçşğ', 'eioucsg'))


# Match inflected Azerbaijani words, including common ASCII phone spelling.
PATTERNS = {
    'fire': [r'\byangin(?!sondur)\w*', r'\balov\w*', r'\btustu\w*', r'\byanir\w*', r'\byanmaqda\b'],
    'collapse': [r'\bdaginti\w*', r'\bucqun\w*', r'\b(?:bina|ev|divar|tavan|kopru)\w*\s+(?:ucub|ucdu|cokub|cokdu|dagilib)\w*',
                 r'\b(?:daginti|beton|divar)\w*\s+altinda\b'],
    'flood': [r'\bsel\b', r'\bsubasma\w*', r'\bsu\s+bas(?:ib|ir|di|masi)\w*',
              r'\bdasqin\w*'],
    'medical': [r'\btibbi\s+yardim\b', r'\btecili\s+yardim\b', r'\byarali\w*', r'\bqanaxma\w*',
                r'\bqan\s+(?:axir|itirir)\w*', r'\bnefes\s+ala\s+bilmir\w*', r'\bnefes\s+(?:almir|catmir)\w*',
                r'\bhusunu\s+itir\w*', r'\bhussuz\w*', r'\burek\s+tutma\w*', r'\byaralan\w*'],
}
NEGATION = re.compile(r'^(?:\s+\w+){0,2}\s+(?:yox\w*|deyil\w*|olmayib|olmadi|olmur|basmayib|basmir)\b')


def classify(text):
    clean = normalize(text)
    matches = {}
    # A negation applies within its clause, not across "amma/lakin" or punctuation.
    for clause in re.split(r'[.!?;,\n]|\b(?:amma|lakin|ancaq)\b', clean):
        for category, patterns in PATTERNS.items():
            for pattern in patterns:
                for match in re.finditer(pattern, clause):
                    tail = clause[match.end():]
                    if NEGATION.match(tail) or re.match(r'\s+olmadig\w*', tail):
                        continue
                    matches.setdefault(category, set()).add(match.group())
    categories = list(matches)
    return {'suggested_type': categories[0] if len(categories) == 1 else None,
            'candidates': categories, 'ambiguous': len(categories) > 1,
            'evidence': {k: sorted(v) for k, v in matches.items()}}


def pace(text, speech_seconds):
    words = len(re.findall(r'[^\W\d_]+(?:[’\x27-][^\W\d_]+)*', text, re.UNICODE))
    # A few words do not give a stable rate. This is descriptive, not emotional triage.
    return round(words * 60 / speech_seconds) if words >= 5 and speech_seconds >= 2 else None
