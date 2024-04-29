from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any
    from typing_extensions import TypedDict

    ResetInfo = TypedDict("ResetInfo", {"obj": Any, "attr": str, "value": str})  # value = file
    FileoutputNodes = TypedDict(
        "FileoutputNodes", {"obj": Any, "value": str, "fpath": str}
    )  # value = file
    ResetFilepath = TypedDict("ResetFilepath", {"o": Any, "value": str})

    FileInfo = TypedDict(
        "FileInfo", {"obj": Any, "mod": Any, "pc": Any, "path": str, "name": str,},
    )
