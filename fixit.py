"""Here I've added a new fixIt module to isolate my changes rather than 
using renderfarm.Farm_OT_FurtherAction right away. This module derails some of the actions intended 
for validator.furtherAction()
"""
import bpy
from bpy_extras.io_utils import ImportHelper
import os
from dataclasses import dataclass
from typing import List
from .utilitis import bake_scripted_drivers

@dataclass(frozen= True)
class OperatorMap:
    """A class to return the relevant operator for result error type"""
    type_: int
    operator: str = ""

    def prepare_operator(self):
        if self.operator != "":
            return f"bpy.ops.{self.operator}('INVOKE_DEFAULT', result_type= result.type, info_1= result.info_1, info_2= result.info_2)"

@dataclass
class OperatorsMapList:
    op_maps: List[OperatorMap]

    def run_operator(self, error_type: int):
        for m in self.op_maps:
            if m.type_ == error_type:
                return m.prepare_operator()

# A list of all the known error types and their relevant operators
operators_list = OperatorsMapList(
    [
        OperatorMap(1,"farm.manage_missing_image"),
        OperatorMap(2, "farm.fix_output"),
        OperatorMap(3, "farm.bake_ocean"),
        OperatorMap(4, "farm.mesh_cache_filepath"),
        OperatorMap(5, "farm.bake_fluidsim"),
        OperatorMap(6, "farm.bake_clothsim"),
        OperatorMap(7, "farm.bake_scripted"),
        OperatorMap(8, "farm.bake_particles"),
        OperatorMap(9, "farm.fix_camera"),
        OperatorMap(10, "farm.bake_fluid_flip"),
        OperatorMap(11, "farm.save_blend"),
        OperatorMap(12, "farm.fix_samples"),
        OperatorMap(13, "farm.fix_render_border"),
        OperatorMap(14, "farm.bake_hair_dynamics")
    ]
)

class FixMe:
    """ A base class that includes all the Test results necessary properties 
    to inherit later in operator classes
    """
    result_type: bpy.props.IntProperty()
    info_1: bpy.props.StringProperty()
    info_2: bpy.props.StringProperty()

def replace_image(image, new_image_path):
        """Replace image path of image with new_image_path"""
        img = bpy.data.images.get(image)
        abspath = bpy.path.abspath(new_image_path)
        img.filepath = abspath

class Farm_ReplaceImage(bpy.types.Operator, ImportHelper):
    """Replace Image, This operator is necessary for opening a new file browser window to search
    for a Texture image replacement
    """
    bl_idname = "farm.replace_image"
    bl_label = "Find Image"
    bl_options = {'UNDO'}

    # filter to display only image files in the file browser
    filter_glob: bpy.props.StringProperty(
        default= "*" + ";*".join(bpy.path.extensions_image),
        options= {'HIDDEN'}
    )

    image: bpy.props.StringProperty()

    def execute(self, context):
        replace_image(self.image, self.filepath)
        return {'FINISHED'}

class Farm_ManageMissingImage(bpy.types.Operator, FixMe):
    """Manage missing images replacement
    Error Message: File not found
    Error Type: 1
    """
    bl_idname = "farm.manage_missing_image"
    bl_label = "Manage Missing Image"
    bl_options = {'UNDO'}

    replace: bpy.props.BoolProperty(name= "Replace with a dummy image", default= False)

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        if self.replace:
            dummypath = os.path.join(os.path.dirname(__file__), "dummy.jpg")
            replace_image(self.info_1, dummypath)
            print("Image replaced with dummy")
            bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "Replace image")
        col.prop(self, "replace")
        sub = col.column()
        sub.operator("farm.replace_image").image = self.info_1
        if self.replace:
            sub.enabled = False

class Farm_FixOutput(bpy.types.Operator, FixMe):
    """Fix file output problem
    Error Message: "Output: Requires filename"
    Error Type: 2
    """
    bl_idname = "farm.fix_output"
    bl_label = "Fix Output"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene = bpy.data.scenes.get(self.info_1)
        col = layout.column()
        col.label(text= "Add output file path")
        col.prop(scene.render, "filepath")
        col.prop(scene.render.image_settings, "file_format")

