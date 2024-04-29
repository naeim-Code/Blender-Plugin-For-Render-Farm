from __future__ import annotations

import os
import bpy
from .validator import Validator, TestResult, ResultHelper

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List
    from bpy.types import Operator  # pylint: disable = no-name-in-module, import-error
    from .renderConfiguration import Config


class ValGeneral(Validator):
    def getName(self) -> str:
        return "General"

    def test(self, results_: List[TestResult]) -> None:
        results = ResultHelper(results_, self)
        errorinstallplugs = os.path.join(
            self.mainDialog.m_defaultPath, "at2_reb_errorinstallplugs.txt"
        )
        if os.path.exists(errorinstallplugs):
            results.error(
                'Farminizer was not installed correctly, please close Blender and call "Reinstall Plugins" from Farm Desk!'
            )

        if not os.path.exists(bpy.data.filepath):
            results.error("Please save the project before exporting to Farm Desk!", type_= 11)

    def prepareSave(self, export_folder: str, assets: List[str], scene_settings: "Config") -> None:
        return

    def postSave(self) -> None:
        return
