# ##### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Lightdesk",
    "description": "Control multiple scene lights from a single Lightdesk panel in the 3D view",
    "author": "Quentin Walker",
    "blender": (2, 80, 0),
    "version": (0, 2, 0),
    "category": "Lighting",
    "location": "View3D > Sidebar > Lightdesk",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
}

import bpy
from bpy.props import (StringProperty,
                       BoolProperty,
                       CollectionProperty,
                       IntProperty,
                       FloatProperty,
                       FloatVectorProperty,
                       EnumProperty,
                       PointerProperty,
                       )
from bpy.types import PropertyGroup
from bpy.types import (Panel,
                       Menu,
                       Operator,
                       PropertyGroup,
                       UIList,
                       )
from bpy.utils import (register_class,
                       unregister_class,
                       )
from bpy.app.handlers import persistent
from uuid import uuid4
import logging
import queue

logging.basicConfig(level = logging.DEBUG)

light_types = ['AREA', 'POINT', 'SPOT', 'SUN']
exec_queue = queue.SimpleQueue()
tracked_scene = object()

# Core -------------------------------------------------------------------------

def startup():
    logging.debug("startup")
    try:
        append_exec_queue(get_lights)
        append_exec_queue(filter_lights)
        append_exec_queue(track_scene)
        append_exec_queue(rebuild_ui)
        add_handlers()
        add_timers()
    except Exception as e:
        logging.error(e)
        shutdown()

def shutdown():
    logging.debug("shutdown")
    try:
        purge_panels()
        remove_timers()
        remove_handlers()
    except Exception as e:
        logging.error(e)

def add_timers():
    if not bpy.app.timers.is_registered(exec_queued):
        logging.debug("add_timers")
        bpy.app.timers.register(exec_queued)

def remove_timers():
    if bpy.app.timers.is_registered(exec_queued):
        logging.debug("remove_timers")
        bpy.app.timers.unregister(exec_queued)

def add_handlers():
    logging.debug("add_handlers")
    if load_pre not in bpy.app.handlers.load_pre:
        logging.debug("- load_pre")
        bpy.app.handlers.load_pre.append(load_pre)
    if load_post not in bpy.app.handlers.load_post:
        logging.debug("- load_post")
        bpy.app.handlers.load_post.append(load_post)
    if depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        logging.debug("- depsgraph_update_post")
        bpy.app.handlers.depsgraph_update_post.append(depsgraph_update_post)

def remove_handlers():
    logging.debug("remove_handlers")
    if load_pre in bpy.app.handlers.load_pre:
        logging.debug("- load_pre")
        bpy.app.handlers.load_pre.remove(load_pre)
    if load_post in bpy.app.handlers.load_post:
        logging.debug("- load_post")
        bpy.app.handlers.load_post.remove(load_post)
    if depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        logging.debug("- depsgraph_update_post")
        bpy.app.handlers.depsgraph_update_post.remove(depsgraph_update_post)

@persistent
def load_pre(scene):
    logging.debug(f"load_pre {scene}")
    try:
        lightdesk = bpy.context.scene.lightdesk
        purge_panels()
    except Exception as e:
        pass

@persistent
def load_post(scene):
    logging.debug(f"load_post {scene}")
    track_scene()
    fill_panels()

@persistent
def depsgraph_update_post(scene):
    logging.debug(f"depsgraph_update_post {scene}")
    if scene_changed():
        track_scene()
    elif len(bpy.context.scene.objects) != len(tracked_scene.objects):
        get_lights()
        filter_lights()

def append_exec_queue(function):
    logging.debug(f"append_exec_queue {function}")
    exec_queue.put(function)

def exec_queued():
    while not exec_queue.empty():
        function = exec_queue.get()
        logging.debug(f"exec_queued {function}")
        function()
    return 1.0

# Tracking ---------------------------------------------------------------------

def track_scene():
    global tracked_scene
    tracked_scene = bpy.context.scene
    logging.debug(f"track_scene {tracked_scene.name}")

def scene_changed():
    global tracked_scene
    changed = False
    try:
        changed = tracked_scene != bpy.context.scene
    except InvalidReference:
        changed = True
    if changed:
        logging.debug(f"scene_changed")
    return changed

