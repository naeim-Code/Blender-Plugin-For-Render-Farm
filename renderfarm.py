 
if "bpy" in locals():
    import imp    
    imp.reload(utilitis)
    imp.reload(general)
    imp.reload(rendersettings)
    imp.reload(Texture) 
else:
    import bpy
    import platform
    import subprocess
    import os  
    from contextlib import suppress
    from bpy.props import (   
        BoolProperty,
        EnumProperty,
        PointerProperty,
        StringProperty,
    )

    try:
        from . import utilitis, general, rendersettings
        from .utilitis import (
            calcMd5,
            is_gpu_render,
            getChangedBlenderFilename,
            manager_version,
            getConfigFileContent,
            generatePreview,
            unique_filename,
            TexPath,
            createFarmOutputPath,
            farmProps,
            bake_scripted_drivers
        )
        from .validator import Validator, TestResult, ResultHelper
        from .general import ValGeneral
        from .rendersettings import ValRendersettings
        from .Texture import ValTexture
        from .Vray import ValVray
        from .renderConfiguration import Config
    except:
        print("Farminizer plugin not installed correctly")

from typing import List, Dict, Set, Any, cast

from . import Texture, Vray
from .fixIt import operators_list
import webbrowser
 
preview_collections = {}

class FarmRenderDlg:
    results: List[TestResult] = []
    m_userName = ""
    m_defaultPath = ""
    m_managerPath = ""
    m_pluginVersion = ""
    m_CpuData = ""
    m_distributed = False
    m_distributedConfirmed = False

    def __init__(self) -> None:
        self.tests = [ValGeneral(self), ValRendersettings(self), ValTexture(self), ValVray(self)]
        print("Farm Dialog Running")

        conf = getConfigFileContent()
        if len(conf) >= 4:
            self.manager_file_exists = True
            self.m_userName = conf[0]
            self.m_defaultPath = conf[1]
            self.m_managerPath = conf[2]
            self.m_pluginVersion = conf[3]
            if len(conf) >= 5:
                self.m_CpuData = conf[4]

            self.getStatusInfo()
        else:
            self.manager_file_exists = False
            self.status_file_exists = False

    def isAllValid(self) -> bool:
        not_empty = len(self.results) > 0
        return not_empty and all(res.severity != 2 for res in self.results)

    def displayResults(self, sev_filter: int, layout: Any) -> None:
        sev = 0
        sev_icon = ["INFO", "ERROR", "CANCEL", "NONE", "NONE", "NONE", "NONE", "NONE"]
        grp = ""
        pre_grp = ""
        # hint = ""
        has_content = False

        for i, vr in enumerate(self.results):
            sev = vr.severity
            if sev == sev_filter or sev_filter == 0:
                if vr.validator is not None:
                    grp = vr.validator.getName()
                    if grp != pre_grp:
                        if i > 0:
                            layout.separator()
                        layout.label(text=grp)
                        pre_grp = grp

                if vr.flagMoreInfos:
                    row = layout.row(align=True)
                    col = row.column()
                    col.alignment = "EXPAND"
                    col.label(text=vr.message, icon=sev_icon[sev])
                    col = row.column()
                    col.alignment = "RIGHT"
                    if vr.type:
                        # change the button label for specific error types
                        op = col.operator("farm.further_action", text= "Fix Me")
                    else:
                        op = col.operator("farm.further_action")
                    op.op_id = i
                else:
                    layout.label(text=vr.message, icon=sev_icon[sev])

                has_content = True

        if not has_content and len(self.results) > 0:
            if sev_filter == 2:
                layout.label(text="No Errors")
            if sev_filter == 1:
                layout.label(text="No Warnings")

    def actionStart(self, fastCheck: bool) -> bool:
        self.results = []
        results = ResultHelper(self.results, None)
        conf = getConfigFileContent()
        if len(conf) >= 4:
            self.m_userName = conf[0]
            self.m_defaultPath = conf[1]
            self.m_managerPath = conf[2]
            self.m_pluginVersion = conf[3]
            if len(conf) >= 5:
                self.m_CpuData = conf[4]
        else:
            results.error(
                "clientsettings.cfg could not be found, please reinstall plugin from Fatm Drop!"
            )

        if len(self.m_userName) == 0:
            results.error("You are not logged in correcly, please login from Farm Drop first!")

   
        if fastCheck:
            results.info("No textures have been checked. To finally export click 'Upload to Farm'")

        if self.m_distributed:
            results.info("Doing a distributed rendering")

        for v in self.tests:
            if fastCheck == False or v.getName() != "Texture":
                v.test(self.results)

        if len(self.results) == 0:
            results.info("No errors or warnings found")

        return self.isAllValid() and not fastCheck

    def actionExport(self, op: bpy.types.Operator) -> None:
        results = ResultHelper(self.results, None)
        with suppress(Exception):
            bpy.ops.file.unpack_all()

        self.actionStart(False)
        valid = self.isAllValid()

        if not valid:
            op.report(
                {"WARNING"},
                "This project could not be exported, please check the displayed errors.",
            )
            return

        export_folder = os.path.join(self.m_defaultPath, self.m_userName)
        results.error(export_folder)
         
        with suppress(FileExistsError):
            os.mkdir(export_folder)

        
        self.doExportFolder(export_folder)
        results.info("Project has been successfully exported !") 
        bpy.ops.farm.project_export_success("INVOKE_DEFAULT")

    def doExportFolder(self, export_folder: str) -> None:
        assets = []  # type: List[str]

        mangled_basename, _ext = os.path.splitext(os.path.basename(getChangedBlenderFilename()))
        blenderpath = unique_filename(export_folder, mangled_basename, ".blend")

        generatePreview(f"{blenderpath}.jpg")

        try:
            bpy.ops.object.make_local(type="ALL")
        except:
            with suppress(Exception):
                bpy.ops.object.editmode_toggle()
                bpy.ops.object.make_local(type="ALL")

        bpy.ops.file.make_paths_absolute()

        scene_settings = Config()
        scene_settings.add_section("region")

        for v in self.tests:
            v.prepareSave(export_folder, assets, scene_settings)

        if self.m_distributed and bpy.context.scene.frame_start == bpy.context.scene.frame_end:
            scene_settings["region"]["singleframeBlenderIntern"] = "1"

        props = farmProps()

        if props.is_auto_start:
            scene_settings["region"]["autostart"] = "1"

        if props.priority != "1":
            scene_settings["region"]["prio"] = props.priority

        if props.is_send_email and props.is_by_finish:
            scene_settings["region"]["notifyComplete"] = "1"

        if not props.is_send_email:
            scene_settings["region"]["notifyCompletedit"] = "True"
             
        if props.is_send_email and props.is_by_start:
            scene_settings["region"]["notifyStart"] = "1"

        if props.is_cost_estimation:
            scene_settings["region"]["estimationFrames"] = "3"
            scene_settings["region"]["autostart"] = "1"

        # batch scenes render
        if props.batch_render:
            upload_scenes = [scene for scene in bpy.data.scenes if scene.upload_scene]
            print (*upload_scenes)
            scene_settings.add_section("SeparateJobs")
            for i, scene in enumerate(upload_scenes):
                scene_settings["SeparateJobs"][f"section{i}"] = scene.name

            for scene in upload_scenes:
                scene_settings.add_section(f"{scene.name}")
                scene_settings[f"{scene.name}"]["resolution"] = f"{scene.render.resolution_x}x{scene.render.resolution_y}"
                scene_settings[f"{scene.name}"]["frames"] = f"{scene.frame_start} {scene.frame_end} 1"
                scene_settings[f"{scene.name}"]["rangestep"] = "1"

                render_path = bpy.path.abspath(scene.render.filepath)
                outputPath = createFarmOutputPath(bpy.farmRender.m_userName, render_path)
                file_format = bpy.context.scene.render.image_settings.file_format
                scene_settings[f"{scene.name}"]["output"] = f"{outputPath}.{file_format}"
                scene_settings[f"{scene.name}"]["camera"] = f"scene.camera.name"
                scene_settings[f"{scene.name}"]["take"] = f"scene.name"
            

        bpy.ops.wm.save_as_mainfile(
            filepath=blenderpath, compress=True, copy=True, relative_remap=False
        )

        files_section: "Dict[str, str]" = {}
        for i, f in enumerate(assets):
            files_section[f"path{i}"] = f.path
            files_section[f"pathlocal{i}"] = f.pathlocal
            size = 0
            try:
                size = os.stat(os.path.join(export_folder, f.pathlocal)).st_size
            except:
                print(f"file not found {os.path.join(export_folder, f.pathlocal)}")
            files_section[f"pathsize{i}"] = str(size)

        files_section["paths"] = str(len(assets))
        scene_settings["files"] = files_section

        scene_settings["checksum"] = {
            "check": str(calcMd5(blenderpath)),  # todo
            "scenesize": str(os.stat(blenderpath).st_size),
        }

        scene_settings.write_to_file(f"{blenderpath}.txt")

        for v in self.tests:
            v.postSave()
 
       # with suppress(Exception):
        #    subprocess.Popen(f'"{self.m_managerPath}"', shell=False)

    def actionSaveLogAllowed(self) -> bool:
        return len(self.results) != 0

    def actionSaveLog(self, name: str) -> None:
        if not name:
            return

        file_ = open(name, "w", encoding="utf-8")
        if file_:
            fileTxt = ""

            # sysbit = "32Bit" # TODO
            # if cmds.about(is64=True):
            #    sysbit = "64Bit"

            fileTxt += "Logfile written by Farm Farminizer Blender Plugin\r\n"
            fileTxt += "\r\n"

            fileTxt += "Environment:\r\n"
            fileTxt += "------------------------------ \r\n"

            fileTxt += f"Client Document: {getChangedBlenderFilename()}\r\n"
            fileTxt += f"Client Original Path: {bpy.context.blend_data.filepath}\r\n"
            fileTxt += f"Scripts Path: {__file__}\r\n"
            fileTxt += f"Client Blender Ver.: {bpy.app.version_string}\r\n"
            fileTxt += f"Client OS: {platform.system()}\r\n"
            fileTxt += "\r\n\r\n"

            fileTxt += "Farminizer Plugin output:\r\n"
            fileTxt += "------------------------------ \r\n\r\n"
            sev_text = ["Info", "Warning", "Error", "", "", "", "", ""]
            grp = ""
            pre_grp = ""

            for i in self.results:
                if i.validator is not None:
                    grp = i.validator.getName()
                    if grp != pre_grp:
                        fileTxt += f"\r\n{grp}:\r\n\r\n"
                        pre_grp = grp
                fileTxt += f" --- {sev_text[i.severity]} --- {i.message}\r\n"

            file_.write(fileTxt)

    def actionCalculateCosts(self) -> str:
        scene = bpy.context.scene
        startframe = int(scene.frame_start)
        endframe = int(scene.frame_end)
        numFrames = endframe - startframe + 1
        timePerFrame = 0

        renderer = scene.render.engine

        if is_gpu_render():
            renderer += "GPU"
        results = ResultHelper(self.results, None)
         
        results.info(url) 
        return url

    def createFarmDropLinkFile(self, file_name, content="") :
        link_file = open(os.path.normpath(os.path.join(self.m_defaultPath, file_name)), 'w')
        if content != "" :
            link_file.write(content + "\n")
        link_file.close()

    def actionAbout(self) -> None:
        print("about")

    def getStatusInfo(self) -> None:
        # Read info from at2_reb_status_info.txt
        status_info_file = "at2_reb_status_info.txt"
        export_folder = os.path.join(self.m_defaultPath, self.m_userName)

        try:
            with open (os.path.join(export_folder, status_info_file), 'r') as info_file:
                info = info_file.readlines()

            self.status_file_exists = True
            self.rp = info[0].split(':')[1].rstrip()
            self.jobsReadyCount = info[1].split(':')[1].rstrip()
            self.jobsQueuedCount = info[2].split(':')[1].rstrip()
            self.jobsRunningCount = info[3].split(':')[1].rstrip()
            self.jobsPausedCount = info[4].split(':')[1].rstrip()
        except:
            self.status_file_exists = False
        
