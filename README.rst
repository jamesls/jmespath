JMESPath
========

This is a special branch I use for verifying the
grammar through ply.  This helps ensure that the
grammar is not ambiguous, and that the grammar can
be specified via a LALR(1) parser.  To test:

1. modify parser/lexer modules as needed.
2. Sync/add compliance tests as needed.
3. Run test_ambiguous.py.  This will compile every JMESPath
   compliance test and ensure that ply does not complain
   about shift reduce conflicts.