def debug_data():
    global tracked_scene
    scene = bpy.context.scene.lightdesk
    ui = bpy.context.window_manager.lightdesk
    logging.debug(f"{tracked_scene.name}: {scene.filtered.keys()}, {scene.selected}")
    if len(scene.channels):
        logging.debug(f"{len(scene.channels)} channels:")
        for channel in scene.channels:
            logging.debug(f"- {channel.name}, {channel.object.name}")
    if len(ui.panels):
        logging.debug(f"{len(ui.panels)} panels:")
        for panel in ui.panels:
            logging.debug(f"- {panel.name}")

# Lights -----------------------------------------------------------------------

def get_lights():
    logging.debug("get_lights")
    lightdesk = bpy.context.scene.lightdesk
    lightdesk.lights.clear()
    lights = [object for object in bpy.context.scene.objects if object.type == 'LIGHT']
    for light in lights:
        collect_light(light, lightdesk.lights)

def get_light_index(id):
    return bpy.context.scene.lightdesk.filtered.find(id)

def filter_lights():
    logging.debug("filter_lights")
    lightdesk = bpy.context.scene.lightdesk
    lightdesk.filtered.clear()
    for light in lightdesk.lights:
        if light.object.data.type == 'AREA':
            if lightdesk.list_area:
                collect_light(light.object, lightdesk.filtered)
        elif light.object.data.type == 'POINT':
            if lightdesk.list_point:
                collect_light(light.object, lightdesk.filtered)
        elif light.object.data.type == 'SPOT':
            if lightdesk.list_spot:
                collect_light(light.object, lightdesk.filtered)
        elif light.object.data.type == 'SUN':
            if lightdesk.list_sun:
                collect_light(light.object, lightdesk.filtered)

def update_filters(self, context):
    logging.debug("update_filters")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected >= 0:
        old_selection = lightdesk.lights[lightdesk.selected].name
    filter_lights()
    if lightdesk.selected >= 0:
        new_selection = lightdesk.filtered[lightdesk.selected].name
        if new_selection == old_selection:
            lightdesk.selected = get_light_index(lightdesk.lights[lightdesk.selected].name)
        else:
            lightdesk.selected = -1

def collect_light(object, collection):
    logging.debug(f"collect_light {object.name} {collection}")
    light = collection.add()
    light.name = object.name
    light.object = object

def get_selected_light():
    logging.debug("get_scelected_light")
    lightdesk = bpy.context.scene.lightdesk
    return lightdesk.filtered[lightdesk.selected].object

def add_light(light):
    logging.debug(f"add_light {light}")
    if not get_channel(light):
        create_channel(light)

def add_selected_light():
    logging.debug("add_selected_light")
    light = get_selected_light()
    add_light(light)

def add_all_lights():
    logging.debug("add_all_lights")
    for light in bpy.context.scene.lightdesk.filtered:
        add_light(light.object)

# Channels ---------------------------------------------------------------------

def get_channel(light):
    logging.debug(f"get_channel {light}")
    channels = bpy.context.scene.lightdesk.channels
    for channel in channels:
        if channel.object == light:
            return channel.name
    return None

def get_channel_index(id):
    logging.debug(f"get_channel_index {id}")
    channels = bpy.context.scene.lightdesk.channels
    return channels.find(id)


def add_channel(id, light):
    logging.debug(f"add_channel {id} {light}")
    channels = bpy.context.scene.lightdesk.channels
    if get_channel_index(id) < 0:
        channel = channels.add()
        channel.name = id
        channel.object = light

def create_channel(light):
    logging.debug(f"create_channel {light}")
    if not get_channel(light):
        id = get_panel_id()
        add_channel(id, light)
        add_panel(id)

def remove_channel(id):
    logging.debug(f"remove_channel {id}")
    channels = bpy.context.scene.lightdesk.channels
    index = get_channel_index(id)
    if index >= 0:
        channel = channels.remove(index)

def delete_channel(channel):
    logging.debug(f"delete_channel {channel}")
    remove_panel(channel)
    remove_channel(channel)

def delete_all_channels():
    logging.debug("delete_all_channels")
    channels = bpy.context.scene.lightdesk.channels
    for channel in reversed(channels):
        delete_channel(channel.name)

