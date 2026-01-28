Declarations 
============

Declarations are how you structure your code. They let you define classes,
functions, and member/global variables. Their syntax is more complex than 
simple statements or expressions. Declarations will never have a semicolon 
at the end, because they do not appear in code blocks. In the global scope,
they aren't separated by anything.

Class declarations 
------------------

... Description for classes here 

Syntax 
^^^^^^

This pseudocode demonstrates the syntax for a class declaration:

.. code-block:: c

    class Name : Extends, Inherits (Type param, int param2, ...) = (
        ...
    )

You don't necessarily have to include all of this syntax, though. If the type 
doesn't inherit another type, you don't need the colon. In addition, if it doesn't 
take any parameters, you don't need to include empty parentheses. For example, 
this is a more minimal class declaration:

.. code-block:: c 

    class Simple = (
        ...
    )

The parameters passed to the class act the same as member variables. You can 
manipulate them inside the ``init`` function which has no parameters and does 
not return anything.

Inside the class body you can define member variables, member functions, and 
even internal classes. Each of these is separated by a comma. Here is an example 
of a basic class that defines all three types:

.. code-block:: c

    class Name = (
        int x = 1,

        scope init = {
            ...
        },

        class Internal = (
            ...
        )
    )

Casting 
^^^^^^^

Types may also define types that they can be implicitly casted from using the 
``cast`` function decorator:

.. code-block:: c

    cast scope (Type other) -> ThisType = {
        ...
    }

A ``cast`` function must return the same type that it is inside of.

Operator overloading
^^^^^^^^^^^^^^^^^^^^

Types may define custom functions for operators. If the operator is binary, the 
other class is passed as a parameter, and if the operator is unary, no parameters 
are passed. The operator function may return any variable, as long as the type is 
the same as the class the function is inside of. But you should probably return 
a new variable, because operators generally should not modify the operands.

.. code-block:: c 

    operator scope + (Type other) -> ThisType = {
        ...
    }

    operator scope ! -> ThisType = { // Unary operators don't take any parameters.
        ...
    }

.. warning:: 
    A few of the features for classes described above are not yet implemented:

    - Inheritance
    - Internal classes
    - Cast and operator functions