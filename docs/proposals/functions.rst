=========
Functions
=========

:JEP: 3
:Author: Michael Dowling
:Status: Draft
:Created: 27-Nov-2013

Abstract
========

This document proposes modifying the `JMESPath grammar <http://jmespath.readthedocs.org/en/latest/specification.html#grammar>`_
to support function expressions.

Motivation
==========

Functions allow users to easily transform and filter data in JMESPath
expressions. As JMESPath is currently implemented, functions would be very useful
in ``multi-select-list`` and ``multi-select-hash`` expressions to format the
output of an expression to contain data that might not have been in the
original JSON input. If filtered projections are added to JMESPath, functions
would be a powerful mechanism to perform any kind of special comparisons for
things like ``length()``, ``contains()``, etc.

Data Types
==========

In order to support functions, we must define a type system. Because JMESPath
is a JSON DSL, we will use JSON types:

* number (integers and double-precision floating-point format in JavaScript)
* string
* boolean (``true`` or ``false``)
* array (an ordered, sequence of values)
* object (an unordered, comma-separated collection of key:value pairs)
* null

Syntax Changes
==============

Functions may be used to start any expression, including but not limited to the
root of an expression, inside of a ``multi-select`` expression, or at the start
of an ``or-expression``.

The function grammar will require the following grammar additions:

::

    function-expression = unquoted-string "(" *(function-arg *("," function-arg ) ) ")"
    function-arg        = expression / number

``expression`` will need to be updated to add the ``current-node`` production:

::

    expression        = sub-expression / index-expression / or-expression / identifier / "*"
    expression        =/ multi-select-list / multi-select-hash
    expression        =/ function-expression / current-node / literal
    current-node      = "@"

A function can accept any number of arguments, and each argument can be an
expression.

current-node
------------

The ``current-node`` token can be used to represent the current node being
evaluated. The ``current-node`` token is useful for functions that require the
current node being evaluated as an argument. For example, the following
expression creates an array containing the total number of elements in the
``foo`` object followed by the value of ``foo["bar"]``.

::

    foo.[count(@), bar]

It is not necessary to prefix a function argument with the ``current-node``
token when descending into the current node. For example, the following two
expressions are equivalent:

::

    contains(foo, `bar`)
    contains(@.foo, `bar`)

current-node state
~~~~~~~~~~~~~~~~~~

At the start of an expression, the value of the current node is the data
being evaluated by the JMESPath expression. As an expression is evaluated, the
value the the current node represents MUST change to reflect the node currently
being evaluated. When in a projection, the current node value MUST be changed
to the node currently being evaluated by the projection.

Functions
=========

JMESPath will ship with various built-in functions that operate on different
data types. Functions can have a required arity or be variadic with a minimum
number of arguments.

Functions MUST return ``null`` when a specific argument is passed that is not
of the expected type. Functions MUST raise an error if the provided arguments
do not match the arity of the function.

.. note::

    All string related functions are defined on the basis of Unicode code
    points; they do not take collations into account.

string functions
----------------

concat
~~~~~~

::

    string concat(string|number $string1, string|number $string2 [, string|number $... ])

Returns each argument concatenated one after the other.

If any argument is provided that is not a string or a number, then this method
MUST return ``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Expression
     - Result
   * - ``concat(`a`, `b`)``
     - "ab"
   * - ``concat(`a`, `b`, `c`)``
     - "abc"
   * - ``concat(`a`, `b`, 1)``
     - "ab1"
   * - ``concat(`a`, `false`, `b`)``
     - ``null``
   * - ``concat(`true`, `false`)``
     - ``null``
   * - ``concat(`a`)``
     - raises an error because the function requires at least two arguments

contains
~~~~~~~~

See contains_.

.. _length:

length
~~~~~~

::

    number length(string|array|object $subject)

Returns the length of the given argument using the following types rules:

