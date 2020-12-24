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
    "description": "Control multiple scene lights from a Lightdesk panel in the 3D view",
    "author": "Quentin Walker",
    "blender": (2, 80, 0),
    "version": (0, 2, 3),
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

logging.basicConfig(level = logging.ERROR)

light_types = ['AREA', 'POINT', 'SPOT', 'SUN']
exec_queue = queue.SimpleQueue()
tracked_scene = object()

# Core -------------------------------------------------------------------------

def startup():
    logging.debug("startup")
    try:
        append_exec_queue(update_lights)
        append_exec_queue(update_filtered)
        append_exec_queue(track_scene)
        append_exec_queue(deadhead_panels)
        append_exec_queue(deadhead_channels)
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
    rebuild_panels()

@persistent
def depsgraph_update_post(scene):
    logging.debug(f"depsgraph_update_post {scene}")
    refresh_lights_on_update()
    rebuild_on_scene_change()

def append_exec_queue(function):
    logging.debug(f"append_exec_queue {function}")
    exec_queue.put(function)

def exec_queued():
    while not exec_queue.empty():
        function = exec_queue.get()
        logging.debug(f"exec_queued {function}")
        function()
    return 1.0

def debug_data():
    global tracked_scene
    logging.debug("----------------------------------------")
    logging.debug(f"Current scene: {tracked_scene.name}")
    ui_props = bpy.context.window_manager.lightdesk
    logging.debug(f"{len(ui_props.panels)} panels:")
    if len(ui_props.panels):
        for panel in ui_props.panels:
            logging.debug(f"- {panel.name}")
    for scene in bpy.data.scenes:
        scene_props = scene.lightdesk
        logging.debug(f".......... {scene.name} ..........")
        logging.debug(f"Lights: {scene_props.lights.keys()}")
        logging.debug(f"Filtered: {scene_props.filtered.keys()}")
        logging.debug(f"Selected: {scene_props.selected}")
        logging.debug(f"{len(scene_props.channels)} channels:")
        if len(scene_props.channels):
            for channel in scene_props.channels:
                logging.debug(f"- {channel.name}, {channel.object.name}")
    logging.debug("----------------------------------------")

# Tracking ---------------------------------------------------------------------

def track_scene():
    global tracked_scene
    tracked_scene = bpy.context.scene
    logging.debug(f"track_scene {tracked_scene.name}")

def has_scene_changed():
    global tracked_scene
    changed = False
    try:
        changed = tracked_scene != bpy.context.scene
    except InvalidReference:
        changed = True
    if changed:
        logging.debug(f"has_scene_changed")
    return changed

def have_objects_changed():
    return len(bpy.context.scene.objects) != bpy.context.scene.lightdesk.objects

# Lights -----------------------------------------------------------------------

def is_context_object_light():
    is_light = False
    if bpy.context.object:
        is_light = bpy.context.object.type == 'LIGHT'
    return is_light

def refresh_lights_on_update():
    if is_context_object_light() or have_objects_changed():
        refresh_lights()
        if not bpy.app.timers.is_registered(deadhead_channels):
            bpy.app.timers.register(deadhead_channels)
        bpy.context.scene.lightdesk.objects = len(bpy.context.scene.objects)

def does_light_exist(light_name):
    return bpy.context.scene.objects.find(light_name) >= 0

def get_light_index(light_name):
    return bpy.context.scene.lightdesk.filtered.find(light_name)

def update_lights():
    logging.debug("update_lights")
    lightdesk = bpy.context.scene.lightdesk
    lightdesk.lights.clear()
    lights = [object for object in bpy.context.scene.objects if object.type == 'LIGHT']
    for light in lights:
        collect_light(light, lightdesk.lights)

def update_filtered():
    logging.debug("update_filtered")
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

def update_listbox():
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected >= 0:
        if lightdesk.selected < len(lightdesk.filtered):
            current_selection = lightdesk.filtered[lightdesk.selected].name
        else:
            lightdesk.selected = -1
    update_filtered()
    if lightdesk.selected >= 0:
        lightdesk.selected = get_light_index(current_selection)

def refresh_lights():
    update_lights()
    update_listbox()

def apply_filters(self, context):
    logging.debug("apply_filters")
    update_listbox()

def collect_light(object, collection):
    logging.debug(f"collect_light {object.name} {collection}")
    light = collection.add()
    light.name = object.name
    light.object = object

def get_selected_light():
    logging.debug("get_scelected_light")
    lightdesk = bpy.context.scene.lightdesk
    return lightdesk.filtered[lightdesk.selected].object

