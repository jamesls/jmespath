#!/usr/bin/env python

import unittest
from tests import OrderedDict

from jmespath import ast
from jmespath import transform
from jmespath import parser


def as_s_expression(node):
    parts = []
    _as_s_expression(node, parts)
    return ''.join(parts)

def _as_s_expression(node, parts):
    parts.append("(%s" % (node.__class__.__name__.lower()))
    if isinstance(node, ast.Field):
        parts.append(" %s" % node.name)
    elif isinstance(node, ast.FunctionExpression):
        parts.append(" %s" % node.name)
    elif isinstance(node, ast.KeyValPair):
        parts.append(" %s" % node.key_name)
    for child in node.children:
        parts.append(" ")
        _as_s_expression(child, parts)
    parts.append(")")


class TestAST(unittest.TestCase):
    def setUp(self):
        self.parser = parser.Parser()
        self.transform = transform.ProjectionTransform()

    def test_subexp_single_field(self):
        parsed = self.parser.parse('a[*].b').parsed
        transformed = self.transform.transform(parsed)
        # From:
        # (subexpression (subexpression (field a) (wildcardindex)) (field b))
        # To:
        expected = (
            '(projection (field a) (field b))')
        self.assertEqual(as_s_expression(transformed), expected)

    def test_subexp_transform_complete(self):
        parsed = self.parser.parse('a.b.c[*].d.e.f').parsed
        # From:
        # (subexpression
        #   (subexpression
        #     (subexpression
        #       (subexpression
        #         (subexpression
        #           (subexpression
        #             (field a)
        #             (field b))
        #           (field c))
        #         (wildcardindex))
        #       (field d))
        #     (field e))
        #   (field f))
        #
        # To:
        # (projection
        #   (subexpression
        #     (subexpression
        #       (field a)
        #       (field b))
        #     (field c)
        #  (subexpression
        #    (subexpression
        #      (field d)
        #      (field e))
        #    (field f)))
        transformed = self.transform.transform(parsed)
        expected = (
            "(projection "
              "(subexpression "
                "(subexpression (field a) (field b)) "
                "(field c)) "
              "(subexpression "
                "(subexpression "
                  "(field d) (field e)) "
                "(field f)))")
        self.assertEqual(as_s_expression(transformed), expected)

    def test_or_expression(self):
        parsed = self.parser.parse('a[*].b || c').parsed
        # From:
        # (orexpression
        #   (subexpression
        #     (subexpression
        #       (field a) (wildcardindex))
        #     (field b))
        #   (field c))
        # To:
        # (orexpression
        #   (projection (field a) (field b))
        #   (field c))
        transformed = self.transform.transform(parsed)
        expected = (
            "(orexpression "
              "(projection (field a) (field b)) "
              "(field c))")
        self.assertEqual(as_s_expression(transformed), expected)