bpy.farmRender = FarmRenderDlg()

class RENDER_PT_farm_panel_view3d(bpy.types.Panel):
    """Farm main view_3d panel"""
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category= "Farm"
    bl_label = "Farm"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

class RENDER_PT_farm_panel_prop(bpy.types.Panel):
    """Farm main properties render section panel"""
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_context = "render" 
    bl_label = "Farm"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout

class RENDER_PT_farm_account_gen(): 

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"

        # row = layout.row()
        
        # row.template_preview(banner_texture)
        
        row = layout.row()
        sub = row.row(align= False)
        sub.label(text=f"User: {bpy.farmRender.m_userName}")
 
        row = layout.row()
        sub = row.row(align= False)  
        if not bpy.farmRender.manager_file_exists:
            sub.enabled = False 

class RENDER_PT_farm_account(RENDER_PT_farm_account_gen, bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category= "Farm" 
    bl_label = "Account"
    bl_parent_id = "RENDER_PT_farm_panel_view3d" 
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_farm_account_prop(RENDER_PT_farm_account_gen, bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW' 
    bl_label = "Account"
    bl_parent_id = "RENDER_PT_farm_panel_prop"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_farm_settings_gen(): 

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"
        props = farmProps()
        
        # layout.prop(bpy.context.object, "rotation_mode", text="Priority")
        layout.prop(props, "priority")

        row = layout.row()
        split = row.split(factor= 0.22)
        col = split.column()
        col = split.column()
         
        
        
        row = layout.row()
        split = row.split(factor= 0.22)
        col = split.column()
        col = split.column()
        
        
        # col.label(text= "Estimated wait time 4 minutes")
        col.prop(props, "is_auto_start")
        row = col.row()
        if bpy.context.scene.frame_end - bpy.context.scene.frame_start >= 1 or not bpy.context.scene.cycles.device == 'CPU':
            row.enabled = False
        row.prop(props, "is_distributed")
        
        row = layout.row()
        row.scale_y = 5
        
        
        row = layout.row()
        row.scale_y = 2.5 
        split = row.split()
        col = split.column()
        col.operator("farm.costcalculator")

class RENDER_PT_farm_settings(RENDER_PT_farm_settings_gen, bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category= "Farm"
    bl_label = "Settings"
    bl_parent_id = "RENDER_PT_farm_panel_view3d"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_farm_settings_prop(RENDER_PT_farm_settings_gen, bpy.types.Panel):
    bl_space_type = 'PROPERTIES'
    bl_region_type = 'WINDOW'
    bl_category= "Farm"
    bl_label = "Settings"
    bl_parent_id = "RENDER_PT_farm_panel_prop"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_batch_render_gen(): 
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"

        props = farmProps()

        row = layout.row()
        split = row.split(factor= 0.22)
        col = split.column()
        col = split.column()

        row = col.row()
        row.prop(props, "batch_render")
        row.enabled = False
        
        row = col.row()
        row.scale_y = 2
        row.operator("farm.setup_scenes_render")
        row.enabled = False
 
 
class RENDER_PT_cost_estimation_gen(): 

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"

        row = layout.row()
        split = row.split(factor= 0.22)

        col = split.column()
        try:
            #loading the icons and adding them to the panel
            pcoll = preview_collections["main"]
            icon_scale = 2
            my_icon = pcoll["calc_icon"]
            col.template_icon(icon_value= my_icon.icon_id, scale= icon_scale)

            my_icon = pcoll["calc_icon_cloud"]
            col.template_icon(icon_value= my_icon.icon_id, scale= icon_scale)
        except:
            print("Error loading icons")

        col = split.column()
        col.scale_y = 2  
        if not bpy.farmRender.manager_file_exists:
            col.enabled = False

 

 

class RENDER_PT_notifications_gen():
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"

        props = farmProps()

        # row = layout.row()
        # sub = row.row(align= False)
        row = layout.row()
        # row.prop(props, "is_send_email")
        sub = row.row()
        # if props.is_send_email == False:
        #     sub.enabled = False
        sub.label(text= "Send e-mail?")
        sub.prop(props, "is_by_start")
        sub.prop(props, "is_by_finish")

        row = layout.row()
        row.scale_y = 5

        row = layout.row()
        row.scale_y = 2.5
        split = row.split()
        col = split.column()
        col.operator("farm.check", text= "QuickCheck")

        col = split.column()
        col.operator("farm.send", text= "Upload to Farm")
        if not bpy.farmRender.manager_file_exists:
            col.enabled = False

class RENDER_PT_notifications(RENDER_PT_notifications_gen, bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category= "Farm"
    bl_label = "Notifications"
    bl_parent_id = "RENDER_PT_farm_panel_view3d"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_notifications_prop(RENDER_PT_notifications_gen, bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_category= "Farm"
    bl_label = "Notifications"
    bl_parent_id = "RENDER_PT_farm_panel_prop"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_farm_check_results_gen():  
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        # rd = context.scene.render
        # return (rd.use_game_engine==False) and (rd.engine in cls.COMPAT_ENGINES)
        return True
    
    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.operator_context = "INVOKE_DEFAULT"

        props = farmProps()

        row = layout.row(align=True)
        row.prop_enum(props, "result_filter", "0")
        row.prop_enum(props, "result_filter", "2")
        row.prop_enum(props, "result_filter", "1")

        col = layout.column()
        col.alignment = "RIGHT"

        # results = [r.message for r in bpy.farmRender.results if "Scripted Expressions" in r.message]

        # if results:
        #     # display the button only when scripted expressions are introduced
        #     col.operator("farm.bake_expressions")

        bpy.farmRender.displayResults(int(props.result_filter), col)
        
        # if results:
        #     # display the button only when scripted expressions are introduced
        #     col.operator("farm.bake_expressions")


class RENDER_PT_farm_check_results(RENDER_PT_farm_check_results_gen, bpy.types.Panel):
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category= "Farm"
    bl_label = "SmartCheck Results"
    bl_parent_id = "RENDER_PT_farm_panel_view3d"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class RENDER_PT_farm_check_results_prop(RENDER_PT_farm_check_results_gen, bpy.types.Panel):
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_category= "Farm"
    bl_label = "SmartCheck Results"
    bl_parent_id = "RENDER_PT_farm_panel_prop"
    COMPAT_ENGINES = set(["BLENDER_RENDER"])

class CheckOperator:
    distributed: bpy.props.BoolProperty(name="Render distributed")  # type: ignore

    def askDistributed(self, context: bpy.types.Context) -> bool:
        pass

    def executeAction(self) -> None:
        pass

    def execute(self, context: bpy.types.Context) -> Set[str]:
        if (
            bpy.context.scene.frame_start == bpy.context.scene.frame_end
            and not bpy.farmRender.m_distributedConfirmed
        ):
            bpy.farmRender.m_distributedConfirmed = True
            bpy.farmRender.m_distributed = self.distributed
        self.executeAction()
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        if (
            self.askDistributed(context)
            and bpy.context.scene.frame_start == bpy.context.scene.frame_end
        ):
            self.distributed = bpy.farmRender.m_distributed
            bpy.farmRender.m_distributedConfirmed = False
            context.window_manager.invoke_props_dialog(self, width=800)
            return {"RUNNING_MODAL"}
        else:
            return self.execute(context)

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout  # type: ignore # pylint: disable=no-member # the children classes have this member
        layout.label(text="You are rendering one frame only.")
        layout.label(
            text="This frame can either be rendered in distributed mode or on one PC only."
        )
        layout.label(
            text="Distributed rendering will render fast but costs more. We recommend this mode for rendertimes higher than 5hour on you PC!"
        )
        layout.label(
            text="Without distributed rendering your frame will use one PC only - it will render slow but very cheap. We recommend this mode for previews or quick renderings."
        )
        layout.separator()
        layout.label(text="Do you want to render distributed?")
        layout.prop(self, "distributed")


class Farm_OT_Check(bpy.types.Operator, CheckOperator):
    bl_idname = "farm.check"
    bl_label = "Smartcheck"

    def executeAction(self) -> None:
        bpy.farmRender.getStatusInfo()
        bpy.farmRender.actionStart(True)

    def askDistributed(self, context: bpy.types.Context) -> bool:
        return not bpy.farmRender.m_distributedConfirmed


class Farm_OT_Send(bpy.types.Operator, CheckOperator):
    bl_idname = "farm.send"
    bl_label = "Upload"

    def executeAction(self) -> None:
        bpy.farmRender.actionExport(self)

    def askDistributed(self, context: bpy.types.Context) -> bool:
        return True

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        if not "FINISHED" in bpy.ops.farm.check_frames("INVOKE_DEFAULT"):
            return {"CANCELLED"}

        props = farmProps()
        bpy.farmRender.m_distributedConfirmed = props.is_distributed
        bpy.farmRender.m_distributed = props.is_distributed
        # return CheckOperator.invoke(self, context, event)
        return self.execute(context)


class Farm_OT_CostCalculator(bpy.types.Operator):
    bl_idname = "farm.costcalculator"
    bl_label = "CostCalculator"
    
    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return True

    def execute(self, context: bpy.types.Context) -> Set[str]:
        bpy.farmRender.createFarmDropLinkFile("opencalculator.txt")
        # bpy.farmRender.actionCalculateCosts()
        webbrowser.open_new("www.google.com")
        return {"FINISHED"}
 

class Farm_OT_SetupScenesRender(bpy.types.Operator):
    bl_idname = "farm.setup_scenes_render"
    bl_label = "Setup Scenes Render"

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        props = farmProps()
        return props.batch_render

    def execute(self, context: bpy.types.Context) -> Set[str]:
        upload_scenes = [scene for scene in bpy.data.scenes if scene.upload_scene]
        if not upload_scenes:
            self.report(type= {'ERROR'}, message="At least one scene needs to be selected")
            # return {'FINISHED'}
        else:
            pass
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text="Select scenes to upload:")

        for sc in bpy.data.scenes:
            row = col.row()
            row.prop(sc, "upload_scene", text="")
            row.label(text= f'{sc.name}')


class Farm_OT_CheckDefaultFrameRange(bpy.types.Operator):
    bl_idname = "farm.check_frames"
    bl_label = "Check frame range"

    def execute(self, context: bpy.types.Context) -> Set[str]:
        bpy.ops.farm.send("EXEC_DEFAULT")
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        if bpy.context.scene.frame_start == 1 and bpy.context.scene.frame_end == 250:
            return cast(Set[str], context.window_manager.invoke_props_dialog(self))
        return {"FINISHED"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Do you really want to render from frame 1 to 250?")


class Farm_OT_SceneExportSuccess(bpy.types.Operator):
    bl_idname = "farm.project_export_success"
    bl_label = "Upload"

    def execute(self, context: bpy.types.Context) -> Set[str]:
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        return cast(Set[str], context.window_manager.invoke_props_dialog(self))

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Project has been successfully exported naeim🧑!")


class Farm_OT_About(bpy.types.Operator):
    bl_idname = "farm.about"
    bl_label = "About"

    def execute(self, context: bpy.types.Context) -> Set[str]:
        return {"FINISHED"}

    def invoke(self, context: bpy.types.Context, event: Any) -> Set[str]:
        context.window_manager.invoke_popup(self, width=350)
        return {"RUNNING_MODAL"}

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        layout.label(text="Renderfarm")
        layout.separator()
        layout.label(text="Exports .blend files to Farm Desk")
        layout.separator()
        layout.operator("farm.visit_farm")


class Farm_OT_FurtherAction(bpy.types.Operator):
    """Perform further fixes to some common errors"""
    bl_idname = "farm.further_action"
    bl_label = "(click here)"

    op_id: bpy.props.IntProperty()

    def execute(self, context: bpy.types.Context) -> Set[str]:
        result = bpy.farmRender.results[self.op_id]
        validator = result.validator
        known_error_types = [opmap.type_ for opmap in operators_list.op_maps]
        if result.type in known_error_types:
            exec(operators_list.run_operator(result.type))
        elif hasattr(validator, "furtherAction"):
            validator.furtherAction(self, result)
        else:
            self.report(type={'INFO'}, message= result.message)
        return {"FINISHED"}


class Farm_OT_VisitFarm(bpy.types.Operator):
    bl_idname = "farm.visit_farm"  

  

class Farm_OT_BakeScriptedExpressions(bpy.types.Operator):
    """Bake all scripted expressions"""
    bl_idname = "farm.bake_expressions"
    bl_label = "Bake all scripted expressions"

    bake_anyway: bpy.props.BoolProperty(name= "I've already saved a backup", default= False)

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        return True

    def execute(self, context: bpy.types.Context) -> Set[str]:
        if self.bake_anyway:
            scene = context.scene
            for ob in bpy.data.objects:
                bake_scripted_drivers(ob, scene)

            bpy.ops.farm.check()
        return {"FINISHED"}

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "We recommend saving a backup of the blend file before baking scripted expressions")
        col.prop(self, "bake_anyway")


def register():
    # for icon images initialization
    import bpy.utils.previews
    pcoll = bpy.utils.previews.new()
    my_icons_dir = os.path.join(os.path.dirname(__file__), "res")
    pcoll.load("calc_icon", os.path.join(my_icons_dir, "calc.png"), 'IMAGE')
    pcoll.load("calc_icon_cloud", os.path.join(my_icons_dir, "calc_cloud.png"), 'IMAGE')
    preview_collections["main"] = pcoll


def unregister():
    for pcoll in preview_collections.values():
        bpy.utils.previews.remove(pcoll)
    preview_collections.clear()