def deadhead_channels():
    logging.debug("deadhead_channels")
    lightdesk = bpy.context.scene.lightdesk
    for channel in lightdesk.channels:
        if len(channel.name):
            try:
                class_name = f"bpy.types.{channel.name}"
                cls = eval(class_name)
            except Exception as e:
                logging.debug(e)
                remove_channel(channel.name)
        else:
            remove_channel(channel.name)

# Panels -----------------------------------------------------------------------

def get_panel_id():
    logging.debug("get_panel_id")
    return f"LIGHTDESK_PT_{str(uuid4().hex)}"

def get_panel_index(id):
    logging.debug(f"get_panel_index {id}")
    panels = bpy.context.window_manager.lightdesk.panels
    return panels.find(id)

def register_panel(id):
    logging.debug(f"register_panel {id}")
    panel = type(id, (LIGHTDESK_PT_channel, Panel, ), {"bl_idname" : id,})
    register_class(panel)

def unregister_panel(id):
    logging.debug(f"unregister_panel {id}")
    class_path = f"bpy.types.{id}"
    cls = eval(class_path)
    unregister_class(cls)

def add_panel(id):
    logging.debug(f"add_panel {id}")
    panels = bpy.context.window_manager.lightdesk.panels
    if get_panel_index(id) < 0:
        panel = panels.add()
        panel.name = id
        register_panel(id)

def remove_panel(id):
    logging.debug(f"remove_panel {id}")
    panels = bpy.context.window_manager.lightdesk.panels
    index = get_panel_index(id)
    if index >= 0:
        unregister_panel(id)
        panels.remove(index)

def fill_panels():
    logging.debug("fill_panels")
    panels = bpy.context.window_manager.lightdesk.panels
    for panel in panels:
        add_panel(panel.name)

def purge_panels():
    logging.debug("purge_panels")
    panels = bpy.context.window_manager.lightdesk.panels
    for panel in reversed(panels):
        remove_panel(panel.name)

def rebuild_ui():
    logging.debug("rebuild_ui")
    purge_panels()
    panels = bpy.context.window_manager.lightdesk.panels
    channels = bpy.context.scene.lightdesk.channels
    for channel in channels:
        panel = panels.add()
        panel.name = channel.name
    fill_panels()

# Operators ====================================================================

class LIGHTDESK_OT_debug_data(Operator):
    bl_idname = "lightdesk.debug_data"
    bl_label = "Output debug data to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        debug_data()
        return{'FINISHED'}

class LIGHTDESK_OT_get_lights(Operator):
    bl_idname = "lightdesk.get_lights"
    bl_label = "Get lights in scene"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        get_lights()
        filter_lights()
        return{'FINISHED'}

class LIGHTDESK_OT_add_light(Operator):
    bl_idname = "lightdesk.add_light"
    bl_label = "Add selected light"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.scene.lightdesk.selected > -1

    def execute(self, context):
        logging.debug("")
        lightdesk = context.scene.lightdesk
        add_light(lightdesk.filtered[lightdesk.selected].object)
        return {'FINISHED'}

class LIGHTDESK_OT_add_all_lights(Operator):
    bl_idname = "lightdesk.add_all_lights"
    bl_label = "Add all displayed lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.filtered))

    def execute(self, context):
        logging.debug("")
        add_all_lights()
        return {'FINISHED'}

class LIGHTDESK_OT_delete_channel(Operator):
    bl_idname = "lightdesk.delete_channel"
    bl_label = "Delete light channel"
    bl_options = {'INTERNAL'}

    channel: StringProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        delete_channel(self.channel)
        return {'FINISHED'}

class LIGHTDESK_OT_delete_all_channels(Operator):
    bl_idname = "lightdesk.delete_all_channels"
    bl_label = "Delete all channels"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.channels))

    def execute(self, context):
        logging.debug("")
        delete_all_channels()
        return {'FINISHED'}

# UI ===========================================================================

