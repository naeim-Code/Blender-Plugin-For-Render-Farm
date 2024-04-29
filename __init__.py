import json
import os
from typing import List, Tuple, cast 
bl_info = {
    "name": "Render Farm",
    "author": "Render Farm <info@RenderFarm.com>",
    "version": (3,),
    "blender": (2, 80, 0),
    "location": "Properties > Render > Render Farm",
    "description": "Exports .blend files to Render Farm",
    "warning": "", 
    "category": "Render",
}

if "bpy" in locals():
    import imp
    import importlib
    if "renderfarm" in locals(): 
        importlib.reload(renderfarm)
        importlib.reload(fixIt)

    imp.reload(renderfarm)   
else:
    import bpy
    from bpy.props import ( 
        BoolProperty,
        EnumProperty,
        PointerProperty,
        StringProperty,
    )
    from . import renderfarm
    from . import fixIt
from bpy.app.handlers import persistent

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
            bake_scripted_drivers,
            getPrioritiesArray
        )

class FarmSettings(bpy.types.PropertyGroup):
    result_filter: EnumProperty(  
        name="Filter",
        items=(
            ("0", "All", "Show all results"),
            ("1", "Warning", "Show only Warnings"),
            ("2", "Error", "Show only Errors"),
        ),
        default="0",
    )

    is_auto_start: BoolProperty(
        name="Activate autostart",
        description="Auto start the render job once uploaded",
        default= False
    )

    is_distributed: BoolProperty(
        name="Render distributed",
        description= "Rendering your file on multiple servers",
        default= False
    )

    batch_render: BoolProperty(
        name="Activate Scenes Render",
        description="Render multiple scenes",
        default= False
    )

    is_send_email: BoolProperty(
        name="Send e-mail",
        description="Send an e-mail notification",
        default= False
    )

    is_by_start: BoolProperty(
        name="by start",
        description="send e-mail notification when render starts",
        default= False
    )

    is_by_finish: BoolProperty(
        name="when complete",
        description="send e-mail notification when render finishes",
        default= False
    )

    priority: EnumProperty(
        name="Priority",
        items = getPrioritiesArray,
    )

    is_cost_estimation: BoolProperty(
        default= False
    )

    
classes = (
    FarmSettings,
    renderfarm.RENDER_PT_farm_panel_view3d,
    renderfarm.RENDER_PT_farm_panel_prop,
    renderfarm.RENDER_PT_farm_account,
    renderfarm.RENDER_PT_farm_settings, 
    renderfarm.RENDER_PT_notifications,
    renderfarm.RENDER_PT_farm_check_results, 
    renderfarm.RENDER_PT_farm_account_prop,
    renderfarm.RENDER_PT_farm_settings_prop, 
    renderfarm.RENDER_PT_notifications_prop,
    renderfarm.RENDER_PT_farm_check_results_prop, 
    renderfarm.Farm_OT_Check,
    renderfarm.Farm_OT_Send,
    renderfarm.Farm_OT_CostCalculator, 
    renderfarm.Farm_OT_CheckDefaultFrameRange,
    renderfarm.Farm_OT_SceneExportSuccess,
    renderfarm.Farm_OT_About,
    renderfarm.Farm_OT_FurtherAction, 
    renderfarm.Farm_OT_SetupScenesRender,
    renderfarm.Farm_OT_BakeScriptedExpressions
) 

def update_handler(dummy): 
    if bpy.context.scene.frame_end - bpy.context.scene.frame_start >= 1:
        bpy.context.scene.farm.is_distributed = False

@persistent
def load_handler(dummy): 
    bpy.farm.results.clear()

bpy.app.handlers.depsgraph_update_post.append(update_handler)



bpy.app.handlers.load_pre.append(load_handler)

def register():
    renderfarm.register()
    fixIt.register()

    from bpy.utils import register_class  # pylint: disable = no-name-in-module, import-error

    for cls in classes:
        register_class(cls)
    bpy.types.WindowManager.farm = PointerProperty(type=FarmSettings, name="Render Farm")
    bpy.types.Scene.upload_scene = BoolProperty(name="Upload Scene", default= True)


def unregister():
    renderfarm.unregister()
    fixIt.unregister()
    from bpy.utils import unregister_class  # pylint: disable = no-name-in-module, import-error

    for cls in classes:
        unregister_class(cls)
    del bpy.types.WindowManager.farm
    del bpy.types.Scene.upload_scene
    


# register()
