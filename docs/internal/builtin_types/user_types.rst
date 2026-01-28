User types
==========

These are types that are primarily created by users. Internally they 
are all held under an umbrella type, depending on whether they are 
a class or a function.

.. module:: representations.types.user_types 

    .. autoclass:: representations.types.user_types.UserType
        :members:
        :private-members:
        :show-inheritance:
    
    .. autoclass:: representations.types.user_types.FunctionType 
        :members:
        :private-members:
        :show-inheritance:
        :exclude-members: add_field, get_field, has_field 
    
    .. autoclass:: representations.types.user_types.InternalType
        :members:
        :private-members:
        :show-inheritance:
        :exclude-members: llvm_type, name, needs_refcount, add_field, get_field, has_field, castable_from, generate_from