1. string: returns the number of characters in the string
2. array: returns the number of elements in the array
3. object: returns the number of key-value pairs in the object
4. boolean, null: returns null

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - n/a
     - ``length(`abc`)``
     - 3
   * - "current"
     - ``length(@)``
     - 7
   * - "current"
     - ``length(@.not_there)``
     - ``null``
   * - "current"
     - ``length(not_there)``
     - ``null``
   * - n/a
     - ``length(`false`)``
     - ``null``
   * - n/a
     - ``length(10)``
     - ``null``
   * - n/a
     - ``length()``
     - Raises an error
   * - ``["a", "b", "c"]``
     - ``length(@)``
     - 3
   * - ``[]``
     - ``length(@)``
     - 0
   * - ``{}``
     - ``length(@)``
     - 0
   * - ``{"foo": "bar", "baz": "bam"}``
     - ``length(@)``
     - 2

number functions
----------------

abs
~~~

::

    number abs(number $number)

Returns the absolute value of the provided argument.

If the provided argument is not a number, then this function MUST return ``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Expression
     - Result
   * - ``abs(1)``
     - 1
   * - ``abs(-1)``
     - 1
   * - ``abs(`abc`)``
     - ``null``

ceil
~~~~

::

    number ceil(number $number)

Returns the next highest integer value by rounding up if necessary.

This function MUST return ``null`` if the provided argument is not a number.

.. list-table:: Examples
   :header-rows: 1

   * - Expression
     - Result
   * - ``ceil(`1.001`)``
     - 2
   * - ``ceil(`1.9`)``
     - 2
   * - ``ceil(`1`)``
     - 1
   * - ``ceil(`abc`)``
     - ``null``

floor
~~~~~

::

    number floor(number $number)

Returns the next lowest integer value by rounding down if necessary.

This function MUST return ``null`` if the provided argument is not a number.

.. list-table:: Examples
   :header-rows: 1

   * - Expression
     - Result
   * - ``floor(`1.001`)``
     - 1
   * - ``floor(`1.9`)``
     - 1
   * - ``floor(`1`)``
     - 1
   * - ``floor(`abc`)``
     - ``null``

array functions
---------------

avg
~~~

::

    number avg(array $arr)

Returns the average of the elements in the provided array.

Elements in the array that are not numbers are excluded from the averaged
result. If no elements are numbers, then this function MUST return ``null``.

If the provided argument, ``$arr``, is not an array, this function MUST return
``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``[10, 15, 20]``
     - ``avg(@)``
     - 15
   * - ``[10, false, 20]``
     - ``avg(@)``
     - 15
   * - ``[false]``
     - ``avg(@)``
     - ``null``
   * - ``false``
     - ``avg(@)``
     - ``null``

.. _contains:

contains
~~~~~~~~

::

    boolean contains(array|string $subject, $search)

Returns true if the given ``$subject`` contains the provided ``$search``
string.

If ``$subject`` is an array, this function returns true if one of the elements
in the array is exactly equal to the provided ``$search`` value.

If the provided ``$subject`` is a string, this function returns true if
the string contains the provided ``$search`` argument. In this case, the
``$search`` argument MUST be a string or the function will return ``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - n/a
     - ``contains(`foobar`, `foo`)``
     - ``true``
   * - n/a
     - ``contains(`foobar`, `not`)``
     - ``false``
   * - n/a
     - ``contains(`foobar`, `bar`)``
     - ``true``
   * - n/a
     - ``contains(`false`, `bar`)``
     - ``null``
   * - n/a
     - ``contains(123, `bar`)``
     - ``null``
   * - n/a
     - ``contains(`foobar`, 123)``
     - ``false``
   * - ``["a", "b"]``
     - ``contains(@, `a`)``
     - ``true``
   * - ``["a"]``
     - ``contains(@, `a`)``
     - ``true``
   * - ``["a"]``
     - ``contains(@, `b`)``
     - ``false``
   * - ``{"a": "123"}``
     - ``contains(@, `123`)``
     - ``null``
   * - ``{"a": "123"}``
     - ``contains(`foo`, @)``
     - ``null``

has
~~~

::

    boolean has(array|object $subject, $key)

