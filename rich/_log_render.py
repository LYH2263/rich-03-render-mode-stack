from datetime import datetime
from typing import Iterable, List, Optional, TYPE_CHECKING, Tuple, Union, Callable


from .text import Text, TextType

if TYPE_CHECKING:
    from .console import (
        Console,
        ConsoleOptions,
        ConsoleRenderable,
        RenderableType,
        RenderResult,
    )
    from .table import Table

FormatTimeCallable = Callable[[datetime], Text]


class _SoftLogRow:
    """A log row rendered without width constraining.

    Soft wrap mode (see :meth:`rich.console.Console.use_render_mode`) makes
    :meth:`~rich.console.Console.log` behave like ``print(soft_wrap=True)``:
    content is neither wrapped nor cropped to the console width. The usual log
    layout still joins its time, level, message and path cells with single
    spaces, but without putting them through a (measuring, cropping) Table.
    """

    def __init__(
        self,
        cells: List[Tuple["RenderableType", Optional[str], Optional[int]]],
    ) -> None:
        # Each cell is (renderable, optional column style, optional fixed width).
        self.cells = cells

    def __rich_console__(
        self, console: "Console", options: "ConsoleOptions"
    ) -> "RenderResult":
        from .segment import Segment

        soft_options = options.update(no_wrap=True, overflow="ignore")
        rendered: List[Tuple[List[List[Segment]], int]] = []
        for renderable, column_style, fixed_width in self.cells:
            segments = console.render(renderable, soft_options)
            if column_style:
                segments = Segment.apply_style(
                    segments, console.get_style(column_style)
                )
            lines = list(Segment.split_lines(list(segments)))
            # A trailing newline (e.g. the print ``end``) becomes an empty
            # trailing line; the row itself emits its own line break.
            if len(lines) > 1 and not lines[-1]:
                lines.pop()
            if not lines:
                lines = [[]]
            if fixed_width is not None:
                width = fixed_width
            else:
                width = max(Segment.get_line_length(line) for line in lines)
            rendered.append((lines, width))

        height = max(len(lines) for lines, _ in rendered)
        new_line = Segment.line()
        for line_no in range(height):
            row: List[Segment] = []
            for cell_no, (lines, width) in enumerate(rendered):
                if cell_no:
                    # One space of inter-column padding, as in the normal grid.
                    row.append(Segment(" "))
                if line_no < len(lines):
                    line = lines[line_no]
                    row.extend(line)
                    missing = width - Segment.get_line_length(line)
                    if missing > 0:
                        row.append(Segment(" " * missing))
                else:
                    row.append(Segment(" " * width))
            # Soft wrapped output is not padded to the console width: drop
            # trailing filler spaces (but never control segments).
            while row and not row[-1].control:
                stripped_text = row[-1].text.rstrip(" ")
                if stripped_text == row[-1].text:
                    break
                if stripped_text:
                    row[-1] = Segment(stripped_text, row[-1].style)
                    break
                row.pop()
            yield from row
            yield new_line


class LogRender:
    def __init__(
        self,
        show_time: bool = True,
        show_level: bool = False,
        show_path: bool = True,
        time_format: Union[str, FormatTimeCallable] = "[%x %X]",
        omit_repeated_times: bool = True,
        level_width: Optional[int] = 8,
    ) -> None:
        self.show_time = show_time
        self.show_level = show_level
        self.show_path = show_path
        self.time_format = time_format
        self.omit_repeated_times = omit_repeated_times
        self.level_width = level_width
        self._last_time: Optional[Text] = None

    def __call__(
        self,
        console: "Console",
        renderables: Iterable["ConsoleRenderable"],
        log_time: Optional[datetime] = None,
        time_format: Optional[Union[str, FormatTimeCallable]] = None,
        level: TextType = "",
        path: Optional[str] = None,
        line_no: Optional[int] = None,
        link_path: Optional[str] = None,
    ) -> Union["Table", _SoftLogRow]:
        from .containers import Renderables
        from .table import Table

        # (renderable, column style, fixed width)
        cells: List[Tuple["RenderableType", Optional[str], Optional[int]]] = []
        if self.show_time:
            log_time = log_time or console.get_datetime()
            time_format = time_format or self.time_format
            if callable(time_format):
                log_time_display = time_format(log_time)
            else:
                log_time_display = Text(log_time.strftime(time_format))
            if log_time_display == self._last_time and self.omit_repeated_times:
                log_time_display = Text(" " * len(log_time_display))
            else:
                self._last_time = log_time_display
            cells.append((log_time_display, "log.time", None))
        if self.show_level:
            cells.append((level, "log.level", self.level_width))

        cells.append((Renderables(renderables), "log.message", None))
        if self.show_path and path:
            path_text = Text()
            path_text.append(
                path, style=f"link file://{link_path}" if link_path else ""
            )
            if line_no:
                path_text.append(":")
                path_text.append(
                    f"{line_no}",
                    style=f"link file://{link_path}#{line_no}" if link_path else "",
                )
            cells.append((path_text, "log.path", None))

        if console.soft_wrap:
            # No wrapping or cropping at all, mirroring print(soft_wrap=True).
            return _SoftLogRow(cells)

        output = Table.grid(padding=(0, 1))
        output.expand = True
        for renderable, column_style, fixed_width in cells:
            if fixed_width is not None:
                output.add_column(style=column_style, width=fixed_width)
            elif column_style == "log.message":
                output.add_column(ratio=1, style=column_style, overflow="fold")
            else:
                output.add_column(style=column_style)
        output.add_row(*(renderable for renderable, _, _ in cells))
        return output


if __name__ == "__main__":  # pragma: no cover
    from rich.console import Console

    c = Console()
    c.print("[on blue]Hello", justify="right")
    c.log("[on blue]hello", justify="right")
