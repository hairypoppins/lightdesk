# Lightdesk

An add-on for Blender 2.8+

Lightdesk provides a lighting control panel in the sidebar of any 3D view.
Add lights from the current scene to lighting channels on the desk. Control the visibility, power, and color of multiple lights from this single panel. Tweak your scene lighting without first having to hunt/select individual lights in the 3D/Outliner views and clicking their light properties tab.

Select the Lightdesk tab in the 3D view sidebar ('N') and a Scene Lights panel will be displayed.

{insert panel image}

This panel will list all the light objects in the current scene. The buttons above may be used to filter the list by light types.

Select a light from the list and click Add Selected to create a new lighting channel and assign the selected light to it.
Click Add All to quickly create channels for all lights in the current scene.

{insert channel image}

Operators, from left to right, are:

  Show/hide the light in the viewport
  Show/hide the light in the render
  Light power/energy
  Light color
  Delete channel

Channel panels may be reordered by drag-drop and collapsed when necessary. Clicking a channel's  Delete button will not delete the associated light object, only remove the channel.

Lightdesk channels and settings are configured per scene and are saved with the .blend file, so your channel setup will be recreated next time you load your project.
