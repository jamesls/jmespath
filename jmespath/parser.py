"""Module for parsing JMESPath expressions.

Parsing Projections
===================

This module handles parsing projections slightly differently than
what's in the ABNF grammar (though it's still 100% identical in terms
of its final result).

Let's take a simple expression: ``foo[*].bar``.  Following the productions
from the ABNF grammar in the spec then, as an S-expression, we'd get an
AST of::

    (sub-expression
        (index-expression (field foo)
                          (bracket-specifier "*"))
        (field bar))

The AST walker then needs have implicit knowledge that the ``*`` creates
a projection in which each element in the collection of the evaluated
first child of the subexpression node is then evaluated against the
second child ``(field bar)``.  Any non-None values are then collected
and returned as the final result.

An alternate way to express this logic is to instead embed the projection
semantics into the AST by introducing a projection node.  The same
expression of ``foo[*].bar`` can be written as::

    (projection (field foo) (field bar))

Then the projection semantics are all contained within the ``projection`` AST
node.

Here's a more complicated example.  Given the expression
``foo.bar[*].baz.to_number(@)``, the AST from the ABNF grammar in the spec
is::

    (sub-expression
        (sub-expression
            (index-expression
                (sub-expression (field foo) (field bar))
                (bracket-specifier "*"))
            (field baz))
        (function-expression ("to_number" (function-arg current-node))))

Again, the AST walker needs to know that all the way in the leaf node, the
``*`` creates a projection that then applies for all the remaining AST
walking.  Using a projection node we'd instead have::

    (projection
        (sub-expression (field foo) (field bar))
        (sub-expression
            (field baz)
            (function-expression ("to_number" (function-arg current-node)))))

This once again makes the projection explicit and makes the scope of the
projection clear. This is especially useful in the case of pipes where the
projections do not carry across child nodes of a pipe expression.

"""
import random

import ply.yacc
import ply.lex

from jmespath import ast
from jmespath import lexer
from jmespath.compat import with_repr_method
from jmespath.compat import LR_TABLE
from jmespath.exceptions import VariadictArityError
from jmespath.exceptions import ArityError
from jmespath.exceptions import ParseError
from jmespath.exceptions import IncompleteExpressionError


class Grammar(object):
    precedence = (
        ('left', 'PIPE'),
        ('left', 'OR'),
        ('right', 'DOT', 'STAR'),
        ('left', 'LT', 'LTE', 'GT', 'GTE', 'EQ'),
        ('right', 'LBRACKET', 'RBRACKET'),
    )

    def p_jmespath_single_expr(self, p):
        """expression : subexpression
                      | index-expression
                      | or-expression
                      | identifier-expr
                      | wildcard-value
                      | multi-select-list
                      | multi-select-hash
                      | literal-expression
                      | function-expression
                      | pipe-expression
        """
        p[0] = p[1]

    def p_jmespath_subexpression(self, p):
        """subexpression : expression DOT identifier-expr
                         | expression DOT multi-select-list
                         | expression DOT multi-select-hash
                         | expression DOT function-expression
                         | expression DOT wildcard-value
        """
        p[0] = ast.SubExpression(p[1], p[3])

    def p_jmespath_or_expression(self, p):
        """or-expression : expression OR expression"""
        p[0] = ast.ORExpression(p[1], p[3])

    def p_jmespath_index(self, p):
        """index-expression : expression bracket-spec
                            | bracket-spec
        """
        if len(p) == 3:
            p[0] = ast.SubExpression(p[1], p[2])
        else:
            p[0] = p[1]

    def p_jmespath_multiselect_list(self, p):
        """multi-select-list : LBRACKET expressions RBRACKET
        """
        p[0] = ast.MultiFieldList(p[2])

    def p_jmespath_multiselect(self, p):
        """multi-select-hash : LBRACE keyval-exprs RBRACE
        """
        p[0] = ast.MultiFieldDict(p[2])

    def p_jmespath_pipe(self, p):
        """pipe-expression : expression PIPE expression"""
        p[0] = ast.Pipe(p[1], p[3])

    def p_jmespath_literal_expression(self, p):
        """literal-expression : LITERAL"""
        p[0] = ast.Literal(p[1])

    def p_jmespath_identifier(self, p):
        """identifier : UNQUOTED_IDENTIFIER
                      | QUOTED_IDENTIFIER
        """
        p[0] = p[1]

    # NOTE: Projections are parsed differently than the
    # production rules in the official ABNF grammar from
    # the reference docs.  See the docstring at the top
    # of the module for more info on this.

    def p_jmespath_star(self, p):
        """wildcard-value : STAR"""
        p[0] = ast.WildcardValues()

    def p_jmespath_bracket_specifier(self, p):
        """bracket-spec : LBRACKET STAR RBRACKET
                        | LBRACKET NUMBER RBRACKET
                        | LBRACKET RBRACKET
        """
        if len(p) == 3:
            p[0] = ast.ListElements()
        elif p[2] == '*':
            p[0] = ast.WildcardIndex()
        else:
            p[0] = ast.Index(p[2])

    def p_jmespath_bracket_specifier_filter(self, p):
        """bracket-spec : FILTER filter-expression RBRACKET
        """
        p[0] = ast.FilterExpression(p[2])

    def p_jmespath_filter_expression(self, p):
        """filter-expression : expression comparator expression
        """
        # p[2] is a class object (from p_jmespath_comparator), so we
        # instantiate with the the left hand expression and the right hand
        # expression (p[1] and p[3] respectively).
        p[0] = p[2](p[1], p[3])

    def p_jmespath_comparator(self, p):
        """comparator : LT
                      | LTE
                      | GT
                      | GTE
                      | EQ
                      | NE
        """
        op_map = {
            '<': ast.OPLessThan,
            '<=': ast.OPLessThanEquals,
            '==': ast.OPEquals,
            '>': ast.OPGreaterThan,
            '>=': ast.OPGreaterThanEquals,
            '!=': ast.OPNotEquals,
        }
        p[0] = op_map[p[1]]

    def p_jmespath_identifier_expr(self, p):
        """identifier-expr : identifier"""
        p[0] = ast.Field(p[1])

    def p_jmespath_keyval_exprs(self, p):
        """keyval-exprs : keyval-exprs COMMA keyval-expr
                        | keyval-expr
        """
        if len(p) == 2:
            p[0] = [p[1]]
        elif len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]

    def p_jmespath_keyval_expr(self, p):
        """keyval-expr : identifier COLON expression
        """
        p[0] = ast.KeyValPair(p[1], p[3])

    def p_jmespath_multiple_expressions(self, p):
        """expressions : expressions COMMA expression
                       | expression
        """
        if len(p) == 2:
            p[0] = [p[1]]
        elif len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]

    def p_jmespath_function_expression(self, p):
        """function-expression : UNQUOTED_IDENTIFIER LPAREN function-args RPAREN
                               | UNQUOTED_IDENTIFIER LPAREN RPAREN
        """
        if len(p) == 5:
            args = p[3]
        else:
            args = []
        function_node = ast.FunctionExpression(p[1], args)
        if function_node.variadic:
            if len(function_node.args) < function_node.arity:
                raise VariadictArityError(function_node)
        elif function_node.arity != len(function_node.args):
            raise ArityError(function_node)
        p[0] = function_node

    def p_jmespath_function_args(self, p):
        """function-args : function-args COMMA function-arg
                         | function-arg
        """
        if len(p) == 2:
            p[0] = [p[1]]
        elif len(p) == 4:
            p[1].append(p[3])
            p[0] = p[1]

    def p_jmespath_function_arg(self, p):
        """function-arg : expression
                        | CURRENT
                        | EXPREF expression
        """
        if len(p) == 3:
            p[0] = ast.ExpressionReference(p[2])
        elif p[1] == '@':
            p[0] = ast.CurrentNode()
        else:
            p[0] = p[1]

    def p_error(self, t):
        if t is not None:
            raise ParseError(t.lexpos, t.value, t.type)
        else:
            raise IncompleteExpressionError(None, None, None)


