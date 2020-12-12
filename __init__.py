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
    "description": "Control scene lights from a lighting desk panel",
    "author": "Quentin Walker",
    "blender": (2, 80, 0),
    "version": (0, 1, 5),
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

subscription_owner = object()
exec_queue = queue.Queue()
scene_pin = ""

#===============================================================================
# Functions
#===============================================================================

def init():
    add_to_exec_queue(collate_lights)
    add_to_exec_queue(filter_lights)
    bpy.app.timers.register(exec_queued_functions)
    bpy.app.timers.register(check_scene_switch)
    if load_post_handler not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(load_post_handler)


def add_to_exec_queue(function):
    exec_queue.put(function)


def exec_queued_functions():
    while not exec_queue.empty():
        function = exec_queue.get()
        logging.debug(f"* Executing from queue: {function}")
        function()
    return 1.0


@persistent
def load_post_handler(scene):
    logging.debug("*** load_post handler...")
    init()


def check_scene_switch():
    global scene_pin
    if bpy.context.scene.name != scene_pin:
        if len(scene_pin):
            logging.debug(f"* Scene changed to {bpy.context.scene.name}")
            delete_scene_panels(scene_pin)
            collate_lights()
            filter_lights()
            validate_tracking()
            create_scene_panels(bpy.context.scene.name)
        scene_pin = bpy.context.scene.name
    return 0.25


def log_data():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug("--------------------------------------------------")
    logging.debug(f"{len(lightdesk.lights)} Scene lights:")
    logging.debug(f"- {lightdesk.lights.keys()}")
    logging.debug("....................")
    logging.debug(f"Light filters:")
    logging.debug(f"- AREA : {lightdesk.list_area}")
    logging.debug(f"- POINT : {lightdesk.list_point}")
    logging.debug(f"- SPOT : {lightdesk.list_spot}")
    logging.debug(f"- SUN : {lightdesk.list_sun}")
    logging.debug("....................")
    logging.debug(f"{len(lightdesk.filtered)} Filtered lights:")
    logging.debug(f"- {lightdesk.filtered.keys()}")
    logging.debug(f"- {lightdesk.selected_name} ({lightdesk.selected_index}) selected")
    logging.debug("....................")
    logging.debug(f"{len(lightdesk.channels)} Channels:")
    if len(lightdesk.channels):
        for channel in bpy.context.scene.lightdesk.channels:
            logging.debug(f"- {channel.name}, {channel.object.name}")
    logging.debug("--------------------------------------------------")


def add_light_to_collection(object, collection):
    logging.debug(f"- Adding {object.name} to {collection}")
    lightdesk = bpy.context.scene.lightdesk
    light = collection.add()
    light.name = object.name
    light.object = object


def collate_lights():
    try:
        logging.debug("Collating scene lights...")
        lightdesk = bpy.context.scene.lightdesk
        if len(lightdesk.lights):
            logging.debug("- Clearing existing collection...")
            lightdesk.lights.clear()
        lights = [object for object in bpy.context.scene.objects if object.type == 'LIGHT']
        for light in lights:
            add_light_to_collection(light, lightdesk.lights)
        logging.debug(f"{len(lights)} lights added to collection")
    except Exception as e:
        logging.error(f"*** ERROR *** register_panel: {panel_id}")
        logging.error(e)


def refresh_light_list(self, context):
    collate_lights()
    update_filters(self, context)


def filter_lights():
    logging.debug("Filtering lights...")
    lightdesk = bpy.context.scene.lightdesk
    lightdesk.filtered.clear()
    for light in lightdesk.lights:
        if light.object.data.type == 'AREA':
            if lightdesk.list_area:
                add_light_to_collection(light.object, lightdesk.filtered)
        elif light.object.data.type == 'POINT':
            if lightdesk.list_point:
                add_light_to_collection(light.object, lightdesk.filtered)
        elif light.object.data.type == 'SPOT':
            if lightdesk.list_spot:
                add_light_to_collection(light.object, lightdesk.filtered)
        elif light.object.data.type == 'SUN':
            if lightdesk.list_sun:
                add_light_to_collection(light.object, lightdesk.filtered)