class LIGHTDESK_UL_lights(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        layout.label(text = item.name)

class LIGHTDESK_PT_lights(Panel):
    bl_idname = 'LIGHTDESK_PT_lights'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = 'Lightdesk'
    bl_context = 'objectmode'
    bl_label = "Scene Lights"

    @classmethod
    def poll(cls, context):
        if scene_changed() and not bpy.app.timers.is_registered(rebuild_ui):
            bpy.app.timers.register(rebuild_ui)
        return bpy.context.scene.lightdesk

    def draw(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout
        if logging.getLevelName(logging.root.level) == 'DEBUG':
            row = layout.row()
            row.operator("lightdesk.get_lights", text="Refresh")
            row.operator("lightdesk.debug_data", text="Debug")
        row = layout.row(align = True)
        row.prop(lightdesk, "list_area", toggle = True, text = "Area" )
        row.prop(lightdesk, "list_point", toggle = True, text = "Point" )
        row.prop(lightdesk, "list_spot", toggle = True, text = "Spot" )
        row.prop(lightdesk, "list_sun", toggle = True, text = "Sun" )
        row = layout.row()
        row.template_list("LIGHTDESK_UL_lights", "", lightdesk, "filtered", lightdesk, "selected", rows = 2, maxrows = 5, type = 'DEFAULT')
        row = layout.row()
        row.operator("lightdesk.add_light", text="Add")
        row.operator("lightdesk.add_all_lights", text="Add All")
        row.operator("lightdesk.delete_all_channels", text="Delete All")

class LIGHTDESK_PT_channel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Lightdesk'
    bl_context = 'objectmode'
    bl_idname = "LIGHTDESK_PT_channel"
    bl_options = {'HEADER_LAYOUT_EXPAND'}
    bl_label = ""

    @classmethod
    def poll(cls, context):
        global tracked_scene
        return bpy.context.scene == tracked_scene

    def draw_header(self, context):
        lightdesk = bpy.context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split(factor = 0.85)
        split.label(text = lightdesk.channels[self.bl_idname].object.name)
        op = split.operator("lightdesk.delete_channel", icon = 'X', text = "", emboss = False)
        split = split.split()
        op.channel = str(self.bl_idname)

    def draw(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split(factor = 0.25, align = True)
        split.prop(lightdesk.channels[self.bl_idname].object, "hide_viewport", icon_only = True, emboss = False)
        split.prop(lightdesk.channels[self.bl_idname].object, "hide_render", icon_only = True, emboss = False)
        split = row.split(factor = 0.85)
        split.prop(lightdesk.channels[self.bl_idname].object.data, "energy", text = "")
        split = split.split()
        split.prop(lightdesk.channels[self.bl_idname].object.data, "color", text = "")

# Properties ===================================================================

class LIGHTDESK_PG_object(PropertyGroup):
    name : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_scene(PropertyGroup):
    list_area : BoolProperty(default = True, update = update_filters)
    list_point : BoolProperty(default = True, update = update_filters)
    list_spot : BoolProperty(default = True, update = update_filters)
    list_sun : BoolProperty(default = True, update = update_filters)
    lights : CollectionProperty(type = LIGHTDESK_PG_object)
    filtered : CollectionProperty(type = LIGHTDESK_PG_object)
    selected : IntProperty(default = -1)
    channels : CollectionProperty(type = LIGHTDESK_PG_object)

class LIGHTDESK_PG_ui(PropertyGroup):
    panels : CollectionProperty(type = LIGHTDESK_PG_object)

# Registration =================================================================


classes = [
            LIGHTDESK_OT_debug_data,
            LIGHTDESK_OT_get_lights,
            LIGHTDESK_OT_add_light,
            LIGHTDESK_OT_add_all_lights,
            LIGHTDESK_OT_delete_channel,
            LIGHTDESK_OT_delete_all_channels,
            LIGHTDESK_PG_object,
            LIGHTDESK_PG_scene,
            LIGHTDESK_PG_ui,
            LIGHTDESK_UL_lights,
            LIGHTDESK_PT_lights,
            ]

def register():
    logging.debug("register")
    for cls in classes:
        register_class(cls)
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_scene)
    bpy.types.WindowManager.lightdesk = PointerProperty(type = LIGHTDESK_PG_ui)
    startup()

def unregister():
    logging.debug("unregister")
    shutdown()
    for cls in reversed(classes):
        unregister_class(cls)
    del bpy.types.Scene.lightdesk
