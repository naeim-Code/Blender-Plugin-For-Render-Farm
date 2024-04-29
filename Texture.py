from __future__ import annotations
import bpy
import shutil
import glob
import subprocess
import time
import sys
import os
from contextlib import suppress

from .utilitis import TexPath, readFtpFileContents, checkFilename
from .validator import Validator, TestResult, ResultHelper

from typing import TYPE_CHECKING, Callable, cast

if TYPE_CHECKING:
    from typing import List, Set, Any
    from bpy.types import Operator  # pylint: disable = no-name-in-module, import-error
    from .renderConfiguration import Config

    from .typAliases import ResetFilepath, FileInfo

BLENDER_VERSION = bpy.app.version

class FakePointCache:
    """A fake point cache class that has the same attributes as a blender 
    pointCache object to be used with blender versions where point cache objects
    are depricated in some physics simulation modifiers"""
    def __init__(self):
        self.filepath = ""
        self.name = ""
        self.is_baked = False
        self.use_external = False


class SKY_FixMeTex(bpy.types.Operator):
    bl_idname = "farm.fix_me_tex"
    bl_label = "Perform fixes for texture and point cache properties"

    postsaveResetFilepath: List[ResetFilepath] = []

    def execute(self, context: bpy.types.Context) -> Set[str]:
        dummypath = os.path.join(os.path.dirname(__file__), "dummy.jpg")

        data = bpy.data
        for files in [data.images, data.movieclips, data.fonts, data.sounds]:
            for file_ in files:
                abspath = bpy.path.abspath(file_.filepath, library= file_.library)
                if not os.path.exists(abspath):
                    file_.filepath = dummypath

            self.report({"ERROR"}, "All missing textures have been replaced!")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        wm = context.window_manager
        # return cast(Set[str], wm.invoke_props_dialog(self))
        return wm.invoke_props_dialog(self)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Do you want to replace missing textures with a dummy?")


class Asset():
    def __init__(self, path, pathlocal):
        self.path = path
        self.pathlocal = pathlocal
        self.filesize = os.stat(self.pathlocal).st_size
        self.mod_timestamp = int(os.path.getmtime(self.pathlocal)*1000)