Checks if the given array or object has the given key. If an object
``$subject`` is provided, this function returns true if the object has the
given key of ``$key``. If an array ``$subject`` is provided, this functions
returns true if the array has the given numeric index of ``$key``.

This function MUST return ``null`` if the provided ``$subject`` is not an
array or object. This function MUST return ``null`` if the provided ``$key``
argument is not a string or number.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``["a", "b"]``
     - ``has(@, 0)``
     - ``true``
   * - ``["a", "b"]``
     - ``has(@, 1)``
     - ``true``
   * - ``["a", "b"]``
     - ``has(@, 2)``
     - ``false``
   * - ``{"foo": 1}``
     - ``has(@, `foo`)``
     - ``true``
   * - ``{"foo": 1}``
     - ``has(@, `bar`)``
     - ``false``
   * - ``"abc"``
     - ``has(@, `bar`)``
     - ``null``
   * - ``{"foo": 1}``
     - ``has(@, false)``
     - ``null``

join
~~~~

::

    string join(string $glue, array $stringsarray)

Returns all of the elements from the provided ``$stringsarray`` array joined
together using the ``$glue`` argument as a separator between each.

Any element that is not a string or number is excluded from the joined result.

This function MUST return ``null`` if ``$stringsarray`` is not an array. This
function MUST return ``null`` if the provided ``$glue`` argument is not a
string.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``["a", "b"]``
     - ``join(`, `, @)``
     - "a, b"
   * - ``["a", "b"]``
     - ``join(``, @)``
     - "ab"
   * - ``["a", false, "b"]``
     - ``join(`, `, @)``
     - "a, b"
   * - ``[false]``
     - ``join(`, `, @)``
     - ""
   * - n/a
     - ``join(`, `, `foo`)``
     - ``null``
   * - ``["a", "b"]``
     - ``join(`false`, @)``
     - ``null``

length
~~~~~~

See length_.

max
~~~

::

    number max(array $collection)

Returns the highest found number in the provided array argument. Any element in
the sequence that is not a number MUST be ignored from the calculated result.

If the provided argument is not an array, this function MUST return ``null``.

If no Numeric values are found, this function MUST return ``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``[10, 15]``
     - ``max(@)``
     - 15
   * - ``[10, false, 20]``
     - ``max(@)``
     - 20
   * - ``[false]``
     - ``max(@)``
     - ``null``
   * - ``[]``
     - ``max(@)``
     - ``null``
   * - ``{"foo": 10, "bar": 20}``
     - ``max(@)``
     - ``null``
   * - ``false``
     - ``max(@)``
     - ``null``

min
~~~

::

    number min(array $collection)

Returns the lowest found number in the provided array argument.

Any element in the sequence that is not a number MUST be ignored from the
calculated result. If no Numeric values are found, this function MUST return
``null``.

This function MUST return ``null`` if the provided argument is not an array.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``[10, 15]``
     - ``min(@)``
     - 10
   * - ``[10, false, 20]``
     - ``min(@)``
     - 10
   * - ``[false]``
     - ``min(@)``
     - ``null``
   * - ``[]``
     - ``min(@)``
     - ``null``
   * - ``{"foo": 10, "bar": 20}``
     - ``min(@)``
     - ``null``
   * - ``false``
     - ``min(@)``
     - ``null``

sort
~~~~

::

    array sort(array $list)

This function accepts an array ``$list`` argument and returns the
lexicographically sorted elements of the ``$list`` as an array.

This function MUST return ``null`` if the provided argument is not an array.

array element types are sorted in the following order (the lower the number
means the sooner in the list the element appears):

1. object
2. array
3. null
4. boolean
5. number
6. string

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``[b, a, c]``
     - ``sort(@)``
     - ``[a, b, c]``
   * - ``[1, a, c]``
     - ``sort(@)``
     - ``[1, a, c]``
   * - ``[false, [], null]``
     - ``sort(@)``
     - ``[[], null, false]``
   * - ``[[], {}, false]``
     - ``sort(@)``
     - ``[{}, [], false]``
   * - ``{"a": 1, "b": 2}``
     - ``sort(@)``
     - ``null``
   * - ``false``
     - ``sort(@)``
     - ``null``