def assign_light(light):
    logging.debug(f"assign_light {light.name}")
    if not get_channel(light):
        create_channel(light)

def add_selected_light():
    logging.debug("add_selected_light")
    light = get_selected_light()
    assign_light(light)

def fill_lights():
    logging.debug("fill_lights")
    for light in bpy.context.scene.lightdesk.filtered:
        assign_light(light.object)

# Channels ---------------------------------------------------------------------

def get_channel(light):
    channels = bpy.context.scene.lightdesk.channels
    for channel in channels:
        if channel.object == light:
            return channel.name
    return None

def get_channel_index(channel_name):
    channels = bpy.context.scene.lightdesk.channels
    return channels.find(channel_name)

def add_channel(channel_name, light):
    logging.debug(f"add_channel {channel_name} {light}")
    channels = bpy.context.scene.lightdesk.channels
    if get_channel_index(channel_name) < 0:
        channel = channels.add()
        channel.name = channel_name
        channel.object = light

def create_channel(light):
    logging.debug(f"create_channel {light}")
    if not get_channel(light):
        channel_name = get_channel_name()
        add_channel(channel_name, light)
        add_panel(channel_name, light)

def pop_channel(channel_name):
    logging.debug(f"pop_channel {channel_name}")
    channels = bpy.context.scene.lightdesk.channels
    index = get_channel_index(channel_name)
    if index >= 0:
        channel = channels.remove(index)

def kill_channel(channel_name):
    logging.debug(f"kill_channel {channel_name}")
    detach_panel(channel_name)
    pop_channel(channel_name)

def purge_channels():
    logging.debug("purge_channels")
    channels = bpy.context.scene.lightdesk.channels
    for channel in reversed(channels):
        kill_channel(channel.name)

def deadhead_channels():
    logging.debug("deadhead_channels")
    channels = bpy.context.scene.lightdesk.channels
    for channel in reversed(channels):
        if channel.name:
            try:
                class_path = f"bpy.types.{channel.name}"
                panel_class = eval(class_path)
                if not does_light_exist(channel.object.name):
                    kill_channel(channel.name)
            except Exception as e:
                logging.error(e)
                kill_channel(channel.name)
        else:
            logging.warning("deadhead_channels: invalid channel name")
            kill_channel(channel.name)

# Panels -----------------------------------------------------------------------

def rebuild_on_scene_change():
    if has_scene_changed():
        rebuild_ui()

def get_channel_name():
    logging.debug("get_channel_name")
    return f"LIGHTDESK_PT_{str(uuid4().hex)}"

def get_panel_index(panel_name):
    logging.debug(f"get_panel_index {panel_name}")
    panels = bpy.context.window_manager.lightdesk.panels
    return panels.find(panel_name)

def register_panel(panel_name):
    logging.debug(f"register_panel {panel_name}")
    panel = type(panel_name, (LIGHTDESK_PT_channel, Panel, ), {"bl_idname" : panel_name,})
    register_class(panel)

def unregister_panel(panel_name):
    logging.debug(f"unregister_panel {panel_name}")
    class_path = f"bpy.types.{panel_name}"
    try:
        panel_class = eval(class_path)
    except Exception as e:
        logging.error(e)
    else:
        unregister_class(panel_class)

def add_panel(panel_name, light):
    logging.debug(f"add_panel {panel_name} {light}")
    panels = bpy.context.window_manager.lightdesk.panels
    if get_panel_index(panel_name) < 0:
        panel = panels.add()
        panel.name = panel_name
        panel.object = light
        register_panel(panel_name)

def detach_panel(panel_name):
    logging.debug(f"detach_panel {panel_name}")
    panels = bpy.context.window_manager.lightdesk.panels
    index = get_panel_index(panel_name)
    if index >= 0:
        unregister_panel(panel_name)
        panels.remove(index)

def rebuild_panels():
    logging.debug("rebuild_panels")
    panels = bpy.context.window_manager.lightdesk.panels
    for panel in panels:
        register_panel(panel.name)

def purge_panels():
    logging.debug("purge_panels")
    panels = bpy.context.window_manager.lightdesk.panels
    for panel in reversed(panels):
        detach_panel(panel.name)

def deadhead_panels():
    logging.debug("deadhead_panels")
    panels = bpy.context.window_manager.lightdesk.panels
    for panel in reversed(panels):
        if panel.name:
            try:
                class_path = f"bpy.types.{panel.name}"
                cls = eval(class_path)
            except Exception as e:
                logging.error(e)
                detach_panel(panel.name)
                pop_channel(panel.name)
        else:
            logging.warning(f"deadhead_panels: invalid panel name")
            detach_panel(panel.name)
            pop_channel(panel.name)

