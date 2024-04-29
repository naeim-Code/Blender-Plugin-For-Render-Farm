from __future__ import annotations
import bpy
import platform
import os
from contextlib import suppress

from .validator import Validator, TestResult, ResultHelper
from .utilitis import (
    createFarmOutputPath,
    is_gpu_render,
    isPictureFormat,
    isDRPictureFormat,
    generateLocalOutputPath,
)

from typing import TYPE_CHECKING, List, Iterable, Any, Tuple, cast

if TYPE_CHECKING:
    from bpy.types import Operator  # pylint: disable = no-name-in-module, import-error
    from .renderConfiguration import Config
    from .typAliases import ResetFilepath, FileoutputNodes


class ValRendersettings(Validator):
    outputFilepath = ""
    threadsMode = ""
    fileQuality = 100
    debugTileSize = 32
    debugMinSize = 32
    user_frame_current = 0
    postsaveResetFilepath: List[FileoutputNodes] = []
    unique_node_id = 0

    def getName(self) -> str:
        return "Render Settings"

    def basePathForOutputNode(self, node: Any) -> str:
        try:
            folder, filename = cast(Tuple[str, str], os.path.split(node.base_path))
            return filename or folder
        except:
            return ""

    def getFileOutputNodes(self) -> List[FileoutputNodes]:
        try:
            nodes = bpy.context.scene.node_tree.nodes
            return [
                {"obj": node, "value": node.base_path, "fpath": self.basePathForOutputNode(node)}
                for node in nodes
                if node.type == "OUTPUT_FILE"
            ]
        except:
            return []

    def findBlacklistedNodes(self) -> List[Any]:
        blacklist = [
            "BILATERALBLUR",
            "BLUR",
            "BOKEHBLUR",
            "DEFOCUS",
            "DESPECKLE",
            "DILATEERODE",
            "DBLUR",
            "FILTER",
            "GLARE",
            "INPAINT",
            "PIXELATE",
            "SUNBEAMS",
            "VECBLUR",
            "NORMALIZE",
            "BOXMASK",
            "ELLIPSEMASK",
            "CORNERPIN",
            "CROP",
            "DISPLACE",
            "FLIP",
            "LENSDIST",
            "MAP_UV",
            "MOVIEDISTORTION",
            "PLANETRACKDEFORM",
            "ROTATE",
            "SCALE",
            "STABILIZE2D",
            "TRANSFORM",
            "TRANSLATE",
        ]
        try:
            nodes = bpy.context.scene.node_tree.nodes
            return [node for node in nodes if node.type in blacklist]
        except:
            return []

    def testForScriptedExpressions(self, drivers: Iterable[Any], results: ResultHelper) -> None:
        for obj in drivers:
            with suppress(Exception):
                for driver in obj.animation_data.drivers:
                    with suppress(Exception):
                        if driver.driver.type == "SCRIPTED":
                            results.error(
                                f"Scripted Expressions are unsupported. ( Object: '{obj.name}', Expression: {driver.driver.expression} ) ",
                                type_= 7, info_1= obj.name, info_2= driver.driver.expression
                            )

    def test(self, results_: List[TestResult]) -> None:
        results = ResultHelper(results_, self)
        scene = bpy.context.scene
        renderEngines = {
            "CYCLES",
            "BLENDER_EEVEE",
            "octane",
            "LUXCORE"
        }  # , 'VRAY_RENDER', 'VRAY_RENDER_PREVIEW' }
        if not scene.render.engine in renderEngines:
            results.error("Engine: Render engine not supported")
        if not scene.camera:
            results.error("Camera: Camera missing. Add a camera object to the scene.", type_= 9)
        # else:
        #     results.info(f'Camera: Render camera is "{scene.camera.name}"')
        layerCount = 0
        for layer in scene.view_layers:
            if layer.use:
                results.info(f'Layers: Active Render Layer is "{layer.name}"')
                layerCount += 1
        if layerCount == 0:
            results.error("Layers: No Render Layer is active")
        if scene.render.resolution_x < 300:
            results.warn("Dimensions: Resolution X seems to be very low")
        if not self.mainDialog.m_distributed and scene.render.resolution_x > 1920:
            results.warn("Dimensions: Resolution X seems to be very high")
        if scene.render.resolution_y < 300:
            results.warn("Dimensions: Resolution Y seems to be very low")
        if not self.mainDialog.m_distributed and scene.render.resolution_y > 1920:
            results.warn("Dimensions: Resolution Y seems to be very high")
        if scene.render.resolution_percentage != 100:
            results.warn("Dimensions: Resolution Percentage is not 100%")
        # if scene.frame_start == bpy.context.scene.frame_end:
        # results.error("Dimensions: Frame Range has to contain more than one frame")
        if scene.frame_step != 1:
            results.error("Dimensions: Frame Range Step has to be 1")
        if scene.render.use_border:
            results.warn("Dimensions: Border is active", type_= 13)
        if scene.render.use_border and scene.render.use_crop_to_border:
            results.warn("Dimensions: Crop is active")
        if scene.render.use_stamp:
            results.error("Stamp: not allowed")

        render_path = bpy.path.abspath(scene.render.filepath)
        output_file_name = os.path.basename(render_path)
        render_dir = os.path.dirname(render_path)
        # if len(os.path.basename(scene.render.filepath)) == 0 and not scene.render.engine in {
        #     "VRAY_RENDER",
        #     "VRAY_RENDER_PREVIEW",
        # }:
        if not os.path.exists(render_dir) or not output_file_name:
            results.error("Output: Requires filename", type_= 2, info_1= scene.name)

        tiff_codec = None
        try:
            file_format = scene.render.image_settings.file_format
            color_mode = scene.render.image_settings.color_mode
            tiff_codec = scene.render.image_settings.tiff_codec
        except:
            file_format = scene.render.file_format
            color_mode = scene.render.color_mode

        if not isPictureFormat(file_format):
            results.error("Output: Only single image formats are supported", type_= 2, info_1= scene.name)

        if file_format == "TIFF" and tiff_codec == "NONE":
            results.error("Output: TIFF Compression must be activated")

        with suppress(Exception):
            if scene.render.engine == "BLENDER_RENDER":
                if not scene.render.use_antialiasing:
                    results.warn("Anti-Aliasing: AA is disabled")
                else:
                    if int(scene.render.antialiasing_samples) >= 16:
                        results.warn(
                            f"Anti-Aliasing: Samples {scene.render.antialiasing_samples} seems very high"
                        )
                if scene.render.use_motion_blur:
                    results.warn("Samples motion blur: Motion blur is enabled")
                if not scene.render.use_textures:
                    results.warn("Shading: Textures are disabled")
                if not scene.render.use_shadows:
                    results.warn("Shading: Shadows are disabled")
                if not scene.render.use_raytrace:
                    results.warn("Shading: Ray Tracing is disabled")
                # if scene.render.threads_mode != 'AUTO':
                # results.error("Performance: Threads have to be set to Auto-detect")
                if scene.render.use_fields:
                    results.warn("Post Processing: Fields is active")
                if scene.render.use_edge_enhance:
                    results.warn("Post Processing: Edge is active")
                if color_mode == "BW":
                    results.warn('Output: "BW" is active')

        if self.mainDialog.m_distributed:
            if not isDRPictureFormat(file_format):
                results.error(
                    "Output: File format not allowed for distributed render - use PNG instead"
                )
            if scene.render.use_compositing:
                nodes = self.findBlacklistedNodes()
                if len(nodes) > 0:
                    st = ""
                    for i, node in enumerate(nodes):
                        if i > 3:
                            st += "..."
                            break
                        st += f"{node.name}, "

                    results.error(
                        "Post Processing: These nodes are not supported for distributed render: "
                        + st
                    )
            if scene.render.use_freestyle:
                results.error(
                    "Freestyle: Because of a bug in Blender, currently not allowed for distributed render."
                )
            if scene.render.resolution_x % 10 != 0 or scene.render.resolution_y % 10 != 0:
                results.error(
                    "Output: for distributed rendering your resolution must be divisible by ten."
                )
            if file_format in ["BMP", "PNG", "TIFF"] and (
                scene.render.resolution_x > 16000 or scene.render.resolution_y > 16000
            ):
                results.error(
                    "Output: format not supported for resolutions over 16000, use EXR instead."
                )
        if scene.render.engine == "CYCLES":
            if is_gpu_render():
                if self.mainDialog.m_distributed:
                    results.info(
                        "Cycles Device: Distributed render is only supported on CPU so your job will render on CPU instead."
                    )
                else:
                    results.info("Cycles Device: GPU Rendering is much more expensive than CPU.\n We recommend you to run CPU rendering, as you will spare money and still get a fast result")
            elif scene.cycles.device == "CPU":
                results.info("Cycles Device: Sky will render your scene on CPU.")
            if scene.cycles.samples > 666:
                results.warn("Cycles: Samples seem to be very high", type_= 12)
        if scene.render.engine == "BLENDER_EEVEE":
            results.warn("ATTENTION. Blender Eevee is implemented as Beta for testing.")
            results.info("Eevee: GPU Rendering is much more expensive than CPU.\n We recommend you to run CPU rendering, as you will spare money and still get a fast result")

        # test compositing node output path is set
        nodes = self.getFileOutputNodes()
        for node in nodes:
            if node["fpath"] == "":
                results.error(
                    f"Compositing Node( File Output ): 'Base Path' unset. ( {node['obj'].name} ) "
                )
            elif node["fpath"] == scene.render.filepath:
                results.error(
                    f"Compositing Node( File Output ): 'Render Output Path' and 'Node Base Path' must be different. ( {node['obj'].name} ) "
                )

        # test if drivers have scripted expressions
        self.testForScriptedExpressions(bpy.data.objects, results)
        self.testForScriptedExpressions(bpy.data.textures, results)
        self.testForScriptedExpressions(bpy.data.materials, results)
        self.testForScriptedExpressions(bpy.data.particles, results)
        self.testForScriptedExpressions(bpy.data.worlds, results)

    def furtherAction(self, op: Operator, result: TestResult) -> None:
        op.report({"ERROR"}, result.message)

    def prepareSave(
        self, _export_folder: str, assets: List[str], scene_settings: "Config"
    ) -> None:
        scene = bpy.context.scene

        abs_path = bpy.path.abspath(scene.render.filepath)
        output_file_name = os.path.basename(abs_path)
        self.outputFilepath = scene.render.filepath
        outputPath = createFarmOutputPath(self.mainDialog.m_userName, output_file_name)
        scene.render.filepath = outputPath

        self.threadsMode = scene.render.threads_mode
        scene.render.threads_mode = "AUTO"

        try:
            self.fileQuality = scene.render.image_settings.quality
            scene.render.image_settings.quality = 100
        except:
            self.fileQuality = scene.render.file_quality
            scene.render.file_quality = 100

        if scene.render.engine == "CYCLES":
            try:
                self.debugTileSize = scene.cycles.debug_tile_size #Intruction for Blender until 2.93
                scene.cycles.debug_tile_size = 32
            
            except:
                self.debugTileSize = scene.cycles.tile_size #Intruction for Blender 3x
                scene.cycles.tile_size = 32

            with suppress(Exception):
                self.debugMinSize = scene.cycles.debug_min_size
                scene.cycles.debug_min_size = 32

        tilesize = 16
        renderer = scene.render.engine
        platforms = {"Windows": "Windows", "Darwin": "Mac", "Linux": "Linux"}
        bits = {"32bit": "32", "64bit": "64"}

        settings = scene_settings["region"]

        if is_gpu_render() and not self.mainDialog.m_distributed:
            # renderer += "GPU"
            GPU_SUFFIX = "GPU"
            settings["blenderGPU"] = "1"
            tilesize = 256
        else:
            GPU_SUFFIX = ""

        # get the render engine name from a dict in case different versions
        # have different name conventions for engine names
        supported_renderers = {
            "octane": "Octane",
            "LUXCORE": "LUXCORE",
            "CYCLES": "CYCLES"
        }
        if renderer in list(supported_renderers.keys()):
            if renderer == "octane":
                renderer = supported_renderers[renderer]
                renderer += GPU_SUFFIX
                renderer += bpy.context.scene.octane.octane_blender_version.replace(".", "")

            elif renderer == "LUXCORE":
                renderer = supported_renderers[renderer]
                import addon_utils
                addon = [addon for addon in addon_utils.modules() if addon.bl_info['name'] == "LuxCore"]
                if addon:
                    addon_version = addon[0].bl_info.get('version', (-1,-1,-1))
                    addon_version_txt = "".join(str(item) for item in addon_version)
                    renderer += GPU_SUFFIX
                    renderer += addon_version_txt
                    
                else:
                    print("Unable to find Luxcore render engine addon")
                    pass
            
            elif renderer == "CYCLES":
                renderer += GPU_SUFFIX
        

        settings.update(
            {
                "user": self.mainDialog.m_userName, 
                "units": "0",  # todo
                "program": "BLENDER",
                "version": bpy.app.version_string,
                "renderer": renderer, 
                "startframe": f"{scene.frame_start} ",
                "endframe":f" {scene.frame_end}",
                "resolution": f"{scene.render.resolution_x}x{scene.render.resolution_y}",   
                "OS": platforms[platform.system()],
                "Bits": bits[platform.architecture()[0]],
            }
        )

        with suppress(Exception):
            self.tileSizeX = scene.render.tile_x
            self.tileSizeY = scene.render.tile_y
            scene.render.tile_x = tilesize
            scene.render.tile_y = tilesize
            

        try:
        #    file_format = scene.render.image_settings.file_format
            file_format = ".txt"
        except:
            file_format = scene.render.file_format

        is_vray = scene.render.engine in {"VRAY_RENDER", "VRAY_RENDER_PREVIEW"}
        settings["output"] = "" if is_vray else f"{outputPath}.{file_format}"

        tmpDLPath = generateLocalOutputPath(bpy.path.abspath(self.outputFilepath))
        settings["downloadpath"] = tmpDLPath if len(tmpDLPath) > 2 else ""
        settings["localRend"] = "2"

        self.user_frame_current = bpy.context.scene.frame_current
        bpy.context.scene.frame_current = bpy.context.scene.frame_start

        self.postsaveResetFilepath = self.getFileOutputNodes()

        # find duplicated base paths in file output nodes and make them unique
        # slow O(n^2)
        for node in self.postsaveResetFilepath:
            i = 0
            for other in self.postsaveResetFilepath:
                if node["fpath"] == other["fpath"]:
                    i = i + 1
                if i > 1:
                    self.unique_node_id = self.unique_node_id + 1
                    other["fpath"] = f"{other['fpath']}_{self.unique_node_id}"

        # change compositing node output paths
        for node in self.postsaveResetFilepath:
            if not self.mainDialog.m_distributed:
                node["obj"].base_path = createFarmOutputPath(
                    self.mainDialog.m_userName, node["fpath"]
                )

    def postSave(self) -> None:
        scene = bpy.context.scene
        scene.render.filepath = self.outputFilepath
        scene.render.threads_mode = self.threadsMode
        try:
            scene.render.image_settings.quality = self.fileQuality
        except:
            scene.render.file_quality = self.fileQuality

        if scene.render.engine == "CYCLES":
            try:
                scene.cycles.debug_tile_size = self.debugTileSize #Intruction for Blender until 2.93
            except:
                scene.cycles.tile_size = self.debugTileSize #instruction form Blender 3x

            with suppress(Exception):
                scene.cycles.debug_min_size = self.debugMinSize

        with suppress(Exception):
            scene.render.tile_x = self.tileSizeX
            scene.render.tile_y = self.tileSizeY

        bpy.context.scene.frame_current = self.user_frame_current

        # reset compositing file output nodes base path
        self.unique_node_id = 0
        for node in self.postsaveResetFilepath:
            node["obj"].base_path = node["value"]
