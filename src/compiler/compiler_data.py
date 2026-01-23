

from dataclasses import dataclass

from llvmlite import ir
import llvmlite.binding as llvm

from ast_classes import Program
from representations.field import ValueField
from representations.types.base_type import Type
from runtime.c_runtime import CRuntime
from runtime.rc_runtime import RCRuntime


@dataclass
class CompilerData:
    program: Program
    target_machine: llvm.TargetMachine
    module_name: str
    module: ir.Module
    c_runtime: CRuntime
    rc_runtime: RCRuntime
    type_db: dict[str, Type]
    path_array: list[str]
    builder_stack: list[ir.IRBuilder]
    scoped_variables: list[dict[str, ValueField]]
    inside_ptr: ir.Value | None = None # The class passed to the function currently being processed.