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
    "version": (0, 1, 6),
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

subscriptions_owner = object()
tracked_scene = object()
exec_queue = queue.Queue()

#===============================================================================
# Functions
#===============================================================================

def start_all_the_things():
    logging.debug("Starting all the things")
    add_function_to_exec_queue(collate_scene_lights)
    add_function_to_exec_queue(filter_lights)
    add_function_to_exec_queue(track_scene)
    add_function_to_exec_queue(create_scene_panels)
    add_handlers()
    add_subscriptions()
    add_timers()

def stop_all_the_stuff():
    logging.debug("Shutting down")
    delete_scene_panels()
    remove_timers()
    remove_subscriptions()
    remove_handlers()

def add_timers():
    if not bpy.app.timers.is_registered(exec_queued_functions):
        logging.debug("- Registering timer: exec_queued_functions")
        bpy.app.timers.register(exec_queued_functions)

def remove_timers():
    if bpy.app.timers.is_registered(exec_queued_functions):
        logging.debug("- Unregistering timers")
        bpy.app.timers.unregister(exec_queued_functions)

def add_subscriptions():
    global subscriptions_owner
    logging.debug("- Adding msgbus subscription: bpy.types.Window.scene")
    subscription = bpy.types.Window, "scene"
    bpy.msgbus.subscribe_rna(
        key = subscription,
        owner = subscriptions_owner,
        args = (bpy.context,),
        notify = switch_scene,
        )

def remove_subscriptions():
    global subscriptions_owner
    logging.debug("- Removing msgbus subscriptions")
    bpy.msgbus.clear_by_owner(subscriptions_owner)

def add_handlers():
    if handle_load_pre not in bpy.app.handlers.load_pre:
        logging.debug("- Adding handler: load_pre")
        bpy.app.handlers.load_pre.append(handle_load_pre)
    if handle_load_post not in bpy.app.handlers.load_post:
        logging.debug("- Adding handler: load_post")
        bpy.app.handlers.load_post.append(handle_load_post)
    if handle_depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        logging.debug("- Adding handler: depsgraph_update_post")
        bpy.app.handlers.depsgraph_update_post.append(handle_depsgraph_update_post)

def remove_handlers():
    if handle_load_pre in bpy.app.handlers.load_pre:
        logging.debug("- Removing handler: load_pre")
        bpy.app.handlers.load_pre.remove(handle_load_pre)
    if handle_load_post in bpy.app.handlers.load_post:
        logging.debug("- Removing handler: load_post")
        bpy.app.handlers.load_post.remove(handle_load_post)
    if handle_depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        logging.debug("- Removing handler: depsgraph_update_post")
        bpy.app.handlers.depsgraph_update_post.remove(handle_depsgraph_update_post)

@persistent
def handle_load_pre(scene):
    logging.debug("Event handler: LOAD_PRE")
    try:
        lightdesk = bpy.context.scene.lightdesk
        delete_scene_panels()
        remove_subscriptions()
    except Exception as e:
        pass
    logging.debug("")

@persistent
def handle_load_post(scene):
    logging.debug("Event handler: LOAD_POST")
    track_scene()
    create_scene_panels()
    add_subscriptions()
    logging.debug("")

@persistent
def handle_depsgraph_update_post(scene):
    global tracked_scene
    logging.debug("Event handler: DEPSGRAPH_UPDATE_POST")
    if bpy.context.scene != tracked_scene:
        try:
            logging.debug(f"- {len(tracked_scene.lightdesk.channels)}")
        except ReferenceError:
            logging.error("Invalid reference: tracked_scene")
            track_scene()
        finally:
            delete_scene_panels()
            track_scene()
            create_scene_panels()
    if len(bpy.context.scene.objects) != len(tracked_scene.objects):
        collate_scene_lights()
        filter_lights()
        validate_selection_tracking()
    logging.debug("")

def add_function_to_exec_queue(function):
    logging.debug(f"Adding to execution queue: {function}")
    exec_queue.put(function)

def exec_queued_functions():
    while not exec_queue.empty():
        function = exec_queue.get()
        logging.debug(f"Executing from queue: {function}")
        function()
    return 1.0

def track_scene():
    global tracked_scene
    tracked_scene = bpy.context.scene
    logging.debug(f"Scene tracked: {tracked_scene.name}")

