"""Strict reader for pinned Vercel CLI env-pull output, without expansion."""
import re

# ECMAScript WhiteSpace + LineTerminator, used by String.prototype.trim.
# Python str.strip additionally removes U+0085 and U+001C..U+001F, and omits BOM.
JS_TRIM_WHITESPACE='\u0009\u000a\u000b\u000c\u000d\u0020\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff'


def parse_pulled_environment(path):
    """Match the export format and pinned build reader, not JSON escaping.

    env/pull wraps raw values in double quotes and escapes only LF and CR.
    The bundled dotenv 4 reader decodes backslash-n, leaves backslash-r and
    all other backslashes intact, strips outer quotes and trims values.
    This format cannot distinguish an original LF from literal backslash-n.
    """
    try:
        content=path.read_text(encoding='utf-8')
    except (OSError,UnicodeError):
        raise ValueError('invalid production environment file') from None
    values={}
    # Do not use splitlines(): it splits controls that JavaScript preserves.
    for line in content.split('\n'):
        if line.endswith('\r'):line=line[:-1]
        if not line or line.startswith('#'):continue
        key,sep,raw=line.partition('=')
        if (not sep or re.fullmatch(r'[A-Z_][A-Z0-9_]*',key) is None or key in values
                or len(raw)<2 or raw[0]!='"' or raw[-1]!='"'
                or any(character in raw for character in ('\r','\x00','\u2028','\u2029'))):
            raise ValueError('invalid production environment file')
        # dotenv 4's non-dotAll assignment regex drops U+2028/U+2029 lines;
        # reject them above rather than silently losing a reviewed binding.
        values[key]=raw[1:-1].replace('\\n','\n').strip(JS_TRIM_WHITESPACE)
    return values