def update_filters(self, context):
    logging.debug("Updating light filters...")
    filter_lights()
    validate_tracking()


def get_channel(light_name):
    logging.debug(f"- Checking for existing channel for {light_name}...")
    lightdesk = bpy.context.scene.lightdesk
    for channel in lightdesk.channels:
        if channel.object.name == light_name:
            logging.debug(f"- Channel found {channel.name}")
            return True
    logging.debug(f"- No channel found")
    return False


def update_tracking(self, context):
    logging.debug("- Updating tracking...")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1 and lightdesk.selected_index <= len(lightdesk.filtered) - 1:
        lightdesk.selected_name = lightdesk.filtered[lightdesk.selected_index].name
        logging.debug(f"{lightdesk.selected_name} selected")


def validate_tracking():
    logging.debug("- Validating selection tracking...")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1:
        lookup = lightdesk.filtered.find(lightdesk.selected_name)
        if lookup > -1:
            logging.debug(f"{lightdesk.selected_name} found in filtered collection")
            lightdesk.selected_index = lookup
        else:
            logging.debug(f"{lightdesk.selected_name} not found in filtered collection, trackers reset")
            lightdesk.selected_index = -1
            lightdesk.selected_name = ""


def get_new_panel_id():
    return f"LIGHTDESK_PT_{str(uuid4().hex)}"


def register_panel(panel_id):
    if len(panel_id):
        logging.debug(f"- Registering panel class {panel_id}...")
        panel = type(panel_id, (LIGHTDESK_PT_channel, Panel, ), {"bl_idname" : panel_id,})
        try:
            register_class(panel)
        except Exception as e:
            logging.error(f"*** ERROR *** register_panel: {panel_id}")
            logging.error(e)
    else:
        logging.error("*** ERROR *** register_panel: Missing panel_id")


def unregister_panel(panel_id):
    if len(panel_id):
        logging.debug(f"- Unregistering panel class '{panel_id}'...")
        try:
            class_name = f"bpy.types.{panel_id}"
            cls = eval(class_name)
            unregister_class(cls)
        except Exception as e:
            logging.error(f"*** ERROR *** unregister_panel: {panel_id}")
            logging.error(e)
            deadhead_channels()
    else:
        logging.error("*** ERROR *** unregister_panel: Missing panel_id")


def delete_scene_panels(scene):
    for channel in bpy.data.scenes[scene].lightdesk.channels:
        unregister_panel(channel.name)


def create_scene_panels(scene):
    for channel in bpy.data.scenes[scene].lightdesk.channels:
        register_panel(channel.name)


def add_light_to_channel(light_name):
    lightdesk = bpy.context.scene.lightdesk
    if not get_channel(light_name):
        logging.debug("- Creating channel...")
        try:
            channel = lightdesk.channels.add()
            channel.object = bpy.data.objects[light_name]
            channel.name = get_new_panel_id()
            register_panel(channel.name)
            validate_tracking()
        except Exception as e:
            logging.error(f"*** ERROR *** create_channel: {lightdesk.selected_name} ({channel.name})")
            logging.error(e)
            deadhead_channels()


def add_all_lights():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug(f"Adding {len(lightdesk.filtered)} lights to channels...")
    for light in lightdesk.filtered:
        add_light_to_channel(light.object.name)


def pop_channel(channel_name):
    logging.debug(f"- Popping channel out of collection...")
    lightdesk = bpy.context.scene.lightdesk
    index = lightdesk.channels.find(channel_name)
    if index > -1:
        lightdesk.channels.remove(index)
    else:
        logging.error(f"*** ERROR *** delete_channel: Could not find channel_name '{channel_name}'")
        deadhead_channels()


def delete_channel(channel_name):
    logging.debug(f"Deleting channel {channel_name}...")
    pop_channel(channel_name)
    unregister_panel(channel_name)


