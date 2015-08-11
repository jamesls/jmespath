import os
from pprint import pformat
from tests import OrderedDict
from tests import json

from nose.tools import assert_equal

import jmespath

# Will try to parse every expression and ensure that
# ply doesn't complain about being ambiguous.

TEST_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'compliance')
NOT_SPECIFIED = object()


def test_compliance():
    for full_path in _walk_files():
        if full_path.endswith('.json'):
            for given, expression, result, error in _load_cases(full_path):
                if error is NOT_SPECIFIED and result is not NOT_SPECIFIED:
                    yield (_test_expression, given, expression,
                        result, os.path.basename(full_path))


def _walk_files():
    # Check for a shortcut when running the tests interactively.
    # If a JMESPATH_TEST is defined, that file is used as the
    # only test to run.  Useful when doing feature development.
    single_file = os.environ.get('JMESPATH_TEST')
    if single_file is not None:
        yield os.path.abspath(single_file)
    else:
        for root, dirnames, filenames in os.walk(TEST_DIR):
            for filename in filenames:
                yield os.path.join(root, filename)


def _load_cases(full_path):
    all_test_data = json.load(open(full_path), object_pairs_hook=OrderedDict)
    for test_data in all_test_data:
        given = test_data['given']
        for case in test_data['cases']:
            yield (given, case['expression'],
                   case.get('result', NOT_SPECIFIED),
                   case.get('error', NOT_SPECIFIED))


def _test_expression(given, expression, expected, filename):
    try:
        parser = jmespath.parser.Parser(debug=True)
        parsed = parser.parse(expression)
    except ValueError as e:
        raise AssertionError(
            'jmespath expression failed to compile: "%s", error: %s"' %
            (expression, e))
    if 'conflict' in parser.errors.getvalue():
        raise AssertionError("Grammar is ambiguous: %s"
                             % parser.errors.getvalue())
