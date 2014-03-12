"""
Transformating Projections
==========================

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
            (function-expression "to_number" (function-arg current-node))))

This once again makes the projection explicit and makes the scope of the
projection clear. This is especially useful in the case of pipes where the
projections do not carry across child nodes of a pipe expression.


"""
from jmespath import ast


class ProjectionTransform(object):
    def __init__(self):
        self.parents = {}

    def transform(self, node):
        if not isinstance(node, ast.WildcardIndex):
            for child in node.children:
                self.parents[child] = node
                result = self.transform(child)
                if result is not None:
                    return result
        else:
            # When we hit a node that triggers
            # a projection, the parent node has its
            # first child assigned to a projection.
            parent = self.parents[node]
            grandparent = self.parents[parent]
            left = parent.children[0]
            orphan = grandparent.children[1]
            self.parents[grandparent].children[0] = orphan
            # To find the right node, we need to traverse
            # all the way up until we can't go any higher.
            current = node
            while True:
                next_element = self.parents.get(current)
                if next_element is None:
                    break
                current = next_element
            right = current
            projection = ast.Projection(left, right)
            return projection