class ValTexture(Validator):

    REPLACE_MISSING_TEXT = 1
    managerPath = ""

    def getPointCaches(self) -> List[FileInfo]:
        files: List[FileInfo] = []
        for o in bpy.data.objects:
            for m in o.modifiers:
                pointCaches = []
                if (
                    hasattr(bpy.types, "SmokeModifier") and isinstance(m, bpy.types.SmokeModifier)
                ) and m.smoke_type == "DOMAIN":
                    pointCaches.append(m.domain_settings.point_cache.point_caches)

                if (
                    hasattr(bpy.types, "FluidModifier")
                    and isinstance(m, bpy.types.FluidModifier)
                    and m.fluid_type == "DOMAIN"
                    and not m.domain_settings.has_cache_baked_mesh
                ):
                    if BLENDER_VERSION <= (2, 90, 0):
                        pointCaches.append(m.domain_settings.point_cache.point_caches)
                    else:
                        # append a fake point cache object because point caches
                        # are depricated from fluid mi=odifier in Blender 2.9+
                        fake_point_cache = FakePointCache()
                        pointCaches.append([fake_point_cache])

                if isinstance(m, bpy.types.ClothModifier):
                    pointCaches.append(m.point_cache.point_caches)

                if isinstance(m, bpy.types.ParticleSystemModifier) and m.particle_system.settings.type in ['HAIR', 'EMITTER']:
                    # the second condition after and  is added to
                    # exclude the cases where particles modifier is part of a fluid silumaltion process
                    # in this case the addon should search for caches in the fluid simulation modifier

                    try:
                        has_cache = m.particle_system.settings.physics_type not in ["NO", "KEYED"]
                    except:
                        has_cache = True

                    if has_cache:
                        pointCaches.append(m.particle_system.point_cache.point_caches)

                if isinstance(m, bpy.types.DynamicPaintModifier) and m.ui_type == "CANVAS":
                    with suppress(AttributeError):
                        # AttributeError: #m.canvas_settings may be None
                        for canv in m.canvas_settings.canvas_surfaces:
                            pointCaches.append(canv.point_cache.point_caches)

                files.extend(
                    {"obj": o, "mod": m, "pc": p, "path": p.filepath, "name": p.name}
                    for pc in pointCaches
                    for p in pc
                )

                if isinstance(m, bpy.types.OceanModifier):
                    files.append(
                        {"obj": o, "mod": m, "pc": "OCEAN", "path": m.filepath, "name": m.name}
                    )

                if hasattr(bpy.types, "FluidSimulationModifier") and isinstance(
                    m, bpy.types.FluidSimulationModifier
                ):
                    if m.settings.type == "DOMAIN" or m.settings.type == "PARTICLE":
                        files.append(
                            {
                                "obj": o,
                                "mod": m,
                                "pc": "FLUID_SIMULATION",
                                "path": m.settings.filepath,
                                "name": m.name,
                            }
                        )

                if hasattr(bpy.types, "FluidModifier") and isinstance(m, bpy.types.FluidModifier):
                    if m.fluid_type == "DOMAIN":
                        files.append(
                            {
                                "obj": o,
                                "mod": m,
                                "pc": "MantaFlow",
                                "path": m.domain_settings.cache_directory,
                                "name": m.name,
                            }
                        )

                if isinstance(m, bpy.types.MeshCacheModifier):
                    files.append(
                        {
                            "obj": o,
                            "mod": m,
                            "pc": "MESH_CACHE",
                            "path": m.filepath,
                            "name": m.name,
                        }
                    )

        for volume in bpy.data.volumes:
            vol_fake_pc = FakePointCache()
            files.append(
                {
                    "obj": volume,
                    "mod": volume,
                    "pc": "VOLUME",
                    "path": os.path.dirname(bpy.path.abspath(volume.filepath)),
                    "name": volume.name
                }
            )

        return files

    def getName(self) -> str:
        return "Texture"

    def test(self, results_: List[TestResult]) -> None:
        results = ResultHelper(results_, self)
        texpath = os.path.join(self.mainDialog.m_defaultPath, self.mainDialog.m_userName, "tex")
        
        def is_file(file_: Any) -> bool:
            if hasattr(file_, "source"):
                if file_.source == 'TILED':
                    return True
                return cast(bool, file_.source == "FILE")
            return cast(bool, file_.filepath != "<builtin>")

        data = bpy.data
        temp_files = [
            file_
            for files in [data.images, data.movieclips, data.fonts, data.sounds]
            for file_ in filter(is_file, files)
        ]

        shadowPath=os.path.join(self.mainDialog.m_defaultPath,"shadows.txt") 
        if self.mainDialog.m_defaultPath != "" and os.path.exists(shadowPath)==False:           
            is_connected = True
            try:
                subprocess.Popen(f'"{self.mainDialog.m_managerPath}"', shell=False) 
            except:
                print(f"texture: {sys.exc_info()}")              
        else: 
            results.info(f'Farm Desk Is Running')

        for file_ in temp_files:
            # udims special treatment
            if file_.source == 'TILED':
                base_path = file_.filepath.split('.')[0]
                ext = file_.filepath.split('.')[-1]

                for tile in file_.tiles:
                    udim_path = f"{base_path}.{tile.number}.{ext}"
                    udim_path_abs = bpy.path.abspath(udim_path)

                    if not os.path.exists(udim_path_abs):
                        results.error(
                            f"File not found: {udim_path_abs} (texture: {file_.name} )", type_= self.REPLACE_MISSING_TEXT,
                            info_1= file_.name
                        )

            f = file_.filepath
            fRealPath = bpy.path.abspath(file_.filepath, library= file_.library)
            texFilePath = os.path.join(texpath, os.path.basename(fRealPath))

            if os.path.splitext(fRealPath)[1].lower() == ".py":
                pass
            elif not os.path.exists(fRealPath):
                results.error(
                    f"File not found: {f} (texture: {file_.name} )", type_= self.REPLACE_MISSING_TEXT,
                    info_1= file_.name
                )
            elif not os.path.isfile(fRealPath):
                results.error(f"Invalid file name for texture: {file_.name} (file name: {f} )")
            elif not checkFilename(os.path.basename(fRealPath)):
                results.error(f"Filename has unsupported characters: {f}")
            elif os.path.exists(texFilePath):
                if os.path.getsize(texFilePath) != os.path.getsize(fRealPath):
                    results.error(
                        f'Texture "{os.path.basename(f)}" {fRealPath} exported and used by other project. Please rename this texture. {f} (texture: {file_.name} )'
                    )
            else:
                if os.path.basename(f).lower() in ftpContentsFiles:
                    pos = ftpContentsFiles.index(os.path.basename(f).lower())
                    if pos >= 0:
                        if os.path.getsize(f) != ftpContentsSizes[pos]:
                            results.error(
                                f'Texture "{os.path.basename(f)}" exported and used by other project. Please rename this texture'
                            )

            if f.endswith(".psd"):
                results.error(f"Filetype (psd) not supported: {f}")

        for f in self.getPointCaches():
            print(f["mod"].name)
            folder = bpy.path.abspath(f["path"])
            file_ = f["name"]
            # fobj= f['obj']
            fmod = f["mod"]
            fpc = f["pc"]
            blender_scene_path = bpy.context.blend_data.filepath
            cache_folder = os.path.join(os.path.dirname(blender_scene_path), folder.strip("/"))
            obj_notice = f"object: \"{f['obj'].name}\" modifier: \"{f['mod'].name}\""

            if fpc == "OCEAN":
                if not fmod.is_cached:
                    results.error(f"Ocean Modifier: Was not baked. {obj_notice}", type_= 3, info_1= f['obj'].name, info_2= f['mod'].name)

            elif fpc == "MESH_CACHE":
                if not os.path.exists(folder):
                    results.error(f"MeshCache: File not found. {folder} {obj_notice}", type_= 4, info_1= f['obj'].name, info_2= f['mod'].name)

            elif fpc == "FLUID_SIMULATION":
                if not os.path.exists(folder) or len(glob.glob(os.path.join(folder, "*"))) < 1:
                    results.error(f"Fluid Modifier: Was not baked. {obj_notice}", type_= 5, info_1= f['obj'].name, info_2= f['mod'].name)

            elif fpc == "MantaFlow":
                # if no cache dir or no files in cache dir
                if not os.path.exists(cache_folder) or all(
                    len(filenames) == 0 for _dirpath, _dirnames, filenames in os.walk(cache_folder)
                ):
                    results.error(f"Fluid Modifier: Was not baked. {obj_notice}", type_= 10, info_1= f['obj'].name)

            elif fpc == "VOLUME":
                # do nothing
                # print("It's a volume")
                pass

            elif not fpc.is_baked and not fpc.use_external:
                if not hasattr(fmod, "particle_system"):
                    if fmod.name == "Cloth":
                        results.error(
                            f"Cloth Modifier: Cloth Cache Was never baked. Bake or use external files. {obj_notice}", type_= 6, info_1= f['obj'].name, info_2= f['mod'].name
                        )
                    elif fmod.type == 'FLUID' and not fmod.domain_settings.has_cache_baked_mesh:
                        results.error(message= f"Fluid Simulation was not baked. {obj_notice}", type_= 10, info_1= f['obj'].name)
                    else:
                        results.error(
                            f"Modifier: Point Cache Was never baked. Bake or use external files. {obj_notice}"
                        )
                elif fmod.particle_system.settings.type == "HAIR":
                    if fmod.particle_system.use_hair_dynamics == True:
                        results.error(
                            f"Hair dynamics: PointCache Was not baked. Bake or use external. {obj_notice}",
                            type_= 14, info_1= f['obj'].name
                        )
                else:
                    results.error(f"PointCache: Was not baked. Bake or use external. {obj_notice}", type_= 8, info_1= f['obj'].name)
            else:
                if not fpc.use_disk_cache and not fpc.use_external:
                    ob = bpy.data.objects.get(f['obj'].name)
                    mod = ob.modifiers.get(f['mod'].name)

                    # these conditions are to avoid raising errors for baked already caches
                    if mod.type == 'CLOTH':
                        error_type = 6
                    elif mod.type == 'FLUID':
                        error_type = 10
                    else:
                        # particles modifier
                        error_type = 8

                    results.error(
                        f"PointCache: Disk Cache not activated, activate Disk Cache or use external. {obj_notice}", type_= error_type,
                        info_1= f['obj'].name, info_2= f['mod'].name
                    )

                if fpc.use_external:
                    if folder == "":
                        results.error(f"PointCache: External path empty. {obj_notice}")
                    elif not os.path.exists(folder):
                        results.error(f"PointCache: Folder not found. {folder} {obj_notice}")
                elif fpc.is_outdated:
                    results.error(
                        f"PointCache: Cache outdated. Free bake and rebake. {obj_notice}"
                    )

                if file_ == "":
                    results.error(
                        f"Please enter a name for the Point Cache of \"{f['mod'].name}\", object \"{f['obj'].name}\"."
                    )

                if not fpc.use_external and fpc.use_disk_cache:
                    dir = os.path.dirname(bpy.context.blend_data.filepath)
                    fn = os.path.splitext(os.path.basename(bpy.context.blend_data.filepath))[0]
                    cacheFolder = os.path.join(dir, f"blendcache_{fn}")
                    if not os.path.exists(cacheFolder):
                        results.error(f"PointCache: implicit folder not found. {cacheFolder}")

    def furtherAction(self, op: Operator, result: TestResult) -> None:
        if result.type == self.REPLACE_MISSING_TEXT:
            bpy.ops.farm.fix_me_tex("INVOKE_DEFAULT")
        op.report(type= {'ERROR'}, message= result.message)

    def prepareSave(self, export_folder: str, assets: List[str], scene_settings: "Config") -> None:
        texpath = os.path.join(export_folder, "tex")
        os.makedirs(texpath, exist_ok=True)

        self.postsaveResetFilepath: List[ResetFilepath] = []
        serverpath = TexPath(self.mainDialog.m_userName)

        self.save_point_caches(export_folder, texpath, serverpath, assets)
        self.save_regular_assets(texpath, serverpath, assets)

    def postSave(self) -> None:
        for stuff in self.postsaveResetFilepath:
            # mantaflow uses .cache_directory, all others use .filepath
            if hasattr(stuff["o"], "filepath"):
                stuff["o"].filepath = stuff["value"]
            else:
                stuff["o"].cache_directory = stuff["value"]

    def add_asset(
        self,
        assets: List[str],
        serverpath: str,
        texpath: str,
        file_: Any,
        take_absolute_path: bool = False,
        is_preupload: bool = False
    ) -> None:
        oriPath: str = file_.filepath
        filename = os.path.basename(oriPath)
        outFile = os.path.join(texpath, filename)
        fRealPath = bpy.path.abspath(oriPath) if take_absolute_path else oriPath

        if os.path.isfile(fRealPath):
            vFile = f"tex/{filename}"
            asset = Asset(vFile, fRealPath)

            if asset.path not in [a.path for a in assets if hasattr(a, 'path')]:
            # if vFile not in assets:
                assets.append(asset)
                # shutil.copy(fRealPath, outFile)

            if not is_preupload:
                file_.filepath = os.path.join(serverpath, filename)
                self.postsaveResetFilepath.append({"o": file_, "value": oriPath})

    def save_point_caches(
        self, export_folder: str, texpath: str, serverpath: str, assets: List[str],
        is_preupload: bool = False
    ) -> None:
        def add_pointcache_assets(
            folder: str, f: Any, save_asset: Callable[[Any], None], subfolder: str = ""
        ) -> None:

            if not os.path.exists(folder):
                return

            if subfolder != "":
                os.makedirs(os.path.join(texpath, subfolder), exist_ok=True)

            valid_file = lambda entry: not entry.name.startswith(".") and entry.is_file()

            for entry in filter(valid_file, os.scandir(folder)):
                filename = entry.name
                # if subfolder is empty, it is ignored in path.join()
                outFile = os.path.join(texpath, subfolder, filename)
                vFile = os.path.join("tex", subfolder, filename).replace("\\", "/")
                asset = Asset(vFile, entry.path)
                if asset.path not in [a.path for a in assets if hasattr(a, 'path')]:
                # if vFile not in assets:
                    assets.append(asset)
                    # shutil.copy(entry.path, outFile)

            save_asset(f)

        for icp, f in enumerate(self.getPointCaches()):
            # obj = f['obj']
            folder = f["path"]
            fpc = f["pc"]
            if fpc == "OCEAN":
                uniqueCachePath = f"cache_{icp}"

                def save_asset(f: Any) -> None:
                    self.postsaveResetFilepath.append({"o": f["mod"], "value": f["mod"].filepath})
                    f["mod"].filepath = f"{serverpath}\\{uniqueCachePath}\\"

                add_pointcache_assets(folder, f, save_asset, uniqueCachePath)

            elif fpc == "MESH_CACHE":
                self.add_asset(assets, serverpath, texpath, f["mod"], take_absolute_path=True)

            elif fpc == "FLUID_SIMULATION":

                def save_asset(f: Any) -> None:
                    self.postsaveResetFilepath.append(
                        {"o": f["mod"].settings, "value": f["mod"].settings.filepath}
                    )
                    f["mod"].settings.filepath = serverpath

                add_pointcache_assets(folder, f, save_asset)

            elif fpc == "MantaFlow":

                base_subfolder = os.path.basename(
                    os.path.dirname(f["mod"].domain_settings.cache_directory)
                )

                def save_asset(f: Any) -> None:
                    self.postsaveResetFilepath.append(
                        {
                            "o": f["mod"].domain_settings,
                            "value": f["mod"].domain_settings.cache_directory,
                        }
                    )
                    f["mod"].domain_settings.cache_directory = f"{serverpath}\\{base_subfolder}\\"

                valid_dir = lambda entry: not entry.name.startswith(".") and entry.is_dir()
                for cache_dir in filter(
                    valid_dir, os.scandir(f["mod"].domain_settings.cache_directory)
                ):
                    cache_dir = cache_dir.name
                    subfolder = os.path.join(base_subfolder, cache_dir)
                    cache_folder = os.path.join(folder, cache_dir)
                    add_pointcache_assets(cache_folder, f, save_asset, subfolder)
            
            elif fpc == "VOLUME":

                def save_asset(f: Any) -> None:
                    self.postsaveResetFilepath.append(
                        {"o": f["mod"], "value": f["path"]}
                    )
                    f["mod"].filepath = serverpath + "\\" + os.path.basename(bpy.path.abspath(f["mod"].filepath))

                add_pointcache_assets(folder, f, save_asset)

            elif fpc.use_external:

                def save_asset(f: Any) -> None:
                    self.postsaveResetFilepath.append({"o": f["pc"], "value": f["pc"].filepath})
                    f["pc"].filepath = serverpath

                add_pointcache_assets(folder, f, save_asset)

            else:
                filename = f["name"]
                dir_ = os.path.dirname(bpy.context.blend_data.filepath)
                fn = os.path.splitext(os.path.basename(bpy.context.blend_data.filepath))[0]
                cachFolderName = f"blendcache_{fn}"
                cacheFolder = os.path.join(dir_, cachFolderName)
                cacheFolderDest = os.path.join(export_folder, cachFolderName)
                if os.path.exists(cacheFolder):
                    os.makedirs(cacheFolderDest, exist_ok=True)

                    for ff in glob.glob(os.path.join(cacheFolder, f"{filename}*")):
                        if not os.path.isdir(ff):
                            filename = os.path.basename(ff)
                            outFile = os.path.join(cacheFolderDest, filename)
                            vFile = f"{cachFolderName}/{filename}"
                            asset = Asset(vFile, ff)
                            # shutil.copy(ff, outFile)
                            assets.append(asset)

    def save_regular_assets(self, texpath: str, serverpath: str, assets: List[str], is_preupload: bool = False) -> None:
        def add_asset(file_: Any, take_absolute_path: bool = False) -> None:
            self.add_asset(assets, serverpath, texpath, file_, take_absolute_path, is_preupload)

        # save images
        for file_ in bpy.data.images:
            # handle UDIM textures
            if file_.source == 'TILED':
                
                base_path = file_.filepath.split('.')[0]
                ext = file_.filepath.split('.')[-1]

                for tile in file_.tiles:
                    udim_path = f"{base_path}.{tile.number}.{ext}"
                    udim_path_abs = bpy.path.abspath(udim_path)
                    file_name = os.path.split(udim_path_abs)[-1]
                    vFile = f"tex/{file_name}"

                    if os.path.isfile(udim_path_abs):
                        asset = Asset(vFile, udim_path_abs)

                        if asset.path not in [a.path for a in assets if hasattr(a, 'path')]:
                            assets.append(asset)

            fRealPath = bpy.path.abspath(file_.filepath)
            dir_, filename = os.path.split(fRealPath)
            add_asset(file_, take_absolute_path=True)

            # handle image sequences
            with suppress(Exception):
                if file_.source == "SEQUENCE":
                    filename, ext = os.path.splitext(filename)
                    unnumbered_filename = filename.rstrip("0123456789")
                    sFiles = glob.glob(f"{dir_}/{unnumbered_filename}*{ext}")

                    for sFile in sFiles:
                        sOriPath = sFile
                        sFilename = os.path.basename(sOriPath)
                        sOutFile = os.path.join(texpath, sFilename)

                        vFile = f"tex/{sFilename}"
                        asset = Asset(vFile, sOriPath)
                        if asset.path not in [a.path for a in assets if hasattr(a, 'path')]:
                        # if vFile not in assets:
                            assets.append(asset)
                            # shutil.copy(sOriPath, sOutFile)

        data = bpy.data
        for files in [data.movieclips, data.fonts, data.sounds, data.cache_files]:
            for file_ in files:
                add_asset(file_)

    #        #safe external blend files
    #        for file_ in bpy.data.libraries:
    #            oriPath    = file_.filepath
    #            filename= os.path.basename(oriPath)
    #            outFile = os.path.join(texpath, filename)
    #
    #            if os.path.exists(oriPath):
    #                assets.append(f"tex/{filename}")
    #                shutil.copy(oriPath, outFile)
    #                file_.filepath= os.path.join(serverpath, filename)
    #                self.postsaveResetFilepath.append({"o":file_, "value":oriPath})