class Farm_BakeOcean(bpy.types.Operator, FixMe):
    """Fix Ocean modifier problem
    Error Message: "Ocean Modifier: Was not baked."
    Error Type: 3
    """
    bl_idname = "farm.bake_ocean"
    bl_label = "Bake Ocean"

    def invoke(self, context, event):
        ob = bpy.data.objects.get(self.info_1)
        bpy.context.view_layer.objects.active = ob
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "Bake Ocean modifier")
        op = col.operator("object.ocean_bake")
        op.modifier = bpy.data.objects[self.info_1].modifiers[self.info_2].name
        op.free = False

class Farm_MeshCacheFilepath(bpy.types.Operator, FixMe):
    """Fix Mesh cache problem
    Error Message: "MeshCache: File not found."
    Error Type: 4
    """
    bl_idname = "farm.mesh_cache_filepath"
    bl_label = "Mesh Cache Filepath"

    def invoke(self, context, event):
        ob = bpy.data.objects.get(self.info_1)
        bpy.context.view_layer.objects.active = ob
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "Path to external displacements file")
        mod = bpy.data.objects[self.info_1].modifiers[self.info_2]
        col.prop(mod, "filepath")


class Farm_BakeFluid(bpy.types.Operator, FixMe):
    """Fix fluid simulation baking
    Error Message: "Fluid Modifier: Was not baked. (FLUID_SIMULATION)"
    This operator is to bake fluid simulation in Old blender versions pre Mantaflow simulation (pre Blender 2.82)
    Error Type: 5
    """
    bl_idname = "farm.bake_fluidsim"
    bl_label = "Bake Fluid Simulation"

    def invoke(self, context, event):
        # ob = bpy.data.objects.get(self.info_1)
        # bpy.context.view_layer.objects.active = ob
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        ob = bpy.data.objects.get(self.info_1)
        scene = [sc for sc in bpy.data.scenes if ob.name in sc.objects][0]

        bpy.ops.fluid.bake({'scene': scene, 'active_object': ob})
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "Bake this fluid simulation?")

class Farm_BakeClothSim(bpy.types.Operator, FixMe):
    """Fix cloth simulation baking
    Error Message: "Cloth Modifier: Cloth Cache Was never baked. Bake or use external files."
    Error Type: 6
    """
    bl_idname = "farm.bake_clothsim"
    bl_label = "Bake Cloth Simulation"

    point_cache_name: bpy.props.StringProperty(default= "point_cache_01")

    @classmethod
    def poll(cls, context):
        # mod = bpy.data.objects[self.info_1].modifiers[self.info_2]
        # return mod.point_cache.use_disk_cache
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        ob = bpy.data.objects.get(self.info_1)
        scene = [sc for sc in bpy.data.scenes if ob.name in sc.objects][0]
        # mod = ob.modifiers[self.info_2]
        mod = [mod for mod in ob.modifiers if mod.type == 'CLOTH'][0]
        mod.point_cache.name = self.point_cache_name
        override = {'scene': scene, 'active_object': ob, 'point_cache': mod.point_cache}
        bpy.ops.ptcache.bake(override, bake= True)
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        ob = bpy.data.objects.get(self.info_1)
        mod = [mod for mod in ob.modifiers if mod.type == 'CLOTH'][0]
        layout = self.layout
        col = layout.column()
        col.label(text= "Bake cloth simulation?")
        col.prop(self, "point_cache_name")
        col.prop(mod.point_cache, "use_disk_cache")
        col.prop(mod.point_cache, "frame_start")
        col.prop(mod.point_cache, "frame_end")

