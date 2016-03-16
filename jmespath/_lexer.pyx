import string
import warnings
from json import loads

from jmespath.exceptions import LexerError, EmptyExpressionError

cdef unsigned long long IDENT_START = 0x7fffffe87fffffe
cdef unsigned long long *IDENT_TRAIL = [0x3ff000000000000, 0x7fffffe87fffffe]

DEF LBRACKET = ord('[')
DEF RBRACKET = ord(']')
DEF ZERO = ord('0')
DEF NINE = ord('9')


cdef _is_ident_start(unsigned long long ch):
    if ch < 65:
        return False
    return (IDENT_START & (1ULL << (ch - 64ULL))) > 0


cdef _is_ident_trailing(s):
    cdef unsigned x
    cdef unsigned long long chrbit
    if s is None:
        return None
    x = ord(s)
    if x > 128:
        return False
    chrbit = (1ULL << (x % 64ULL))
    return (IDENT_TRAIL[x / 64] & chrbit) > 0


cdef class Lexer(object):
    WHITESPACE = set(" \t\n\r")
    SIMPLE_TOKENS = {
        '.': 'dot',
        '*': 'star',
        ']': 'rbracket',
        ',': 'comma',
        ':': 'colon',
        '@': 'current',
        '(': 'lparen',
        ')': 'rparen',
        '{': 'lbrace',
        '}': 'rbrace',
    }

    cdef int _position, _length
    cdef basestring _expression, _current
    cdef object _chars

    def __init__(self):
        self._position = 0
        self._expression = ''
        self._chars = []
        self._current = ''
        self._length = 0

    def tokenize(self, expression):
        self._initialize_for_expression(expression)
        cdef unsigned curchar
        while self._current is not None:
            curchar = ord(self._current)
            if _is_ident_start(curchar):
                start = self._position
                buff = self._current
                while _is_ident_trailing(self._next()):
                    buff += self._current
                yield {'type': 'unquoted_identifier', 'value': buff,
                       'start': start, 'end': start + len(buff)}
            elif self._current in self.SIMPLE_TOKENS:
                yield {'type': self.SIMPLE_TOKENS[self._current],
                       'value': self._current,
                       'start': self._position, 'end': self._position + 1}
                self._next()
            elif curchar == LBRACKET:
                start = self._position
                next_char = self._next()
                if next_char is not None and ord(next_char) == RBRACKET:
                    self._next()
                    yield {'type': 'flatten', 'value': '[]',
                           'start': start, 'end': start + 2}
                elif next_char == '?':
                    self._next()
                    yield {'type': 'filter', 'value': '[?',
                           'start': start, 'end': start + 2}
                else:
                    yield {'type': 'lbracket', 'value': '[',
                           'start': start, 'end': start + 1}
            elif self._current == "'":
                yield self._consume_raw_string_literal()
            elif self._current == '|':
                yield self._match_or_else('|', 'or', 'pipe')
            elif self._current == '&':
                yield self._match_or_else('&', 'and', 'expref')
            elif self._current == '`':
                yield self._consume_literal()
            elif ZERO <= curchar <= NINE:
                start = self._position
                buff = self._consume_number()
                yield {'type': 'number', 'value': int(buff),
                       'start': start, 'end': start + len(buff)}
            elif self._current == '-':
                # Negative number.
                start = self._position
                buff = self._consume_number()
                if len(buff) > 1:
                    yield {'type': 'number', 'value': int(buff),
                           'start': start, 'end': start + len(buff)}
                else:
                    raise LexerError(lexer_position=start,
                                     lexer_value=buff,
                                     message="Unknown token '%s'" % buff)
            elif self._current == '"':
                yield self._consume_quoted_identifier()
            elif self._current == '<':
                yield self._match_or_else('=', 'lte', 'lt')
            elif self._current == '>':
                yield self._match_or_else('=', 'gte', 'gt')
            elif self._current == '!':
                yield self._match_or_else('=', 'ne', 'not')
            elif self._current == '=':
                yield self._match_or_else('=', 'eq', 'unknown')
            elif self._current in self.WHITESPACE:
                self._next()
            else:
                raise LexerError(lexer_position=self._position,
                                 lexer_value=self._current,
                                 message="Unknown token %s" % self._current)
        yield {'type': 'eof', 'value': '',
               'start': self._length, 'end': self._length}

    cdef _consume_number(self):
        buff = self._current
        cdef unsigned ch
        while True:
            current = self._next()
            if current is None:
                break
            ch = ord(current)
            if ZERO <= ch <= NINE:
                buff += current
            else:
                break
        return buff

    cdef _initialize_for_expression(self, basestring expression):
        if not expression:
            raise EmptyExpressionError()
        self._position = 0
        self._expression = expression
        self._chars = list(self._expression)
        self._current = self._chars[self._position]
        self._length = len(self._expression)

    cdef _next(self):
        self._position += 1
        if self._position != self._length:
            self._current = self._chars[self._position]
            return self._current
        else:
            self._position -= 1
            self._current = None

    cdef _consume_until(self, basestring delimiter):
        # Consume until the delimiter is reached,
        # allowing for the delimiter to be escaped with "\".
        start = self._position
        buff = ''
        self._next()
        while self._current != delimiter:
            if self._current == '\\':
                buff += '\\'
                self._next()
            if self._current is None:
                raise LexerError(lexer_position=start,
                                 lexer_value=self._expression,
                                 message="Unclosed %s delimiter" % delimiter)
            buff += self._current
            self._next()
        # Skip the closing delimiter.
        self._next()
        return buff

    cdef _consume_literal(self):
        start = self._position
        lexeme = self._consume_until('`').replace('\\`', '`')
        try:
            # Assume it is valid JSON and attempt to parse.
            parsed_json = loads(lexeme)
        except ValueError:
            try:
                # Invalid JSON values should be converted to quoted
                # JSON strings during the JEP-12 deprecation period.
                parsed_json = loads('"%s"' % lexeme.lstrip())
                warnings.warn("deprecated string literal syntax",
                              PendingDeprecationWarning)
            except ValueError:
                raise LexerError(lexer_position=start,
                                 lexer_value=self._expression,
                                 message="Bad token %s" % lexeme)
        token_len = self._position - start
        return {'type': 'literal', 'value': parsed_json,
                'start': start, 'end': token_len}

    cdef _consume_quoted_identifier(self):
        start = self._position
        lexeme = '"' + self._consume_until('"') + '"'
        try:
            token_len = self._position - start
            return {'type': 'quoted_identifier', 'value': loads(lexeme),
                    'start': start, 'end': token_len}
        except ValueError as e:
            error_message = str(e).split(':')[0]
            raise LexerError(lexer_position=start,
                             lexer_value=lexeme,
                             message=error_message)

    cdef _consume_raw_string_literal(self):
        start = self._position
        lexeme = self._consume_until("'").replace("\\'", "'")
        token_len = self._position - start
        return {'type': 'literal', 'value': lexeme,
                'start': start, 'end': token_len}

    cdef _match_or_else(self, basestring expected, basestring match_type, basestring else_type):
        start = self._position
        current = self._current
        next_char = self._next()
        if next_char == expected:
            self._next()
            return {'type': match_type, 'value': current + next_char,
                    'start': start, 'end': start + 1}
        return {'type': else_type, 'value': current,
                'start': start, 'end': start}
