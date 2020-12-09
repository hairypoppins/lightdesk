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
    "version": (0, 1, 4),
    "category": "Lighting",
    "location": "",
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

logging.basicConfig(level = logging.DEBUG)

light_types = ['AREA', 'POINT', 'SPOT', 'SUN']

#===============================================================================
# Functions
#===============================================================================

@persistent
def init(scene):
    logging.debug("###########################################################")
    logging.debug("LIGHTDESK INIT ############################################")
    logging.debug("###########################################################")
    bpy.app.handlers.load_post.remove(init)


def output_debug():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug("--------------------------------------------------")
    logging.debug(f"{len(lightdesk.lights)} Scene lights:")
    logging.debug(f"- {lightdesk.lights.keys()}")
    logging.debug("....................")
    logging.debug(f"Light filters:")
    logging.debug(f"list_area : {lightdesk.list_area}")
    logging.debug(f"list_point : {lightdesk.list_point}")
    logging.debug(f"list_spot : {lightdesk.list_spot}")
    logging.debug(f"list_sun : {lightdesk.list_sun}")
    logging.debug("....................")
    logging.debug(f"{len(lightdesk.filtered)} Filtered lights:")
    logging.debug(f"- {lightdesk.filtered.keys()}")
    logging.debug(f"- {lightdesk.selected_name} ({lightdesk.selected_index}) selected")
    logging.debug("....................")
    logging.debug(f"{len(lightdesk.channels)} Channels:")
    for channel in bpy.context.scene.lightdesk.channels:
        logging.debug(f"- {channel.name}, {channel.object.name}")
    logging.debug("--------------------------------------------------")
    return{'FINSHED'}


def get_lights(self, context):
    logging.debug("Getting scene lights...")
    lightdesk = context.scene.lightdesk
    if len(lightdesk.lights):
        logging.debug("Clearing existing light collection...")
        bpy.context.scene.lightdesk.lights.clear()
    lights = [object for object in context.scene.objects if object.type == 'LIGHT']
    for light in lights:
        add_light_to_collection(light, lightdesk.lights)
    logging.debug(f"{len(lights)} lights added to collection")
    filter_lights(self, context)


def filter_lights(self, context):
    logging.debug("Filtering lights...")
    lightdesk = context.scene.lightdesk
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
    validate_tracking()


def add_light_to_collection(object, collection):
    logging.debug(f"Adding {object.name} to {collection}")
    lightdesk = bpy.context.scene.lightdesk
    light = collection.add()
    light.name = object.name
    light.object = object


def get_light_channel(light_name):
    logging.debug(f"Looking for existing channel for {light_name}...")
    lightdesk = bpy.context.scene.lightdesk
    for channel in lightdesk.channels:
        if channel.object.name == light_name:
            logging.debug(f"Channel found: {channel.name}")
            return True
    logging.debug(f"No channel found")
    return False


def update_tracking(self, context):
    logging.debug("Updating tracking...")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1 and lightdesk.selected_index <= len(lightdesk.filtered) - 1:
        lightdesk.selected_name = lightdesk.filtered[lightdesk.selected_index].name
        lightdesk.selected_channel = get_light_channel(lightdesk.selected_name)
        logging.debug(f"{lightdesk.selected_name} selected")


def validate_tracking():
    logging.debug("Validating selection tracking...")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1:
        lookup = lightdesk.filtered.find(lightdesk.selected_name)
        if lookup > -1:
            logging.debug(f"{lightdesk.selected_name} found in light collection")
            lightdesk.selected_index = lookup
            lightdesk.selected_channel = get_light_channel(lightdesk.selected_name)
        else:
            logging.debug(f"{lightdesk.selected_name} not found in light collection, trackers reset")
            lightdesk.selected_index = -1
            lightdesk.selected_name = ""
            lightdesk.selected_channel = False


def register_panel_class():
    class_id = f"LIGHTDESK_PT_{str(uuid4().hex)}"
    logging.debug(f"Registering panel class {class_id}...")
    panel = type(class_id, (LIGHTDESK_PT_channel, Panel, ), {"bl_idname" : class_id,})
    try:
        register_class(panel)
        return class_id
    except Exception as e:
        logging.error(f"***ERROR*** register_panel_class: {class_id}")
        logging.error(e)


def unregister_panel_class(channel_name):
    if len(channel_name):
        logging.debug(f"Unregistering panel class '{channel_name}'...")
        try:
            class_name = f"bpy.types.{channel_name}"
            cls = eval(class_name)
            unregister_class(cls)
        except Exception as e:
            logging.error(f"***ERROR*** unregister_panel_class: {channel_name}")
            logging.error(e)
    else:
        logging.error("***ERROR*** unregister_panel_class: Missing channel_name")