def switch_scene(context):
    global tracked_scene
    logging.debug("")
    logging.debug(f"Scene switched {tracked_scene.name} > {bpy.context.window.scene.name}")
    delete_scene_panels()
    collate_scene_lights()
    filter_lights()
    validate_selection_tracking()
    track_scene()
    create_scene_panels()
    logging.debug("")

def debug_data():
    global tracked_scene
    try:
        lightdesk = bpy.context.scene.lightdesk
        logging.debug("--------------------------------------------------")
        logging.debug(f"tracked_scene: {tracked_scene.name} {len(tracked_scene.objects)}")
        logging.debug(f"context.scene: {bpy.context.scene.name} {len(bpy.context.scene.objects)}")
        logging.debug(f"{len(lightdesk.lights)} Scene lights:")
        logging.debug(f"- {lightdesk.lights.keys()}")
        logging.debug(f"Light filters:")
        logging.debug(f"- AREA : {lightdesk.list_area}")
        logging.debug(f"- POINT : {lightdesk.list_point}")
        logging.debug(f"- SPOT : {lightdesk.list_spot}")
        logging.debug(f"- SUN : {lightdesk.list_sun}")
        logging.debug(f"{len(lightdesk.filtered)} Filtered lights:")
        logging.debug(f"- {lightdesk.filtered.keys()}")
        logging.debug(f"- {lightdesk.selected_name} ({lightdesk.selected_index}) selected")
        logging.debug(f"{len(lightdesk.channels)} Channels:")
        if len(lightdesk.channels):
            for channel in bpy.context.scene.lightdesk.channels:
                logging.debug(f"- {channel.name}, {channel.object.name}")
        logging.debug("--------------------------------------------------")
    except Exception as e:
        logging.error(e)
    logging.debug("")

def add_light_to_collection(object, collection):
    logging.debug(f"- Adding {object.name} to {collection}")
    lightdesk = bpy.context.scene.lightdesk
    light = collection.add()
    light.name = object.name
    light.object = object

def collate_scene_lights():
    try:
        logging.debug("Collating scene lights")
        lightdesk = bpy.context.scene.lightdesk
        if len(lightdesk.lights):
            logging.debug("- Clearing existing collection")
            lightdesk.lights.clear()
        lights = [object for object in bpy.context.scene.objects if object.type == 'LIGHT']
        for light in lights:
            add_light_to_collection(light, lightdesk.lights)
        logging.debug(f"- {len(lights)} lights added to collection")
    except Exception as e:
        logging.error(e)

def refresh_lights_list(self, context):
    collate_scene_lights()
    update_light_filters(self, context)

def filter_lights():
    logging.debug("Filtering lights")
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

def update_light_filters(self, context):
    logging.debug("Updating light filters")
    filter_lights()
    validate_selection_tracking()

def get_channel_from_light(light_name):
    logging.debug(f"- Checking for existing channel for {light_name}")
    lightdesk = bpy.context.scene.lightdesk
    for channel in lightdesk.channels:
        if channel.object.name == light_name:
            logging.debug(f"- Channel found {channel.name}")
            return True
    logging.debug(f"- No channel found")
    return False

def update_selection_tracking(self, context):
    logging.debug("Updating selection tracking")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1 and lightdesk.selected_index <= len(lightdesk.filtered) - 1:
        lightdesk.selected_name = lightdesk.filtered[lightdesk.selected_index].name
        logging.debug(f"- {lightdesk.selected_name} selected")

def validate_selection_tracking():
    logging.debug("Validating selection tracking")
    lightdesk = bpy.context.scene.lightdesk
    if lightdesk.selected_index > -1:
        lookup = lightdesk.filtered.find(lightdesk.selected_name)
        if lookup > -1:
            logging.debug(f"- {lightdesk.selected_name} found in filtered collection")
            lightdesk.selected_index = lookup
        else:
            logging.debug(f"- {lightdesk.selected_name} not found in filtered collection, trackers reset")
            lightdesk.selected_index = -1
            lightdesk.selected_name = ""

def get_new_panel_id():
    return f"LIGHTDESK_PT_{str(uuid4().hex)}"

def register_panel(panel_id):
    if len(panel_id):
        logging.debug(f"- Registering panel class {panel_id}")
        panel = type(panel_id, (LIGHTDESK_PT_channel, Panel, ), {"bl_idname" : panel_id,})
        try:
            register_class(panel)
        except Exception as e:
            logging.error(f"register_panel({panel_id})")
            logging.error(e)
    else:
        logging.error("register_panel missing panel_id")

