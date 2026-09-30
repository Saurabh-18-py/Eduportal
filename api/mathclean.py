import re

_SUP = str.maketrans('0123456789+-n', '⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻ⁿ')
_SUB = str.maketrans('0123456789', '₀₁₂₃₄₅₆₇₈₉')
_SUP_OK = set('0123456789+-n')

_SYMBOLS = {
    'times': '×', 'cdot': '·', 'div': '÷', 'pm': '±',
    'leq': '≤', 'le': '≤', 'geq': '≥', 'ge': '≥', 'neq': '≠', 'ne': '≠',
    'approx': '≈', 'infty': '∞', 'pi': 'π', 'theta': 'θ', 'alpha': 'α',
    'beta': 'β', 'gamma': 'γ', 'delta': 'δ', 'lambda': 'λ', 'mu': 'μ',
    'sigma': 'σ', 'omega': 'ω', 'phi': 'φ', 'Delta': 'Δ', 'Omega': 'Ω',
    'circ': '°', 'degree': '°', 'rightarrow': '→', 'to': '→',
    'therefore': '∴', 'angle': '∠', 'triangle': '△', 'perp': '⊥',
    'parallel': '∥', 'sim': '∼', 'cong': '≅', 'in': '∈', 'cup': '∪', 'cap': '∩',
    'csc': 'cosec',
}
_DROP = {'left', 'right', 'displaystyle', 'quad', 'qquad', 'big', 'Big', 'bigg'}


def _wrap(x):
    x = x.strip()
    return x if re.fullmatch(r'[\w.°]+', x) else '(' + x + ')'


def _frac(m):
    return _wrap(m.group(1)) + '/' + _wrap(m.group(2))


def _cmd(m):
    name = m.group(1)
    if name in _SYMBOLS:
        return _SYMBOLS[name]
    if name in _DROP:
        return ''
    return name


def _sup(m):
    if m.group(1) is not None:
        body = m.group(1).strip()
        if body and all(c in _SUP_OK for c in body):
            return body.translate(_SUP)
        return '^(' + body + ')'
    return m.group(2).translate(_SUP)


def clean_math(text):
    if not isinstance(text, str) or not text:
        return text
    s = text
    for d in ('\\(', '\\)', '\\[', '\\]', '$$', '$'):
        s = s.replace(d, '')
    s = s.replace('\\{', '\u0001').replace('\\}', '\u0002')
    s = re.sub(r'\\[,;:! ]', ' ', s)
    for _ in range(4):
        s = re.sub(r'\\(?:text|mathrm|mathbf|textbf|mathit)\s*\{([^{}]*)\}', r'\1', s)
        s = re.sub(r'\\sqrt\s*\[(\d+)\]\s*\{([^{}]*)\}',
                   lambda m: ('∛' if m.group(1) == '3' else m.group(1) + '√') + '(' + m.group(2) + ')', s)
        s = re.sub(r'\\sqrt\s*\{([^{}]*)\}', r'√(\1)', s)
        s = re.sub(r'\\d?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}', _frac, s)
    s = re.sub(r'\\sqrt\b', '√', s)
    s = re.sub(r'\\([A-Za-z]+)', _cmd, s)
    s = re.sub(r'\^\s*\{?\s*°\s*\}?', '°', s)
    s = re.sub(r'\^\{([^{}]*)\}|\^([+-]?\d+|n(?![A-Za-z]))', _sup, s)
    s = re.sub(r'_\{(\d+)\}|_(\d)', lambda m: (m.group(1) or m.group(2)).translate(_SUB), s)
    s = s.replace('\u0001', '{').replace('\u0002', '}')
    s = re.sub(r'[ \t]{2,}', ' ', s)
    return s.strip()
