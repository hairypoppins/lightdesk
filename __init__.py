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
    "version": (0, 1, 0),
    "category": "Lighting",
    "location": "",
    "warning": "",
    "wiki_url": "",
    "tracker_url": "",
}

import bpy
from bpy.utils import (register_class,
                       unregister_class
                       )
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
import lightdesk

import logging
logging.basicConfig(level = logging.DEBUG)


class LIGHTDESK_PG_light(PropertyGroup):
    name : StringProperty()
    object : PointerProperty(type = bpy.types.Object)

class LIGHTDESK_PG_channel(PropertyGroup):
    name : StringProperty()
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
    # Properties
    LIGHTDESK_PG_light,
    LIGHTDESK_PG_channel,
    LIGHTDESK_PG_properties,
    # Operators
    LIGHTDESK_OT_debug_dump,
    LIGHTDESK_OT_collate_scene_lights,
    LIGHTDESK_OT_add_selected_light,
    LIGHTDESK_OT_add_all_lights,
    LIGHTDESK_OT_delete_channel,
    LIGHTDESK_OT_delete_all_channels,
    # UI
    LIGHTDESK_UL_lights,
    LIGHTDESK_PT_lights,
    ]


def register():
    for cls in classes:
        logging.debug("registering {}".format(cls))
        register_class(cls)
    bpy.types.Scene.lightdesk = PointerProperty(type = LIGHTDESK_PG_properties)

def unregister():
    for cls in reversed(classes):
        logging.debug("unregistering {}".format(cls))
        unregister_class(cls)
    del bpy.types.Scene.lightdesk