def unregister_panel(panel_id):
    if len(panel_id):
        logging.debug(f"- Unregistering panel class '{panel_id}'")
        try:
            class_name = f"bpy.types.{panel_id}"
            cls = eval(class_name)
            unregister_class(cls)
        except Exception as e:
            logging.error(f"unregister_panel({panel_id})")
            logging.error(e)
            deadhead_channels()
    else:
        logging.error("unregister_panel missing panel_id")

def delete_scene_panels():
    global tracked_scene
    logging.debug("Deleting scene panels")
    if len(tracked_scene.lightdesk.channels):
        logging.debug(f"{len(tracked_scene.lightdesk.channels)} panels from {tracked_scene.name}")
        for channel in tracked_scene.lightdesk.channels:
            unregister_panel(channel.name)
    else:
        logging.debug(f"- No channels in {tracked_scene.name}")

def create_scene_panels():
    global tracked_scene
    logging.debug("")
    logging.debug("Creating scene panels")
    if len(tracked_scene.lightdesk.channels):
        logging.debug(f"{len(tracked_scene.lightdesk.channels)} panels for {tracked_scene.name}")
        for channel in tracked_scene.lightdesk.channels:
            register_panel(channel.name)
    else:
        logging.debug(f"- No channels in {tracked_scene.name}")

def add_light_to_channel(light_name):
    lightdesk = bpy.context.scene.lightdesk
    if not get_channel_from_light(light_name):
        logging.debug("- Creating channel")
        try:
            channel = lightdesk.channels.add()
            channel.object = bpy.data.objects[light_name]
            channel.name = get_new_panel_id()
            register_panel(channel.name)
            validate_selection_tracking()
        except Exception as e:
            logging.error(f"create_channel({light_name})")
            logging.error(e)
            deadhead_channels()

def add_all_lights_to_channels():
    lightdesk = bpy.context.scene.lightdesk
    logging.debug(f"Adding {len(lightdesk.filtered)} lights to channels")
    for light in lightdesk.filtered:
        add_light_to_channel(light.object.name)

def pop_channel(channel_name):
    logging.debug(f"- Popping channel out of collection")
    lightdesk = bpy.context.scene.lightdesk
    index = lightdesk.channels.find(channel_name)
    if index > -1:
        lightdesk.channels.remove(index)
    else:
        logging.error(f"delete_channel({channel_name}) could not find channel_name")
        deadhead_channels()

def delete_channel(channel_name):
    logging.debug(f"Deleting channel {channel_name}")
    unregister_panel(channel_name)
    pop_channel(channel_name)

def delete_all_channels():
    logging.debug("")
    logging.debug(f"Deleting {len(bpy.context.scene.lightdesk.channels)} channels:")
    lightdesk = bpy.context.scene.lightdesk
    for channel in reversed(lightdesk.channels):
        delete_channel(channel.name)

def deadhead_channels():
    logging.debug("Deadheading channels")
    lightdesk = bpy.context.scene.lightdesk
    if len(lightdesk.channels):
        logging.debug(f"Verifying {len(lightdesk.channels)} channels")
        for channel in lightdesk.channels:
            if len(channel.name):
                try:
                    class_name = f"bpy.types.{channel.name}"
                    cls = eval(class_name)
                    logging.debug(f"- class {class_name} OK")
                except Exception as e:
                    logging.warning(f"Class {class_name} does not exist, deleting channel")
                    pop_channel(channel.name)
            else:
                    logging.warning(f"Channel name undefined for {channel.object.name}, deleting channel")
                    pop_channel(channel.name)
    logging.debug("")


#===============================================================================
# Operators
#===============================================================================

class LIGHTDESK_OT_debug_data(Operator):
    bl_idname = "lightdesk.debug_data"
    bl_label = "Output debug information to console"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        debug_data()
        return{'FINISHED'}

class LIGHTDESK_OT_refresh_lights_list(Operator):
    bl_idname = "lightdesk.refresh_lights_list"
    bl_label = "Get list of scene lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        refresh_lights_list(self, context)
        return{'FINISHED'}

class LIGHTDESK_OT_add_selected_light(Operator):
    bl_idname = "lightdesk.add_selected_light"
    bl_label = "Add selected light"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.scene.lightdesk.selected_index > -1

    def execute(self, context):
        logging.debug("")
        add_light_to_channel(context.scene.lightdesk.selected_name)
        return {'FINISHED'}

