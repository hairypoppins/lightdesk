'''
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
'''

bl_info = {
    "name": "Lightdesk",
    "description": "Control scene lights from a lighting desk panel",
    "author": "Quentin Walker",
    "blender": (2, 80, 0),
    "version": (0, 1, 2),
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
from uuid import uuid4
import logging

logging.basicConfig(level = logging.DEBUG)


#===============================================================================
# Functions
#===============================================================================


def debug_dump():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug("==================================================")
    logging.debug(f"{len(lightdesk.lights)} Scene lights:")
    for light in bpy.context.scene.lightdesk.lights:
        logging.debug(f"- {light.object.name}")
    logging.debug(f"{lightdesk.selected_name} ({lightdesk.selected_index}) selected")
    logging.debug("..............................")
    logging.debug(f"{len(lightdesk.channels)} Channels (light:panel):")
    for channel in bpy.context.scene.lightdesk.channels:
        logging.debug(f"- {channel.object.name}:{channel.panel_class}")
    logging.debug("..............................")
    logging.debug(f"{len(classes)} Registered classes:")
    for cls in classes:
        logging.debug(f"- {cls}")
    logging.debug("--------------------------------------------------")
    return{'FINSHED'}


def collate_scene_lights(self, context):
    logging.debug("Collating scene lights...")
    scene = bpy.context.scene
    lightdesk = scene.lightdesk
    # clear current scene_lights collection
    logging.debug("- clearing existing collection...")
    if len(lightdesk.lights) > 0:
        bpy.context.scene.lightdesk.lights.clear()
    # find all light objects in scene
    lights = [object for object in scene.objects if object.type == 'LIGHT']
    # check found lights against current type filters, add to scene_lights accordingly
    logging.debug("- adding found lights to collection...")
    for light in lights:
        if light.data.type == 'AREA':
            if lightdesk.show_area:
                add_light_to_collection(light)
        elif light.data.type == 'POINT':
            if lightdesk.show_point:
                add_light_to_collection(light)
        elif light.data.type == 'SPOT':
            if lightdesk.show_spot:
                add_light_to_collection(light)
        elif light.data.type == 'SUN':
            if lightdesk.show_sun:
                add_light_to_collection(light)
        else:
            logging.error(f"Light type {light.data.type} not found in filters")
    # check that previosuly selected item is still in new collection
    logging.debug("- validating UI selection trackers...")
    if lightdesk.selected_index > -1:
        lookup = lightdesk.lights.find(lightdesk.selected_name)
        if lookup > -1:
            logging.debug(f"- {lightdesk.selected_name} found in collection")
            lightdesk.selected_index = lookup
        else:
            logging.debug(f"- {lightdesk.selected_name} not found in collection, trackers reset")
            lightdesk.selected_index = -1
            lightdesk.selected_name = ""


def add_light_to_collection(light):
    logging.debug(f"- adding {light.name} to collection")
    lightdesk = bpy.context.scene.lightdesk
    new_item = lightdesk.lights.add()
    new_item.name = light.name
    new_item.object = light
    return{'FINISHED'}


def update_selection_tracker(self, context):
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1 and lightdesk.selected_index <= len(lightdesk.lights):
        lightdesk.selected_name = lightdesk.lights[lightdesk.selected_index].name
        logging.debug(f"{lightdesk.selected_name} selected")


def register_panel_class():
    pass


def unregister_panel_class(class_name):
    # unregister specified panel class
    if class_name:
        logging.debug(f"Unregistering panel class '{class_name}'...")
        try:
            class_id = f"bpy.types.{class_name}"
            logging.debug(f" ({class_id})")
            cls = eval(class_id)
            unregister_class(cls)
        except Exception as e:
            logging.error(f"! Could not unregister {class_id}")
            logging.error(e)
    else:
        logging.error(f"! unregister_panel_class: Invalid class_name '{class_name}'")


#===============================================================================
# Operators
#===============================================================================

class LIGHTDESK_OT_debug_dump(Operator):
    bl_idname = "lightdesk.debug_dump"
    bl_label = "Dump debug information to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        debug_dump()
        return{'FINISHED'}


class LIGHTDESK_OT_collate_scene_lights(Operator):
    bl_idname = "lightdesk.collate_scene_lights"
    bl_label = "Get list of scene lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk
        collate_scene_lights(self, context)
        debug_dump()
        return{'FINISHED'}


class LIGHTDESK_OT_add_selected_light(Operator):
    bl_idname = "lightdesk.add_selected_light"
    bl_label = "Add selected light to lightdesk"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        # TODO check existing channels to see if selected light already added?
        lightdesk = context.scene.lightdesk
        return bool(lightdesk
                    and lightdesk.selected_index > -1
                    and lightdesk.channels.find(lightdesk.selected_name) < 0)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk

        logging.debug(f"Adding {lightdesk.selected_name} to new channel...")
        class_id = f"LIGHTDESK_PT_{str(uuid4().int)}"
        channel = lightdesk.channels.add()
        channel.object = bpy.data.objects[lightdesk.selected_name]
        channel.panel_class = class_id
        logging.debug(f"Creating panel class {class_id}...")
        panel = type(class_id,
                     (LIGHTDESK_PT_channel, Panel, ),
                     {"bl_idname" : class_id,}
                     )
        register_class(panel)

        return {'FINISHED'}


class LIGHTDESK_OT_add_all_lights(Operator):
    bl_idname = "lightdesk.add_all_lights"
    bl_label = "Add all scene lights to lightdesk"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk
        debug_dump()
        return {'FINISHED'}


class LIGHTDESK_OT_delete_channel(Operator):
    bl_idname = "lightdesk.delete_channel"
    bl_label = "delete selected light channel"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        scene = context.scene
        lightdesk = scene.lightdesk
        # TODO unregister(channel panel)
        logging.debug("Deleting channel {???}...")
        # TODO remove from lightdesk.channels
        debug_dump()
        return {'FINISHED'}



class LIGHTDESK_OT_delete_all_channels(Operator):
    bl_idname = "lightdesk.delete_all_channels"
    bl_label = "Delete all light channels"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        lightdesk = context.scene.lightdesk
        return bool(lightdesk and len(lightdesk.channels) > 0)

    def execute(self, context):
        lightdesk = bpy.context.scene.lightdesk
        if len(lightdesk.channels):
            logging.debug(f"Unregistering {len(lightdesk.channels)} panel classes:")
            for channel in lightdesk.channels:
                if channel.panel_class:
                    unregister_panel_class(channel.panel_class)
                else:
                    logging.warning(f"! Channel {channel.object.name} has no panel_class, skipping")
        else:
            logging.debug("No panel classes registered")
        logging.debug(f"Clearing {len(lightdesk.channels)} channels...")
        lightdesk.channels.clear()
        debug_dump()
        return {'FINISHED'}


#===============================================================================
# UI
#===============================================================================

class LIGHTDESK_UL_lights(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        lightdesk = bpy.context.scene.lightdesk
        # TODO check to see if selected_index valid/within bounds?
        light_icon = "LIGHT_{}".format((lightdesk.lights[index].object.data.type).upper())
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
        scene = context.scene
        lightdesk = scene.lightdesk
        layout = self.layout

        row = layout.row()
        row.operator("lightdesk.debug_dump", text="Dump Debug")

        row = layout.row(align = True)
        row.prop(lightdesk, "show_area", toggle = True, text = "Area" )
        row.prop(lightdesk, "show_point", toggle = True, text = "Point")
        row.prop(lightdesk, "show_spot", toggle = True, text = "Spot")
        row.prop(lightdesk, "show_sun", toggle = True, text = "Sun")

        row = layout.row()
        row.template_list("LIGHTDESK_UL_lights", "", lightdesk, "lights", lightdesk, "selected_index", rows = 2, maxrows = 5, type = 'DEFAULT')

        # check selected light name matches name of object at selected index, if not fix/reset
        if lightdesk.selected_index > -1 and lightdesk.selected_index < len(lightdesk.lights):
            try:
                if lightdesk.selected_name != lightdesk.lights[lightdesk.selected_index].name:
                    lightdesk.selected_name = lightdesk.lights[lightdesk.selected_index].name
            except IndexError:
                lightdesk.selected_index = -1
                lightdesk.selected_name = ""


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
    bl_label = ""

    def draw_header(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split()
        split.prop(lightdesk.channels[0].object, "name", text = "")
        split = row.split()
        split.operator("lightdesk.delete_channel", icon = 'X', text = "")


    def draw(self, context):
        lightdesk = context.scene.lightdesk
        layout = self.layout

        # TODO update controls for specific light/channel rather than index [0]
        if len(lightdesk.channels):
            row = layout.row()
            split = row.split(factor = 0.4, align = True)
            split.prop(lightdesk.channels[0].object, "hide_viewport", icon_only = True, emboss = False)
            split.prop(lightdesk.channels[0].object, "hide_render", icon_only = True, emboss = False)
            split = row.split()
            split = split.split(factor = 0.8)
            split.prop(lightdesk.channels[0].object.data, "energy", text = "")
            split = split.split()
            split.prop(lightdesk.channels[0].object.data, "color", text = "")


#===============================================================================
# Properties
#===============================================================================

class LIGHTDESK_PG_light(PropertyGroup):
    name : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_channel(PropertyGroup):
    panel_class : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_properties(PropertyGroup):
    show_area : BoolProperty(default = True, update = collate_scene_lights)
    show_point : BoolProperty(default = True, update = collate_scene_lights)
    show_spot : BoolProperty(default = True, update = collate_scene_lights)
    show_sun : BoolProperty(default = True, update = collate_scene_lights)
    lights : CollectionProperty(type = LIGHTDESK_PG_light)
    channels : CollectionProperty(type = LIGHTDESK_PG_channel)
    selected_index : IntProperty(default = -1, update = update_selection_tracker)
    selected_name : StringProperty()


#===============================================================================
# Init
#===============================================================================


classes = [
           # Operators
           LIGHTDESK_OT_debug_dump,
           LIGHTDESK_OT_collate_scene_lights,
           LIGHTDESK_OT_add_selected_light,
           LIGHTDESK_OT_add_all_lights,
           LIGHTDESK_OT_delete_channel,
           LIGHTDESK_OT_delete_all_channels,
           # ui elelements
           LIGHTDESK_UL_lights,
           LIGHTDESK_PT_lights,
           # property groups
           LIGHTDESK_PG_light,
           LIGHTDESK_PG_channel,
           LIGHTDESK_PG_properties,
           ]


def register():
    # register main classes
    logging.debug(f"Registering {len(classes)} main classes...")
    for cls in classes:
        logging.debug(f"- {cls}")
        register_class(cls)
    # instantiate lightdesk properties
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_properties)


def unregister():
    # unregister any channel panel classes
    lightdesk = bpy.context.scene.lightdesk
    if len(lightdesk.channels):
        logging.debug(f"Unregistering {len(lightdesk.channels)} panel classes:")
        for channel in lightdesk.channels:
            if channel.panel_class:
                unregister_panel_class(channel.panel_class)
            else:
                logging.warning(f"! Channel {channel.object.name} has no panel_class, skipping")
    else:
        logging.debug("No panel classes registered")
    # clear collections
    # TODO remove and add panel creation from saved data upon load
    lightdesk.channels.clear()
    lightdesk.lights.clear()
    # unregister all main classes
    logging.debug(f"Unregistering {len(classes)} classes:")
    for cls in reversed(classes):
        logging.debug(f"- {cls}")
        try:
            unregister_class(cls)
        except E:
            logging.error(f"! Could not unregister {class_id}")
            logging.error(E)
            pass
    # remove lightdesk properties
    del bpy.types.Scene.lightdesk