class Farm_BakeScripted(bpy.types.Operator, FixMe):
    """Bake Scripted expressions
    Error Message: "Scripted Expressions are unsupported."
    Error Type: 7
    """
    bl_idname = "farm.bake_scripted"
    bl_label = "Bake Scripted Expressions"
    bl_options = {'UNDO'}

    bake_anyway: bpy.props.BoolProperty(name= "Bake anyway, I've already saved a backup", default= False)
    bake_all: bpy.props.BoolProperty(name= "Bake all scripted expressions", default= False)

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self, width=500)

    def execute(self, context):
        scene = context.scene
        
        if self.bake_anyway and self.bake_all:
            # bake for all objects
            for ob in bpy.data.objects:
                bake_scripted_drivers(ob, scene)
        elif self.bake_anyway:
            ob = bpy.data.objects.get(self.info_1)
            bake_scripted_drivers(ob, scene)
        else:
            self.report(type= {'WARNING'}, message= "No scripted expressions were baked, please select bake anyway checkbox")

        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "We recommend saving a backup of the blend file before baking scripted expressions")
        col.prop(self, "bake_anyway")

        col = layout.column()
        col.prop(self, "bake_all")
        if not self.bake_anyway:
            col.enabled = False

class Farm_BakeParticles(bpy.types.Operator, FixMe):
    """Fix Particles Baking
    Error Message: "Disk Cache not activated, activate Disk Cache or use external."
    And: "Cache outdated. Free bake and rebake."
    And: "Please enter a name for the Point Cache of"
    Error Type: 8
    """
    bl_idname = "farm.bake_particles"
    bl_label = "Bake Particles"

    point_cache_name: bpy.props.StringProperty(default= "point_cache_01")

    @classmethod
    def poll(cls, context):
        return mod.point_cache.use_disk_cache

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        ob = bpy.data.objects.get(self.info_1)
        scene = [sc for sc in bpy.data.scenes if ob.name in sc.objects][0]
        mod = [mod for mod in ob.modifiers if mod.type == 'PARTICLE_SYSTEM'][0]
        mod.particle_system.point_cache.name = self.point_cache_name
        override = {'scene': scene, 'active_object': ob, 'point_cache': mod.particle_system.point_cache}
        bpy.ops.ptcache.bake(override, bake= True)
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        ob = bpy.data.objects.get(self.info_1)
        mod = [mod for mod in ob.modifiers if mod.type == 'PARTICLE_SYSTEM'][0]
        layout = self.layout
        col = layout.column()
        col.label(text= "Bake Particles?")
        col.prop(self, "point_cache_name")
        col.prop(mod.particle_system.point_cache, "use_disk_cache")


class Farm_FixCamera(bpy.types.Operator, FixMe):
    """Fix the missing scene camera issue
    Error Message: "Camera: Camera missing. Add a camera object to the scene."
    Error Type: 9
    """
    bl_idname = "farm.fix_camera"
    bl_label = "Add scene camera"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column()
        col.label(text= "Select a scene camera")
        col.prop(scene, "camera")


class Farm_BakeFluidFlip(bpy.types.Operator, FixMe):
    """Fix Flip fluids baking
    Error Message: "PointCache: Was not baked. Bake or use external."
    Error Type: 10
    """
    bl_idname = "farm.bake_fluid_flip"
    bl_label = "Bake Point Cache"

    point_cache_name: bpy.props.StringProperty(default= "point_cache_01")

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def is_fluid(self):
        """This function checks if this is a fluid simulation or a normal particles system"""
        ob = bpy.data.objects.get(self.info_1)
        mod_types = [mod.type for mod in ob.modifiers]
        if 'FLUID' in mod_types and 'PARTICLE_SYSTEM' in mod_types:
            # if it's a fluid simulation
            return True
        else:
            return False

    def execute(self, context):
        ob = bpy.data.objects.get(self.info_1)
        scene = [sc for sc in bpy.data.scenes if ob.name in sc.objects][0]
        mod = [mod for mod in ob.modifiers if mod.type == 'FLUID'][0]
        override = {'scene': scene, 'active_object': ob}

        if mod.domain_settings.cache_type in ['FINAL', 'ALL']:
            bpy.ops.fluid.bake_all(override)
            bpy.ops.farm.check()
        else:
            self.report(type= {'ERROR'}, message= "Simulation is not baked, make sure to change Cache type to Final/All")
        return {'FINISHED'}

    def draw(self, context):
        ob = bpy.data.objects.get(self.info_1)
        layout = self.layout
        col = layout.column()

        mod = [mod for mod in ob.modifiers if mod.type == 'FLUID'][0]

        col.label(text= "Change Cache Type Final to bake simulation")
        col.prop(mod.domain_settings, "cache_type")
        if mod.domain_settings.cache_type in ['FINAL', 'ALL']:
            col.prop(mod.domain_settings, "cache_directory")
            col.prop(mod.domain_settings, "cache_frame_start")
            col.prop(mod.domain_settings, "cache_frame_end")
            