object functions
----------------

contains
~~~~~~~~

See contains_.

length
~~~~~~

See length_.

keys
~~~~

::

    array keys(object $obj)

Returns an array containing the hash keys of the provided object.

This function MUST return ``null`` if the provided argument is not an object.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``{"foo": "baz", "bar": "bam"}``
     - ``keys(@)``
     - ``["foo", "bar"]``
   * - ``{}``
     - ``keys(@)``
     - ``[]``
   * - ``false``
     - ``keys(@)``
     - ``null``
   * - ``[b, a, c]``
     - ``keys(@)``
     - ``null``

union
~~~~~

::

    object union(object $object1, object $object2 [, object $... ])

Returns an object containing all of the provided arguments merged into a single
object. If a key collision occurs, the first key value is used.

This function requires at least two arguments. If any of the provided
arguments are not objects, those argument are ignored from the resulting merged
object.

If no object arguments are found, this function MUST return ``null``.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``[{"foo": "baz", "bar": "bam"}, {"qux": "more"}]``
     - ``union(@[0], @[1])``
     - ``{"foo": "baz", "bar": "bam", "qux": "more"}``
   * - ``[{"foo": "baz", "bar": "bam"}, {"qux": "more"}]``
     - ``union([0], [1])``
     - ``{"foo": "baz", "bar": "bam", "qux": "more"}``
   * - ``[{"foo": "baz", "bar": "bam"}, {"qux": "more", "foo": "ignore"}]``
     - ``union(@[0], @[1])``
     - ``{"foo": "baz", "bar": "bam", "qux": "more"}``
   * - ``[{}, {}]``
     - ``union(@[0], @[1])``
     - ``{}``
   * - ``[{"foo": "baz", "bar": "bam"}, [], false, {"qux": "more", "foo": "ignore"}]``
     - ``union(@[0], @[1])``
     - ``{"foo": "baz", "bar": "bam", "qux": "more"}``
   * - n/a
     - ``union(`false`, `false`)``
     - ``null``
   * - {}
     - ``union(@)``
     - Raises an error

values
~~~~~~

::

    array values(object|array $obj)

Returns the values of the provided object.

If the given argument is an array, this function transparently returns the
given argument.

This function MUST return ``null`` if the given argument is not an object or
array.

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - ``{"foo": "baz", "bar": "bam"}``
     - ``values(@)``
     - ``["baz", "bam"]``
   * - ``["a", "b"]``
     - ``values(@)``
     - ``["a", "b"]``
   * - ``[{}, {}]``
     - ``values(@)``
     - ``[{}, {}]``
   * - ``false``
     - ``values(@)``
     - ``null``

Type functions
--------------

type
~~~~

::

    string type(mixed $subject)

Returns the JavaScript type of the given ``$subject`` argument as a string
value.

The return value MUST be one of the following:

* number
* string
* boolean
* array
* object
* null

.. list-table:: Examples
   :header-rows: 1

   * - Given
     - Expression
     - Result
   * - "foo"
     - ``type(@)``
     - "string"
   * - ``true``
     - ``type(@)``
     - "boolean"
   * - ``false``
     - ``type(@)``
     - "boolean"
   * - ``null``
     - ``type(@)``
     - "null"
   * - 123
     - ``type(@)``
     - number
   * - 123.05
     - ``type(@)``
     - number
   * - ``["abc"]``
     - ``type(@)``
     - "array"
   * - ``{"abc": "123"}``
     - ``type(@)``
     - "object"

Test Cases
==========