def delete_all_channels():
    logging.debug(f"Deleting {len(bpy.context.scene.lightdesk.channels)} channels:")
    lightdesk = bpy.context.scene.lightdesk
    for channel in reversed(lightdesk.channels):
        delete_channel(channel.name)


def deadhead_channels():
    lightdesk = bpy.context.scene.lightdesk
    if len(lightdesk.channels):
        logging.debug(f"Verifying {len(lightdesk.channels)} channels...")
        for channel in lightdesk.channels:
            if len(channel.name): # check panel class exists for channel.name, otherwise pop channel
                try:
                    class_name = f"bpy.types.{channel.name}"
                    cls = eval(class_name)
                    logging.debug(f"- class {class_name} OK")
                except Exception as e:
                    logging.warning(f"*** WARNING *** class {class_name} does not exist, deleting channel...")
                    pop_channel(channel.name)
            else: # if channel.name is empty, pop channel
                    logging.warning(f"*** WARNING *** channel.name does not exist, deleting channel...")
                    pop_channel(channel.name)


#===============================================================================
# Operators
#===============================================================================

class LIGHTDESK_OT_log_data(Operator):
    bl_idname = "lightdesk.log_data"
    bl_label = "Output debug information to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        log_data()
        return{'FINISHED'}


class LIGHTDESK_OT_refresh_light_list(Operator):
    bl_idname = "lightdesk.refresh_light_list"
    bl_label = "Get list of scene lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk
        refresh_light_list(self, context)
        return{'FINISHED'}


class LIGHTDESK_OT_add_selected_light(Operator):
    bl_idname = "lightdesk.add_selected_light"
    bl_label = "Add selected light to lightdesk"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.scene.lightdesk.selected_index > -1

    def execute(self, context):
        add_light_to_channel(context.scene.lightdesk.selected_name)
        return {'FINISHED'}


class LIGHTDESK_OT_add_all_lights(Operator):
    bl_idname = "lightdesk.add_all_lights"
    bl_label = "Add all scene lights to lightdesk"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.filtered))

    def execute(self, context):
        add_all_lights()
        return {'FINISHED'}


class LIGHTDESK_OT_delete_channel(Operator):
    bl_idname = "lightdesk.delete_channel"
    bl_label = "delete selected light channel"
    bl_options = {'INTERNAL'}

    channel_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        delete_channel(self.channel_name)
        return {'FINISHED'}


class LIGHTDESK_OT_delete_all_channels(Operator):
    bl_idname = "lightdesk.delete_all_channels"
    bl_label = "Delete all current light channels"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.channels))

    def execute(self, context):
        delete_all_channels()
        return {'FINISHED'}


#===============================================================================
# UI
#===============================================================================

