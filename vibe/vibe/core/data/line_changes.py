from dataclasses import dataclass


@dataclass
class LineNumbered:
    line_number: int
    content: bytes


@dataclass
class Addition(LineNumbered):
    """Represents a single added line of code."""

    ...


@dataclass
class Removal(LineNumbered):
    """Represents a single removed line of code."""

    ...


@dataclass(init=False)
class Move(LineNumbered):
    from_line: int
    to_line: int

    def __init__(self, content: bytes, from_line: int, to_line: int):
        self.content = content
        self.from_line = from_line
        self.to_line = to_line
        # line number will be the to_line in this case
        self.line_number = to_line


@dataclass(init=False)
class Replacement(LineNumbered):
    """Represents a line of code replaced with another, on the same line"""

    old_content: bytes
    new_content: bytes

    def __init__(self, old_content: bytes, new_content: bytes, line_number: int):
        self.old_content = old_content
        self.new_content = new_content
        self.content = new_content  # you can think of it as the final content state
        self.line_number = line_number
