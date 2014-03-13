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


_SENTINEL = object()


class _VirtualParent(object):
    def __init__(self):
        self.children = [_SENTINEL]


class ProjectionTransform(object):

    def transform(self, node):
        parents = {}
        self._virtual_parent = _VirtualParent()
        parents = {node: (self._virtual_parent, 0)}
        self._transform(node, parents)
        # Sometimes the passed in node is replaced completely
        # with a projection.  In this case, we can check the
        # virtual parent to confirm, and return it's new child
        # as the new node.
        if self._virtual_parent.children[0] is not _SENTINEL:
            return self._virtual_parent.children[0]
        else:
            return node

    def _transform(self, node, parents):
        for i, child in enumerate(node.children):
            parents[child] = (node, i)
            self._transform(child, parents)
        if isinstance(node, ast.IndexExpression) and \
                isinstance(node.children[1], (ast.WildcardIndex,
                                              ast.WildcardValues)):
            if isinstance(node.children[1], ast.WildcardIndex):
                projection_class = ast.Projection
            else:
                projection_class = ast.ValueProjection
            # When we hit a node that triggers
            # a projection, the parent node has its
            # first child assigned to a projection.
            # This is a property of the way the AST is created
            # from the parser.
            parent = parents[node][0]
            left = node.children[0]
            if parents[node][1] == 0:
                # Left child.
                parent.children[0] = ast.Identity()
            # Then walk all the way back up until we find something
            # that stops the projection.
            current = node
            while True:
                if isinstance(parents[current][0],
                              (_VirtualParent, ast.ORExpression, ast.Pipe,
                               ast.MultiFieldList, ast.MultiFieldDict,
                               ast.KeyValPair, ast.FunctionExpression,
                               ast.Projection, ast.ValueProjection)):
                    break
                else:
                    current = parents[current][0]
            # If current is still node it means our parent terminates
            # the expression.  The right now should be an identity
            # node then.
            if current is node:
                right = ast.Identity()
            else:
                # Now current represents the child node of the projection.
                right = current
            projection = projection_class(left, right)
            index = parents[current][1]
            parents[current][0].children[index] = projection
            parents[right] = (projection, 1)