class LIGHTDESK_UL_lights(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        lightdesk = bpy.context.scene.lightdesk
        light_icon = "LIGHT_{}".format((lightdesk.filtered[index].object.data.type).upper())
        layout.label(text = item.name, icon = light_icon)

    def invoke(self, context, event):
        pass


class LIGHTDESK_PT_lights(Panel):
    bl_idname = 'LIGHTDESK_PT_lights'
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = 'Lightdesk'
    bl_context = 'objectmode'
    bl_label = "Scene Lights"

    def draw(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout
        if logging.getLevelName(logging.root.level) == 'DEBUG':
            row = layout.row()
            row.operator("lightdesk.refresh_light_list", text="Populate")
            row.operator("lightdesk.log_data", text="Debug")
        row = layout.row(align = True)
        row.prop(lightdesk, "list_area", toggle = True, text = "Area" )
        row.prop(lightdesk, "list_point", toggle = True, text = "Point" )
        row.prop(lightdesk, "list_spot", toggle = True, text = "Spot" )
        row.prop(lightdesk, "list_sun", toggle = True, text = "Sun" )
        row = layout.row()
        row.template_list("LIGHTDESK_UL_lights", "", lightdesk, "filtered", lightdesk, "selected_index", rows = 2, maxrows = 5, type = 'DEFAULT')
        row = layout.row()
        row.operator("lightdesk.add_selected_light", text="Add Selected", emboss = lightdesk.selected_index > -1)
        row.operator("lightdesk.add_all_lights", text="Add All")
        row = layout.row()
        row.operator("lightdesk.delete_all_channels", text="Delete All Channels")


class LIGHTDESK_PT_channel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Lightdesk'
    bl_context = 'objectmode'
    bl_idname = "LIGHTDESK_PT_channel"
    bl_options = {'HEADER_LAYOUT_EXPAND'}
    bl_label = ""

    def draw_header(self, context):
        try:
            lightdesk = bpy.context.scene.lightdesk
            layout = self.layout
            row = layout.row()
            split = row.split(factor = 0.15)
            split.label(text = "", icon = f"LIGHT_{lightdesk.channels[self.bl_idname].object.data.type}")
            split = split.split(factor = 0.8)
            split.label(text = lightdesk.channels[self.bl_idname].object.name)
            op = split.operator("lightdesk.delete_channel", icon = 'X', text = "", emboss = False)
            split = split.split()
            op.channel_name = str(self.bl_idname)
        except Exception as e:
            pass

    def draw(self, context):
        try:
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
        except Exception as e:
            pass

#===============================================================================
# Properties
#===============================================================================

class LIGHTDESK_PG_light(PropertyGroup):
    name : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_channel(PropertyGroup):
    name : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_properties(PropertyGroup):
    init : BoolProperty(default = False)
    list_area : BoolProperty(default = True, update = update_filters)
    list_point : BoolProperty(default = True, update = update_filters)
    list_spot : BoolProperty(default = True, update = update_filters)
    list_sun : BoolProperty(default = True, update = update_filters)
    lights : CollectionProperty(type = LIGHTDESK_PG_light)
    filtered : CollectionProperty(type = LIGHTDESK_PG_light)
    channels : CollectionProperty(type = LIGHTDESK_PG_channel)
    selected_index : IntProperty(default = -1, update = update_tracking)
    selected_name : StringProperty()


#===============================================================================
# Registration
#===============================================================================


classes = [
            LIGHTDESK_OT_log_data,
            LIGHTDESK_OT_refresh_light_list,
            LIGHTDESK_OT_add_selected_light,
            LIGHTDESK_OT_add_all_lights,
            LIGHTDESK_OT_delete_channel,
            LIGHTDESK_OT_delete_all_channels,
            LIGHTDESK_PG_light,
            LIGHTDESK_PG_channel,
            LIGHTDESK_PG_properties,
            LIGHTDESK_UL_lights,
            LIGHTDESK_PT_lights,
            ]


def register():
    # register main classes
    logging.debug("--------------------------------------------------")
    logging.debug("Add-on activated, registering classes...")
    for cls in classes:
        logging.debug(f"- {cls}")
        register_class(cls)
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_properties)
    init()



def unregister():
    logging.debug("--------------------------------------------------")
    logging.debug("Add-on deactivated, deregistering channels...")
    lightdesk = bpy.context.scene.lightdesk
    logging.debug(f"{len(lightdesk.channels)} channels:")
    if len(lightdesk.channels):
        for channel in lightdesk.channels:
            unregister_panel(channel.name)
    lightdesk.channels.clear()
    logging.debug(f"Unregistering {len(classes)} main classes:")
    for cls in reversed(classes):
        logging.debug(f"- {cls}")
        try:
            unregister_class(cls)
        except Exception as e:
            logging.error(f"*** ERROR *** Could not unregister {class_id}")
            logging.error(e)
    logging.debug("Unregistering timers...")
    if bpy.app.timers.is_registered(exec_queued_functions):
        bpy.app.timers.unregister(exec_queued_functions)
    if bpy.app.timers.is_registered(check_scene_switch):
        bpy.app.timers.unregister(check_scene_switch)
    logging.debug("Unregistering handlers...")
    if load_post_handler in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(load_post_handler)
    del bpy.types.Scene.lightdesk
    logging.debug("He's dead, Jim!")