def add_light_to_channel(light_name):
    lightdesk = bpy.context.scene.lightdesk
    if not get_light_channel(light_name):
        logging.debug("Creating channel...")
        try:
            channel = lightdesk.channels.add()
            channel.object = bpy.data.objects[light_name]
            channel.name = register_panel_class()
            validate_tracking()
        except Exception as e:
            logging.error(f"***ERROR*** create_channel: {lightdesk.selected_name} ({channel.name})")
            logging.error(e)


def add_all_lights_to_channels():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug(f"Adding {len(lightdesk.filtered)} lights to channels...")
    for light in lightdesk.filtered:
        add_light_to_channel(light.object.name)


def delete_channel(channel_name):
    logging.debug(f"Deleting channel '{channel_name}'")
    lightdesk = bpy.context.scene.lightdesk
    index = lightdesk.channels.find(channel_name)
    if index > -1:
        try:
            unregister_panel_class(channel_name)
            lightdesk.channels.remove(index)
            #validate_tracking()
        except Exception as e:
            logging.error(e)
    else:
        logging.error(f"***ERROR*** delete_channel: Could not find channel_name '{channel_name}'")


def delete_all_channels():
    logging.debug(f"Deleting {len(bpy.context.scene.lightdesk.channels)} channels:")
    lightdesk = bpy.context.scene.lightdesk
    for channel in reversed(lightdesk.channels):
        delete_channel(channel.name)


#===============================================================================
# Operators
#===============================================================================

class LIGHTDESK_OT_output_debug(Operator):
    bl_idname = "lightdesk.output_debug"
    bl_label = "Output debug information to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        output_debug()
        return{'FINISHED'}


class LIGHTDESK_OT_get_lights(Operator):
    bl_idname = "lightdesk.get_lights"
    bl_label = "Get list of scene lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk
        get_lights(self, context)
        return{'FINISHED'}


class LIGHTDESK_OT_add_selected_light(Operator):
    bl_idname = "lightdesk.add_selected_light"
    bl_label = "Add selected light to lightdesk"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return not context.scene.lightdesk.selected_channel

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
        add_all_lights_to_channels()
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
            row.operator("lightdesk.get_lights", text="Get Lights")
            row.operator("lightdesk.output_debug", text="Output Debug")
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
        lightdesk = context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split(factor = 0.15)
        split.label(text = "", icon = f"LIGHT_{lightdesk.channels[self.bl_idname].object.data.type}")
        split = split.split(factor = 0.8)
        split.prop(lightdesk.channels[self.bl_idname].object, "name", text = "")
        op = split.operator("lightdesk.delete_channel", icon = 'X', text = "", emboss = False)
        split = split.split()
        op.channel_name = str(self.bl_idname)

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
    list_area : BoolProperty(default = True, update = filter_lights)
    list_point : BoolProperty(default = True, update = filter_lights)
    list_spot : BoolProperty(default = True, update = filter_lights)
    list_sun : BoolProperty(default = True, update = filter_lights)
    lights : CollectionProperty(type = LIGHTDESK_PG_light)
    filtered : CollectionProperty(type = LIGHTDESK_PG_light)
    channels : CollectionProperty(type = LIGHTDESK_PG_channel)
    selected_index : IntProperty(default = -1, update = update_tracking)
    selected_name : StringProperty()
    selected_channel : BoolProperty(default = False)


#===============================================================================
# Init
#===============================================================================


classes = [
            LIGHTDESK_OT_output_debug,
            LIGHTDESK_OT_get_lights,
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
    logging.debug("Activated, registering components...")
    logging.debug(f"Registering {len(classes)} main classes...")
    for cls in classes:
        logging.debug(f"- {cls}")
        register_class(cls)
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_properties)
    bpy.app.handlers.load_post.append(init)

def unregister():
    logging.debug("--------------------------------------------------")
    logging.debug("Deactivated, unregistering components...")
    lightdesk = bpy.context.scene.lightdesk
    if len(lightdesk.channels):
        logging.debug(f"{len(lightdesk.channels)} panel classes:")
        for channel in lightdesk.channels:
            if channel.name:
                unregister_panel_class(channel.name)
            else:
                logging.warning(f"***ERROR*** Channel {channel.object.name} has no panel_class, skipping")
    else:
        logging.debug("No panel classes registered")
    logging.debug(f"Unregistering {len(classes)} main classes:")
    for cls in reversed(classes):
        logging.debug(f"- {cls}")
        try:
            unregister_class(cls)
        except Exception as e:
            logging.error(f"***ERROR*** Could not unregister {class_id}")
            logging.error(e)
            pass
    try:
        index = bpy.app.handlers.depsgraph_update_post.index(init)
    except ValueError:
        pass
    else:
        bpy.app.handlers.load_post.remove(init)
    del bpy.types.Scene.lightdesk