def rebuild_ui():
    logging.debug("rebuild_ui")
    purge_panels()
    panels = bpy.context.window_manager.lightdesk.panels
    channels = bpy.context.scene.lightdesk.channels
    for channel in channels:
        panel = panels.add()
        panel.name = channel.name
    rebuild_panels()
    track_scene()

# Operators ====================================================================

class LIGHTDESK_OT_debug(Operator):
    bl_idname = "lightdesk.debug"
    bl_label = "Dump debug data to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        debug_data()
        return{'FINISHED'}

class LIGHTDESK_OT_refresh(Operator):
    bl_idname = "lightdesk.refresh"
    bl_label = "Refresh UI"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        refresh_lights()
        rebuild_ui()
        return{'FINISHED'}

class LIGHTDESK_OT_assign_light(Operator):
    bl_idname = "lightdesk.assign_light"
    bl_label = "Assign selected light"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        lightdesk = context.scene.lightdesk
        assigned = False
        if lightdesk.selected >= 0:
            assigned = get_channel(lightdesk.filtered[lightdesk.selected].object)
        return lightdesk.selected >= 0 and not assigned

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        lightdesk = context.scene.lightdesk
        assign_light(lightdesk.filtered[lightdesk.selected].object)
        return {'FINISHED'}

class LIGHTDESK_OT_fill_lights(Operator):
    bl_idname = "lightdesk.fill_lights"
    bl_label = "Add all displayed lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.filtered))

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        fill_lights()
        return {'FINISHED'}

class LIGHTDESK_OT_kill_channel(Operator):
    bl_idname = "lightdesk.kill_channel"
    bl_label = "Delete light channel"
    bl_options = {'INTERNAL'}

    channel: StringProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        kill_channel(self.channel)
        return {'FINISHED'}

class LIGHTDESK_OT_purge_channels(Operator):
    bl_idname = "lightdesk.purge_channels"
    bl_label = "Delete all channels"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.channels))

    def execute(self, context):
        logging.debug("")
        logging.debug(f"OPERATOR {self}")
        purge_channels()
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
        if has_scene_changed() and not bpy.app.timers.is_registered(rebuild_ui):
            bpy.app.timers.register(rebuild_ui)
        return bpy.context.scene.lightdesk

    def draw(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout
        if logging.getLevelName(logging.root.level) == 'DEBUG':
            row = layout.row()
            row.operator("lightdesk.debug", text="Debug")
            row.operator("lightdesk.refresh", text="Refresh")
        row = layout.row(align = True)
        row.prop(lightdesk, "list_area", toggle = True, text = "Area" )
        row.prop(lightdesk, "list_point", toggle = True, text = "Point" )
        row.prop(lightdesk, "list_spot", toggle = True, text = "Spot" )
        row.prop(lightdesk, "list_sun", toggle = True, text = "Sun" )
        row = layout.row()
        row.template_list("LIGHTDESK_UL_lights", "", lightdesk, "filtered", lightdesk, "selected", rows = 2, maxrows = 5, type = 'DEFAULT')
        row = layout.row()
        row.operator("lightdesk.assign_light", text="Add")
        row.operator("lightdesk.fill_lights", text="Fill")
        row.operator("lightdesk.purge_channels", text="Clear")

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
        return not has_scene_changed()

    def draw_header(self, context):
        lightdesk = bpy.context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split(factor = 0.85)
        split.label(text = lightdesk.channels[self.bl_idname].object.name)
        op = split.operator("lightdesk.kill_channel", icon = 'PANEL_CLOSE', text = "", emboss = False)
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
    list_area : BoolProperty(default = True, update = apply_filters)
    list_point : BoolProperty(default = True, update = apply_filters)
    list_spot : BoolProperty(default = True, update = apply_filters)
    list_sun : BoolProperty(default = True, update = apply_filters)
    lights : CollectionProperty(type = LIGHTDESK_PG_object)
    filtered : CollectionProperty(type = LIGHTDESK_PG_object)
    selected : IntProperty(default = -1)
    objects : IntProperty(default = -1)
    channels : CollectionProperty(type = LIGHTDESK_PG_object)

class LIGHTDESK_PG_ui(PropertyGroup):
    panels : CollectionProperty(type = LIGHTDESK_PG_object)

# Registration =================================================================


classes = [
            LIGHTDESK_OT_debug,
            LIGHTDESK_OT_refresh,
            LIGHTDESK_OT_assign_light,
            LIGHTDESK_OT_fill_lights,
            LIGHTDESK_OT_kill_channel,
            LIGHTDESK_OT_purge_channels,
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
