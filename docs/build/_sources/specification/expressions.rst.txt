Expressions
===========

Much like any language, expressions are used in a wide variety 
of ways in CBLang. Some examples include:

- A raw expression on a line (like ``function()``)
- The value of a variable 
- An argument to a function 
- The condition of an ``if`` statement.

.. note:: A raw expression is considered a :doc:`statement <statements>`

Expressions are made up of "primary" units separated by operators.
A primary unit can mean a lot of things:

- A literal 
- A function call 
- A variable 
- A lambda (``{ ... }``)
- Another expression wrapped in parentheses
- A list wrapped in brackets

Operators can be used on those primary values, but they are obviously 
not guaranteed to be valid. Here are all the operators in CBLang, 
ordered by `precedence <https://en.wikipedia.org/wiki/Order_of_operations>`_
from lowest to highest:

- ``||`` or ``or``
- ``&&`` or ``and``
- ``==`` and ``!=``
- ``>``, ``>=``, ``<``, and ``<=``
- ``+`` and ``-``
- ``*`` and ``/``
- ``!`` and ``-`` (which are unary)

An operator corresponds to a function call on the leftmost operand, 
passing in the rightmost operand if it exists. Custom operators on 
types may be defined.