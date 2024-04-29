from __future__ import annotations
from .validator import Validator, TestResult, ResultHelper

import bpy

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import List, Any
    from .renderConfiguration import Config

    from .typAliases import ResetInfo


class ValVray(Validator):
    files: List[str] = []
    postSaveReset: List[ResetInfo] = []

    def getName(self) -> str:
        return "Vray"

    def has_work(self, scene: Any) -> bool:
        vray_renderers = ["VRAY_RENDER", "VRAY_RENDER_PREVIEW"]
        return "vray" in scene and scene.render.engine in vray_renderers

    def test(self, results_: List[TestResult]) -> None:
        results = ResultHelper(results_, self)
        scene = bpy.context.scene

        if not self.has_work(scene):
            return None

        results.error("V-Ray is currently not supported for Blender.") 

    def prepareSave(self, export_folder: str, assets: List[str], scene_settings: "Config") -> None:
        return None

    def postSave(self) -> None:
        return None
