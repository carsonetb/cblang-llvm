Statements 
==========

Statements appear in code blocks in CBLang, which is what makes statements 
different from declarations (although there is some overlap).

Depending on the type of statement, it may or may not end in a semicolon.
The rule of thumb is that if the statement ends in a code block, then it 
probably doesn't need a semicolon. 

Below is a list of statements that require semicolons:

- Raw :doc:`expressions <expressions>`
- Setting variables 
- Variable declarations 
- Return statements 
- Import statements

And a list of statements that don't require semicolons:

- ``if`` statements 
- ``while`` statements 
- ``for`` statements

Different statements do wildly different things---they are what makes code 
actually do stuff.

Setting variables 
-----------------

You can override any variable with another, as long as the type is the same.
A variable can be reset to a literal, another variable, or the result of a 
function call. If it is a non-primitive type, array, or string, the variable 
will *reference* that value, and otherwise the value will be *copied* and put 
into the variable.

Some examples of setting variables:

.. code-block:: c

    x = 1;
    y = 2.5;
    z = 2;
    z = x; // z becomes 1
    w = int_generate(); 

.. note:: In the above example, no variables are being created, just set.

Variable declarations 
---------------------

Declaring a variable is very similar to setting a variable, except for that 
you have to specify its type before the variable name.

.. code-block:: c 

    int x = 1;
    Obj object = Obj(x);

Return statements 
-----------------

Inside of a function, if you want to return a value, you can use the ``return``
statement. It can optionally have an expression to return from the function. 
You can only return from inside a function.

.. code-block:: c

    return object.num + 1;

Import statements 
-----------------

Import statements are special, because they can't occur in a code block. They 
*must* happen at the start of the file, before any other declarations. This is 
for your own sake, because it makes the files more readable. 

Imports are relative to the main file of the project that is being compiled. 
Instead of paths (``folder/package/file.cblang``) separate folder and file names 
with a ``.``, so importing the previous file would be more like:

.. code-block:: c 

    import folder.package.file 

.. note:: You do not need to include the extension of the file (``.cblang``).

When accessing something from the other class (like a function, variable or class),
you can use the name of the file (in this case literally ``file``) as the module name.
So if you were to access class ``Obj`` from ``file`` you would access it with 
``file.Obj``.

.. warning:: Import statements are currently not implemented and won't do anything,
    although they are valid in the AST.