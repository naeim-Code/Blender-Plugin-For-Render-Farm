from __future__ import annotations
import os
import bpy
import shutil
import hashlib
import itertools
import json
from contextlib import suppress

from typing import List, Tuple, cast


def debuglog(text: str) -> None:
    if True:
        print(text)


def checkFilename(filename: str) -> bool:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_-. "
    return all(ch in allowed for ch in filename)


def changeFilename(filename: str) -> str:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_-. "

    is_changed = False
    for i in range(len(filename)):
        if filename[i] not in allowed:
            filename = filename.replace(filename[i], "_")
            is_changed = True

    return filename if is_changed else ""


def getChangedBlenderFilename() -> str:
    path: str = bpy.context.blend_data.filepath
    fn = os.path.basename(path)
    changed = changeFilename(fn)

    if changed != "":
        fn = changed

    fn = fn.replace(" ", "_")
    return fn or "untitled.blend"


def calcMd5(filepath: str) -> str:
    try:
        data = open(filepath, "rb").read()
        return hashlib.md5(data).hexdigest()
    except OSError:
        return "0"


def isPictureFormat(fmt: str) -> bool:
    fmt = fmt.upper()
    formats = [
        "BMP",
        "DDS",
        "IRIS",
        "PNG",
        "JPEG",
        "JPEG2000",
        "TARGA",
        "TARGA_RAW",
        "CINEON",
        "DPX",
        "MULTILAYER",
        "OPEN_EXR",
        "OPEN_EXR_MULTILAYER",
        "HDR",
        "TIFF",
    ]

    return fmt in formats


def isDRPictureFormat(fmt: str) -> bool:
    formats = ["BMP", "PNG", "TIFF", "OPEN_EXR", "OPEN_EXR_MULTILAYER"]
    return fmt in formats


def isMovieTexture(tex: str) -> bool:
    suffixes = [".mov", ".avi", ".mpg", ".mpeg", ".wmv", ".asf", ".mp4", ".flv", ".divx"]
    return tex in suffixes


def generatePreview(path: str) -> None:
    with suppress(Exception):
        src = os.path.join(os.path.dirname(__file__), "logo.jpg")
        print(src)
        print(path)
        shutil.copyfile(src, path)


def TexPath(path: str) -> str:
    return f"X:\\{path}\\tex"


def createFarmOutputPath(user: str, output_path: str) -> str:
    return f"C:\\logs\\output\\{user}\\{os.path.basename(output_path)}"


def generateLocalOutputPath(output_path: str) -> str:
    if output_path.startswith("/tmp"):
        return ""
    else:
        return os.path.abspath(os.path.dirname(output_path))


def getConfigFileContent() -> List[str]:
    import codecs

    file_ = os.path.join(os.path.dirname(__file__), "clientsettings.cfg")
    try:
        cfgfile = open(file_, "r", encoding="utf-8-sig")
        lines = itertools.takewhile(lambda line: line, cfgfile)
        return [line.replace("\r", "").replace("\n", "") for line in lines]
    except:
        print(f"clientsettings.cfg not found at {file_}")
        return []


def manager_version(manager_path: str) -> str:
    version_file = os.path.join(os.path.dirname(manager_path), "version.txt")
    try:
        with open(version_file, "r", encoding="utf-8-sig") as f:
            return f.read().strip()
    except:
        print(f"version.txt not found at {version_file}")
        return ""


def readFtpFileContents(filePath: str) -> Tuple[List[str], List[int]]:
    contsFiles = []
    contsSizes = []
    with open(filePath, "r", encoding="utf-8-sig") as file_:
        for f in file_:
            with suppress(Exception):
                # FIXME: not all filesystems are case insensitive
                filename, filesize = f.split(":")
                contsFiles.append(filename.lower())
                contsSizes.append(int(filesize))
    return contsFiles, contsSizes


def is_gpu_render() -> bool:
    renderer = bpy.context.scene.render.engine
    
    is_cycles_gpu = renderer == "CYCLES" and cast(str, bpy.context.scene.cycles.device) == "GPU"

    if renderer == "LUXCORE":
        is_luxcore_gpu = bpy.context.scene.luxcore.config.device == "OCL"
        return is_luxcore_gpu

    if renderer == "octane":
        # octane only uses GPU rendering
        return True

    return is_cycles_gpu or renderer == "BLENDER_EEVEE"

 
def unique_filename(location: str, filename: str, ext: str) -> str:
    """
    Returns `os.path.join(location, filename+ext)` if it doesn't exist.
    Otherwise it appends numbers to `filename` until one is found without conflicts.
    """
    names = itertools.chain([filename + ext], (f"{filename}_{i}{ext}" for i in itertools.count(1)))
    paths = (os.path.join(location, name) for name in names)
    return next(p for p in paths if not os.path.exists(p))

def farmProps():
    """gets farm properties instead of using them directly in code"""
    props = bpy.context.window_manager.sky
    return props

def bake_scripted_drivers(ob: bpy_types.Object, scene: bpy.types.Scene):
    """Bake and remove all scripted expression drivers in an object"""
    current_frame = scene.frame_current
    frame_step = 1

    if ob.animation_data:
        if ob.animation_data.drivers:
            f = scene.frame_start
            while f <= scene.frame_end:
                # bake all object drivers
                scene.frame_set(f)
                for d in ob.animation_data.drivers:
                    if d.driver.type == 'SCRIPTED':
                        ob.keyframe_insert(d.data_path)
                f += frame_step

            # remove all drivers
            for d in ob.animation_data.drivers:
                if d.driver.type == 'SCRIPTED':
                    ob.animation_data.drivers.remove(d)

def getPrioritiesArray(self, context):
    cpuPrice = 1.2
    cpuStep = 0.6
    gpuPrice = 0.9
    gpuStep = 0.5
    modifiedDate = 0
    extraCost = 0
 
    conf = getConfigFileContent()
    if len(conf) >= 4:
        m_defaultPath = conf[1]

    filePath = os.path.join(m_defaultPath, "ghzprices.json") 
    try:

        with open(filePath) as json_file:
            pricesjson = json.load(json_file)

            cpuPrice = pricesjson['cpu_price']
            cpuStep = pricesjson['cpu_price_step']
            gpuPrice = pricesjson['gpu_price']
            gpuStep = pricesjson['gpu_price_step']

            scene = bpy.context.scene
            activeRenderer = scene.render.engine
            for renderer in pricesjson['renderers']:
                if renderer['name'] in activeRenderer:
                    extraCost += renderer['price']

            for program in pricesjson['programs']:
                if renderer['name'] in 'BLENDER':
                    extraCost += program['price']

    except:
        pass
    finally:
        try:
            pass  # fh.close()
        except:
            pass

    # build priorities array
    #     ("1", "Standard (0,9 Cent/OBh)", ""),
    #     ("2", "Prio +1 (1,4 Cent/OBh)", ""),
    priorities = []

    price = cpuPrice
    priceStep = cpuStep
    unit = " / GHzh"
    if is_gpu_render():
        price = gpuPrice
        priceStep = gpuStep        
        unit = " / Obh"
 

    
    priorityList= ["Bronze","Silver","Gold"]
    count = 0
    while count < 3:
        priorities.append((str(count), priorityList[count] + unit, ""))
        count += 1

    return priorities

    


    
