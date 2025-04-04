#!/usr/bin/env python
"""
Simple script to generate stub files for the clingo python module.
"""

import inspect
import os.path
import re
import types
from textwrap import indent

from mako.template import Template

import clingo

TYPING_TYPES = [
    "AbstractSet",
    "Any",
    "AnyStr",
    "AsyncContextManager",
    "AsyncGenerator",
    "AsyncIterable",
    "AsyncIterator",
    "Awaitable",
    "AwaitableGenerator",
    "BinaryIO",
    "ByteString",
    "Callable",
    "ChainMap",
    "Collection",
    "Container",
    "ContextManager",
    "Coroutine",
    "Counter",
    "DefaultDict",
    "Deque",
    "Dict",
    "FrozenSet",
    "Generator",
    "Generic",
    "GenericMeta",
    "Hashable",
    "IO",
    "ItemsView",
    "Iterable",
    "Iterator",
    "KeysView",
    "List",
    "Mapping",
    "MappingView",
    "Match",
    "MutableMapping",
    "MutableSequence",
    "MutableSet",
    "NamedTuple",
    "NoReturn",
    "Optional",
    "Pattern",
    "Protocol",
    "Reversible",
    "Sequence",
    "Set",
    "Sized",
    "SupportsAbs",
    "SupportsBytes",
    "SupportsComplex",
    "SupportsFloat",
    "SupportsIndex",
    "SupportsInt",
    "SupportsRound",
    "Text",
    "TextIO",
    "Tuple",
    "TypeAlias",
    "TypeVar",
    "Union",
    "ValuesView",
]


class TypeTemplate(Template):
    """
    Patched template class to only add used types from typing module.
    """

    def render(self, *args, **kwargs):
        """
        This heuristicly adds types from a curated list used in the template to
        the import list.
        """
        s = Template.render(self, *args, **kwargs)
        type_list = []
        for x in TYPING_TYPES:
            if re.search(r"\b{}\b".format(x), s):
                type_list.append(x)

        return s.replace("{TYPES}", ", ".join(type_list))


BASE = os.path.dirname(__file__)

TYPES_TEMPLATE = TypeTemplate(
    """\
# DO NOT EDIT THIS FILE! It was generated by scratch/mypy.py.

from typing import {TYPES}


C = TypeVar("C", bound="Comparable")


class Comparable(Protocol):
    def __lt__(self, other: C) -> bool: ...
    def __gt__(self, other: C) -> bool: ...
    def __le__(self, other: C) -> bool: ...
    def __ge__(self, other: C) -> bool: ...


Key = TypeVar('Key')
Value = TypeVar('Value')
class Lookup(Generic[Key], Collection[Value]):
    def __getitem__(self, key: Key) -> Optional[Value]: ...
"""
)

CLASS_TEMPLATE = Template(
    """\
class ${sig}:
% for x in functions:
${indent(x.stub(), "    ")}
% endfor
% for x in variables:
    ${x.stub()}
% endfor
% if not functions and not variables:
    pass
% endif
"""
)

MODULE_TEMPLATE = TypeTemplate(
    """\
# DO NOT EDIT THIS FILE! It was generated by scratch/mypy.py.

from typing import {TYPES}
from abc import ABCMeta

from .types import Comparable, Lookup
from . import ast


% for x in variables:
${x.stub()}
% endfor


% for x in functions:
${x.stub()}
% endfor


% for x in classes:
${x.stub()}
% endfor
"""
)


def get_sig(value):
    """
    Extract the signature of a docstring.
    """
    return value.__doc__.strip().splitlines()[0]


class Function:
    """
    Something that resembles a function.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def stub(self):
        """
        Generate stub for function.
        """
        if self.value.__doc__ is None:
            return "def {}(*args: Any, **kwargs: Any) -> Any: ...".format(self.name)
        return "def {}: ...".format(get_sig(self.value))


class Other:
    """
    Something arbitrary.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def stub(self):
        """
        Generate stub.
        """
        return self.value


class Property:
    """
    Something that resembles a property (with a docstring).
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def stub(self):
        """
        Generate stub for property.
        """
        return "{}".format(get_sig(self.value))


class Variable:
    """
    Something that resembles a member variable.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def stub(self):
        """
        Generate stub for member variable.
        """
        return "{}: {}".format(self.name, self.value.__class__.__name__)