.. code-block:: json

    [{
      "given":
      {
        "foo": -1,
        "zero": 0,
        "arr": [-1, 3, 4, 5, "a", "100"],
        "strings": ["a", "b", "c"],
        "dec": [1.01, 1.9, -1.5],
        "str": "Str",
        "false": false,
        "empty": [],
        "empty2": {}
      },
      "cases": [
        {
          "expression": "abs(@.foo)",
          "result": 1
        },
        {
          "expression": "abs(foo)",
          "result": 1
        },
        {
          "expression": "abs(@.str)",
          "result": null
        },
        {
          "expression": "abs(str)",
          "result": null
        },
        {
          "expression": "abs(@.arr[1])",
          "result": 3
        },
        {
          "expression": "abs(arr[1])",
          "result": 3
        },
        {
          "expression": "abs(false)",
          "result": null
        },
        {
          "expression": "abs(`false`)",
          "result": null
        },
        {
          "expression": "abs(`1`, `2`, `3`)",
          "error": "runtime"
        },
        {
          "expression": "abs()",
          "error": "runtime"
        },
        {
          "expression": "avg(@.arr)",
          "result": 2.75
        },
        {
          "expression": "avg(arr)",
          "result": 2.75
        },
        {
          "expression": "avg(`abc`)",
          "result": null
        },
        {
          "expression": "avg(@.foo)",
          "result": null
        },
        {
          "expression": "avg(foo)",
          "result": null
        },
        {
          "expression": "avg(@)",
          "result": null
        },
        {
          "expression": "avg(@.strings)",
          "result": null
        },
        {
          "expression": "avg(strings)",
          "result": null
        },
        {
          "expression": "ceil(@.dec[0])",
          "result": 2
        },
        {
          "expression": "ceil(dec[0])",
          "result": 2
        },
        {
          "expression": "ceil(@.dec[1])",
          "result": 2
        },
        {
          "expression": "ceil(dec[1])",
          "result": 2
        },
        {
          "expression": "ceil(@.dec[2])",
          "result": -1
        },
        {
          "expression": "ceil(dec[2])",
          "result": -1
        },
        {
          "expression": "ceil(abc)",
          "result": null
        },
        {
          "expression": "ceil(`abc`)",
          "result": null
        },
        {
          "expression": "concat(@.strings[0], strings[1], @.strings[2])",
          "result": "abc"
        },
        {
          "expression": "concat(strings[0], strings[1], @.strings[2], foo)",
          "result": "abc-1"
        },
        {
          "expression": "concat(@.strings[0], @.strings[1], strings[2], @)",
          "result": null
        },
        {
          "expression": "concat(`null`, `false`)",
          "result": null
        },
        {
          "expression": "concat(`foo`)",
          "error": "runtime"
        },
        {
          "expression": "concat()",
          "error": "runtime"
        },
        {
          "expression": "contains(`abc`, `a`)",
          "result": true
        },
        {
          "expression": "contains(`abc`, `d`)",
          "result": false
        },
        {
          "expression": "contains(`false`, `d`)",
          "result": null
        },
        {
          "expression": "contains(@.strings, `a`)",
          "result": true
        },
        {
          "expression": "contains(dec, `1.9`)",
          "result": true
        },
        {
          "expression": "contains(dec, `false`)",
          "result": null
        },
        {
          "expression": "length(@)",
          "result": 9
        },
        {
          "expression": "length(arr)",
          "result": 6
        },
        {
          "expression": "length(@.str)",
          "result": 3
        },
        {
          "expression": "floor(@.dec[0])",
          "result": 1
        },
        {
          "expression": "floor(dec[0])",
          "result": 1
        },
        {
          "expression": "floor(@.foo)",
          "result": -1
        },
        {
          "expression": "floor(@.str)",
          "result": null
        },
        {
          "expression": "get(@.empty)",
          "result": null
        },
        {
          "expression": "get(@.empty, @.\"false\")",
          "result": null
        },
        {
          "expression": "get(@.empty, @.\"false\", @.foo)",
          "result": -1
        },
        {
          "expression": "get(@.zero, `10`)",
          "result": 0
        },
        {
          "expression": "get(`null`, `false`, @.empty, `true`)",
          "result": true
        },
        {
          "expression": "join(`, `, str)",
          "result": null
        },
        {
          "expression": "join(`, `, strings)",
          "result": "a, b, c"
        },
        {
          "expression": "join(`|`, strings)",
          "result": "a|b|c"
        },
        {
          "expression": "join(`|`, @.dec)",
          "result": "1.01|1.9|-1.5"
        },
        {
          "expression": "join(`\"|\"`, @.empty)",
          "result": ""
        },
        {
          "expression": "keys(@)",
          "result": ["foo", "zero", "arr", "strings", "dec", "str", "false", "empty", "empty2"]
        },
        {
          "expression": "keys(@.empty2)",
          "result": []
        },
        {
          "expression": "keys(@.strings)",
          "result": null
        },
        {
          "expression": "keys(`abc`)",
          "result": null
        },
        {
          "expression": "keys(`false`)",
          "result": null
        },
        {
          "expression": "length(`abc`)",
          "result": 3
        },
        {
          "expression": "length(`\"\"`)",
          "result": 0
        },
        {
          "expression": "length(@.foo)",
          "result": null
        },
        {
          "expression": "length(@.strings[0])",
          "result": 1
        },
        {
          "expression": "length(`false`)",
          "result": null
        },
        {
          "expression": "max(@.arr)",
          "result": 5
        },
        {
          "expression": "max(arr)",
          "result": 5
        },
        {
          "expression": "max(@.dec)",
          "result": 1.9
        },
        {
          "expression": "max(abc)",
          "result": null
        },
        {
          "expression": "max(@.empty)",
          "result": null
        },
        {
          "expression": "min(@.arr)",
          "result": -1
        },
        {
          "expression": "min(@.dec)",
          "result": -1.5
        },
        {
          "expression": "min(abc)",
          "result": null
        },
        {
          "expression": "min(@.empty)",
          "result": null
        },
        {
          "expression": "sort(@.arr)",
          "result": [-1, 3, 4, 5, "a", "100"]
        },
        {
          "expression": "sort(@.strings)",
          "result":  ["a", "b", "c"]
        },
        {
          "expression": "sort(abc)",
          "result": null
        },
        {
          "expression": "sort(@.empty)",
          "result": []
        },
        {
          "expression": "sort(@)",
          "result": null
        },
        {
          "expression": "type(`abc`)",
          "result": "string"
        },
        {
          "expression": "type(`123`)",
          "result": "number"
        },
        {
          "expression": "type(`123`)",
          "result": "number"
        },
        {
          "expression": "type(`1.2`)",
          "result": "number"
        },
        {
          "expression": "type(`true`)",
          "result": "boolean"
        },
        {
          "expression": "type(`false`)",
          "result": "boolean"
        },
        {
          "expression": "type(@.empty)",
          "result": "array"
        },
        {
          "expression": "type(empty)",
          "result": "array"
        },
        {
          "expression": "type(@.strings)",
          "result": "array"
        },
        {
          "expression": "type(@)",
          "result": "object"
        }
      ]
    }, {
      "given":
        [
          {"foo": "baz", "bar": "bam"},
          {"foo": "123"},
          {"abc": "def", "fez": "qux"},
          [1, 2, 3],
          "abc",
          true
        ],
      "cases": [
        {
          "expression": "union(@[0], @[1])",
          "result": {"foo": "baz", "bar": "bam"}
        },
        {
          "expression": "union(@[0], @[2])",
          "result": {"foo": "baz", "bar": "bam", "abc": "def", "fez": "qux"}
        },
        {
          "expression": "union(@[3], @[4])",
          "result": null
        },
        {
          "expression": "union(true, false)",
          "result": null
        },
        {
          "expression": "values(@[0])",
          "result": ["baz", "bam"]
        },
        {
          "expression": "values(@[1])",
          "result": ["123"]
        },
        {
          "expression": "values(@[3])",
          "result": [1, 2, 3]
        },
        {
          "expression": "values(@[4])",
          "result": null
        }
      ]
    }]

History
=======

* This JEP originally proposed the literal syntax. The literal portion of this
  JEP was removed and added instead to JEP 7.
* Removed several functions that require more work on determining how we will
  support unicode inputs.