class Parser(object):
    # The _max_size most recent expressions are cached in
    # _cache dict.
    _cache = {}
    _max_size = 64
    _table_module = LR_TABLE

    def __init__(self, lexer_definition=None, grammar=None,
                 debug=False):
        if lexer_definition is None:
            lexer_definition = lexer.LexerDefinition
        if grammar is None:
            grammar = Grammar
        self._lexer_definition = lexer_definition
        self._grammar = grammar
        self.tokens = self._lexer_definition.tokens
        self._debug = debug

    def parse(self, expression):
        cached = self._cache.get(expression)
        if cached is not None:
            return cached
        lexer = ply.lex.lex(module=self._lexer_definition(),
                            debug=self._debug,
                            reflags=self._lexer_definition.reflags)
        grammar = self._grammar()
        grammar.tokens = self._lexer_definition.tokens
        parser = ply.yacc.yacc(module=grammar, debug=self._debug,
                               tabmodule=self._table_module,
                               write_tables=False)
        parsed = self._parse_expression(parser=parser, expression=expression,
                                        lexer_obj=lexer)
        parsed_result = ParsedResult(expression, parsed)
        self._cache[expression] = parsed_result
        if len(self._cache) > self._max_size:
            self._free_cache_entries()
        return parsed_result

    def _parse_expression(self, parser, expression, lexer_obj):
        try:
            parsed = parser.parse(input=expression, lexer=lexer_obj)
            return parsed
        except lexer.LexerError as e:
            e.expression = expression
            raise e
        except IncompleteExpressionError as e:
            e.set_expression(expression)
            raise e
        except ParseError as e:
            e.expression = expression
            raise e

    def _free_cache_entries(self):
        # This logic is borrowed from the new regex library which
        # uses similar eviction strategies.
        for key in random.sample(self._cache.keys(), int(self._max_size / 2)):
            del self._cache[key]

    @classmethod
    def purge(cls):
        """Clear the expression compilation cache."""
        cls._cache.clear()


@with_repr_method
class ParsedResult(object):
    def __init__(self, expression, parsed):
        self.expression = expression
        self.parsed = parsed

    def search(self, value):
        return self.parsed.search(value)

    def pretty_print(self, indent=''):
        return self.parsed.pretty_print(indent=indent)

    def __repr__(self):
        return repr(self.parsed)

    def __eq__(self, other):
        return (isinstance(other, self.__class__)
                and self.__dict__ == other.__dict__)

    def __ne__(self, other):
        return not self.__eq__(other)