class LIGHTDESK_OT_add_all_lights_to_channels(Operator):
    bl_idname = "lightdesk.add_all_lights_to_channels"
    bl_label = "Add all displayed lights"
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk and len(context.scene.lightdesk.filtered))

    def execute(self, context):
        logging.debug("")
        add_all_lights_to_channels()
        return {'FINISHED'}

class LIGHTDESK_OT_delete_channel(Operator):
    bl_idname = "lightdesk.delete_channel"
    bl_label = "Delete light channel"
    bl_options = {'INTERNAL'}

    channel_name: StringProperty()

    @classmethod
    def poll(cls, context):
        return bool(context.scene.lightdesk)

    def execute(self, context):
        logging.debug("")
        delete_channel(self.channel_name)
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


#===============================================================================
# UI
#===============================================================================

class LIGHTDESK_UL_lights(UIList):

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        lightdesk = bpy.context.scene.lightdesk
        layout.label(text = item.name)

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
            row.operator("lightdesk.refresh_lights_list", text="Populate")
            row.operator("lightdesk.debug_data", text="Debug")
        row = layout.row(align = True)
        row.prop(lightdesk, "list_area", toggle = True, text = "Area" )
        row.prop(lightdesk, "list_point", toggle = True, text = "Point" )
        row.prop(lightdesk, "list_spot", toggle = True, text = "Spot" )
        row.prop(lightdesk, "list_sun", toggle = True, text = "Sun" )
        row = layout.row()
        row.template_list("LIGHTDESK_UL_lights", "", lightdesk, "filtered", lightdesk, "selected_index", rows = 2, maxrows = 5, type = 'DEFAULT')
        row = layout.row()
        row.operator("lightdesk.add_selected_light", text="Add")
        row.operator("lightdesk.add_all_lights_to_channels", text="Add All")
        row.operator("lightdesk.delete_all_channels", text="Delete All")

class LIGHTDESK_PT_channel(Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Lightdesk'
    bl_context = 'objectmode'
    bl_idname = "LIGHTDESK_PT_channel"
    bl_options = {'HEADER_LAYOUT_EXPAND'}
    bl_label = ""

    def draw_header(self, context):
        global ui_condensed
        lightdesk = bpy.context.scene.lightdesk
        layout = self.layout
        row = layout.row()
        split = row.split(factor = 0.85)
        split.label(text = lightdesk.channels[self.bl_idname].object.name)
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
    list_area : BoolProperty(default = True, update = update_light_filters)
    list_point : BoolProperty(default = True, update = update_light_filters)
    list_spot : BoolProperty(default = True, update = update_light_filters)
    list_sun : BoolProperty(default = True, update = update_light_filters)
    lights : CollectionProperty(type = LIGHTDESK_PG_light)
    filtered : CollectionProperty(type = LIGHTDESK_PG_light)
    channels : CollectionProperty(type = LIGHTDESK_PG_channel)
    selected_index : IntProperty(default = -1, update = update_selection_tracking)
    selected_name : StringProperty()


#===============================================================================
# Registration
#===============================================================================


classes = [
            LIGHTDESK_OT_debug_data,
            LIGHTDESK_OT_refresh_lights_list,
            LIGHTDESK_OT_add_selected_light,
            LIGHTDESK_OT_add_all_lights_to_channels,
            LIGHTDESK_OT_delete_channel,
            LIGHTDESK_OT_delete_all_channels,
            LIGHTDESK_PG_light,
            LIGHTDESK_PG_channel,
            LIGHTDESK_PG_properties,
            LIGHTDESK_UL_lights,
            LIGHTDESK_PT_lights,
            ]

def register():
    logging.debug("Lightdesk activated")
    logging.debug(f"Registering {len(classes)} classes:")
    for cls in classes:
        logging.debug(f"- {cls}")
        register_class(cls)
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_properties)
    start_all_the_things()
    logging.debug("Energise!")
    logging.debug("")

def unregister():
    logging.debug("Lightdesk deactivated")
    stop_all_the_stuff()
    logging.debug(f"Unregistering {len(classes)} classes:")
    for cls in reversed(classes):
        logging.debug(f"- {cls}")
        unregister_class(cls)
    del bpy.types.Scene.lightdesk
    logging.debug("He's dead, Jim!")
    logging.debug("")
