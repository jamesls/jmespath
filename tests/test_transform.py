#!/usr/bin/env python

import unittest
from tests import OrderedDict, as_s_expression

from jmespath import ast
from jmespath import transform
from jmespath import parser


class TestAST(unittest.TestCase):
    def setUp(self):
        self.parser = parser.Parser(transforms=[])
        self.transform = transform.ProjectionTransform()

    def assert_transformation(self, expression, s_exp):
        parsed = self.parser.parse(expression).parsed
        transformed = self.transform.transform(parsed)
        self.assertEqual(as_s_expression(transformed), s_exp)

    def test_subexp_single_field(self):
        # From:
        # (subexpression (subexpression (field a) (wildcardindex)) (field b))
        # To:
        expected = (
            '(projection (field a) (subexpression (identity) (field b)))')
        self.assert_transformation('a[*].b', expected)

    def test_subexp_with_flatten(self):
        # TODO: fix flatten, filters, and maybe functions.
        # They need their own projection type.
        return
        # From:
        # (subexpression (subexpression (field a) (wildcardindex)) (field b))
        # To:
        expected = (
            '(projection (field a) (subexpression (identity) (field b)))')
        self.assert_transformation('a[].b', expected)

    def test_subexp_transform_complete(self):
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
        #      (subexpression (identity) (field d))
        #      (field e))
        #    (field f)))
        expected = (
            "(projection "
              "(subexpression "
                "(subexpression (field a) (field b)) "
                "(field c)) "
              "(subexpression "
                "(subexpression "
                  "(subexpression (identity) (field d)) "
                  "(field e)) "
                "(field f)))")
        self.assert_transformation('a.b.c[*].d.e.f',
                                   expected)

    def test_or_expression(self):
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
        expected = (
            "(orexpression "
              "(projection (field a) (subexpression (identity) (field b))) "
              "(field c))")
        self.assert_transformation('a[*].b || c', expected)

    def test_pipe_expression(self):
        expected = (
            "(pipe "
              "(projection "
                "(field a) "
                "(subexpression (identity) (field b))) "
              "(field c))"
        )
        self.assert_transformation('a[*].b | c', expected)

    def test_multiple_projections(self):
        expected = (
            "(projection "
              "(field a) "
              "(projection "
                "(subexpression (identity) (field b)) "
                "(subexpression (identity) (field c))))"
        )
        self.assert_transformation('a[*].b[*].c', expected)

    def test_multiple_projection_with_identity(self):
        expected = (
            "(projection "
              "(field a) "
              "(projection "
                "(subexpression (identity) (field b)) "
                "(identity)))"
        )
        self.assert_transformation('a[*].b[*]', expected)

    def test_value_projection(self):
        expected = (
            "(valueprojection "
              "(field a) "
              "(subexpression (identity) (field b)))"
        )
        self.assert_transformation('a.*.b', expected)

    def test_only_projection(self):
        expected = (
            "(projection (identity) (identity))"
        )
        self.assert_transformation('[*]', expected)

    def test_complex_projection(self):
        expected = (
            "(pipe "
              "(projection "
                "(field foo) "
                "(projection "
                  "(subexpression (identity) (field bar)) "
                  "(identity))) "
              "(indexexpression "
                "(indexexpression "
                  "(identity) (index)) "
                "(index)))"
        )
        self.assert_transformation('foo[*].bar[*] | [0][0]', expected)

    def test_star_dot_star(self):
        expected = (
            "(valueprojection "
              "(identity) "
              "(valueprojection "
                "(identity) (identity)))"
        )
        self.assert_transformation('*.*', expected)

    def test_multiselect_hash(self):
        expected = (
            "(multifielddict "
              "(keyvalpair "
                "a (valueprojection (identity) (identity))))"
        )
        self.assert_transformation('{"a": *}', expected)