class Farm_SaveBlend(bpy.types.Operator, FixMe):
    """Fix the unsaved blend file issue
    Error Message: "Please save the project before exporting to Farm   Desk!"
    Error Type: 11
    """
    bl_idname = "farm.save_blend"
    bl_label = "Save Blend File"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.wm.save_mainfile('INVOKE_DEFAULT')
        bpy.ops.farm.check() # this one won't work after saving the file, it needs to be added to a post save handler instead
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        col = layout.column()
        col.label(text= "Click 'Ok' to save the current blend file")


class Farm_FixCyclesSamples(bpy.types.Operator, FixMe):
    """Fix cycles render samples setting
    Error Message: "Cycles: Samples seem to be very high"
    Error Type: 12
    """
    bl_idname = "farm.fix_samples"
    bl_label = "Change Cycles Render Samples"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column()
        # col.label(text= "Select a scene camera")
        col.prop(scene.cycles, "samples")


class Farm_FixRenderBorder(bpy.types.Operator, FixMe):
    """Fix render border issue
    Error Message: "Dimensions: Border is active"
    Error Type: 13
    """
    bl_idname = "farm.fix_render_border"
    bl_label = "Deactivate Render Border"

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        col = layout.column()
        # col.label(text= "Select a scene camera")
        col.prop(scene.render, "use_border")


class Farm_BakeHairDynamics(bpy.types.Operator, FixMe):
    """Fix hair dynamics baking
    Error Message: "Hair dynamics: PointCache Was not baked. Bake or use external."
    Error Type: 14
    """
    bl_idname = "farm.bake_hair_dynamics"
    bl_label = "Bake Hair Dynamics"

    point_cache_name: bpy.props.StringProperty(default= "point_cache_01")

    @classmethod
    def poll(cls, context):
        return True

    def invoke(self, context, event):
        wm = context.window_manager
        return wm.invoke_props_dialog(self)

    def execute(self, context):
        ob = bpy.data.objects.get(self.info_1)
        scene = [sc for sc in bpy.data.scenes if ob.name in sc.objects][0]
        mod = [mod for mod in ob.modifiers if mod.type == 'PARTICLE_SYSTEM'][0]
        mod.particle_system.point_cache.name = self.point_cache_name
        override = {'scene': scene, 'active_object': ob, 'point_cache': mod.particle_system.point_cache}
        bpy.ops.ptcache.bake(override, bake= True)
        bpy.ops.farm.check()
        return {'FINISHED'}

    def draw(self, context):
        ob = bpy.data.objects.get(self.info_1)
        mod = [mod for mod in ob.modifiers if mod.type == 'PARTICLE_SYSTEM'][0]
        layout = self.layout
        col = layout.column()
        col.prop(self, "point_cache_name")
        col.prop(mod.particle_system.point_cache, "use_disk_cache")
        col.prop(mod.particle_system.point_cache, "frame_start")
        col.prop(mod.particle_system.point_cache, "frame_end")


classes= (
    Farm_ManageMissingImage,
    Farm_ReplaceImage,
    Farm_FixOutput,
    Farm_BakeOcean,
    Farm_MeshCacheFilepath,
    Farm_BakeFluid,
    Farm_BakeClothSim,
    Farm_BakeScripted,
    Farm_BakeParticles,
    Farm_FixCamera,
    Farm_BakeFluidFlip,
    Farm_SaveBlend,
    Farm_FixCyclesSamples,
    Farm_FixRenderBorder,
    Farm_BakeHairDynamics
)

def register():
    for cls in classes:
        bpy.utils.register_class(cls)

def unregister():
    for cls in classes:
        bpy.utils.unregister_class(cls)