class Class:
    """
    Something that resembles a class.
    """

    def __init__(self, name, value):
        self.name = name
        self.value = value

    def declare(self):
        """
        Generate a forward declaration for the class.
        """
        return '{} = ForwardRef("{}")'.format(self.name, self.name)

    def stub(self):
        """
        Generate stub for class.
        """
        doc = self.value.__doc__.strip()
        abstract = not doc.startswith("{}(".format(self.name))

        anc = []
        match = re.search(r"Implements: `[^`]*`(, `[^`]*`)*", doc)
        if match is not None:
            for match in re.finditer(r"`([^`]*)`", match.group(0)):
                anc.append(match.group(1))
        if abstract:
            anc.append("metaclass=ABCMeta")

        sig = "{}({})".format(self.name, ", ".join(anc)) if anc else self.name

        functions = []
        variables = []

        if not abstract:
            init = doc.splitlines()[0].strip()
            init = init.replace(self.name + "(", "__init__(self, ", 1)
            init = init.replace(" -> {}".format(self.name), "")
            functions.append(Other("__init__", "def {}: ...".format(init)))

        for name, value in sorted(self.value.__dict__.items(), key=lambda x: x[0]):
            if name.startswith("_"):
                continue
            if inspect.ismethoddescriptor(value):
                functions.append(Function(name, value))
            elif inspect.isgetsetdescriptor(value):
                variables.append(Property(name, value))
            else:
                variables.append(Variable(name, value))

        return CLASS_TEMPLATE.render(
            indent=indent, sig=sig, variables=variables, functions=functions
        )


class Module:
    """
    Something that resembles a module.
    """

    def __init__(self, name, value, classes=()):
        self.name = name
        self.value = value
        self.classes = classes

    def stub(self):
        """
        Print stub for module.
        """
        functions = []
        classes = list(self.classes)
        modules = []
        variables = []

        for name, value in sorted(self.value.__dict__.items(), key=lambda x: x[0]):
            if name.startswith("_") and name != "__version__":
                continue
            if isinstance(value, type):
                if value.__doc__ is None:
                    continue
                classes.append(Class(name, value))
            elif isinstance(value, types.BuiltinFunctionType):
                functions.append(Function(name, value))
            elif isinstance(value, types.ModuleType):
                modules.append((name, value))
            else:
                variables.append(Variable(name, value))

        return (
            MODULE_TEMPLATE.render(
                classes=classes, functions=functions, variables=variables
            ).rstrip()
            + "\n"
        )


def parse_class(name, doc):
    """
    Extract a class declaration from a docstring.
    """
    match = re.search(r"class ({}(\([^)]*\))?):".format(name), doc)
    csig = match.group(1)

    start = match.start()
    end = doc.find("```", start)
    doc = doc[start:end]

    variables = []
    start = doc.find("Attributes")
    end = doc.find('"""', start)
    attributes = doc[start:end]
    for match in re.finditer(r"^    ([^ :]*): (.*)$", attributes, flags=re.MULTILINE):
        variables.append(
            Other(match.group(1), "{}: {}".format(match.group(1), match.group(2)))
        )

    functions = []
    for match in re.finditer(
        r"(@abstractmethod.*?)?(def .*? -> .*?:)", doc, flags=re.MULTILINE | re.DOTALL
    ):
        fsig = match.group(2)
        fun = re.match(r"def ([^(]*)", fsig).group(1)
        fsig = re.sub("\n *", " ", fsig, flags=re.MULTILINE)
        if match.group(1) is not None:
            fsig = "@abstractmethod\n{}".format(fsig)
        functions.append(Other(fun, "{} ...".format(fsig)))

    return CLASS_TEMPLATE.render(
        indent=indent, sig=csig, functions=functions, variables=variables
    )


def main():
    """
    Write the types.pyi, __init__.pyi, ast.pyi files for the clingo module.

    The files are completely generated from the docstrings.
    """
    classes = [
        Other("Application", parse_class("Application", clingo.clingo_main.__doc__)),
        Other(
            "Propagator",
            parse_class("Propagator", clingo.Control.register_propagator.__doc__),
        ),
        Other(
            "Observer",
            parse_class("Observer", clingo.Control.register_observer.__doc__),
        ),
    ]

    with open(
        os.path.join(BASE, "..", "libpyclingo", "clingo", "types.pyi"), "w"
    ) as handle:
        handle.write(TYPES_TEMPLATE.render())

    with open(
        os.path.join(BASE, "..", "libpyclingo", "clingo", "__init__.pyi"), "w"
    ) as handle:
        handle.write(Module("clingo", clingo, classes).stub())

    with open(
        os.path.join(BASE, "..", "libpyclingo", "clingo", "ast.pyi"), "w"
    ) as handle:
        handle.write(Module("clingo.ast", clingo.ast).stub())


if __name__ == "__main__":
    main()
