# Lightdesk

Lighting add-on for Blender 2.8+

Lightdesk provides a lighting control panel located in the sidebar of the 3D view.
Add lights from within the current scene to lighting channels on this desk. Control the visibility, power, and color of multiple lights from one location. Adjust and experiment with your scene lighting without having to hunt/click lights and constantly switch back and forth between 3D/Outliner and property views.

## Installation
Install using one of these methods:

* Download the repository as a zip file and install from anywhere, [as per the Blender manual](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html)
* Download and copy `__init__.py` to a subfolder within your Blender installation add-ons directory, e.g. `C:\Program Files\Blender Foundation\Blender 2.90\2.90\scripts\addons\lightdesk`, then enable within Blender preferences.

## Usage

Select the Lightdesk tab in the sidebar of the 3D view to display the Scene Lights panel.

![Light selection](lights.png)

This lists all of the light objects in the current scene. The toggle buttons above may be used to filter the list by light type. Standard filter and sort-by-name options are also available from the drop-down section at the foot of the list.

Select a light from the list and click Add to create a new lighting channel and assign the selected light to it.
Optionally, click Add All to quickly create channels for all the lights currently displayed in the light list. Click Delete All to delete all current channels, or remove individual channels by clicking the Delete button in their panel headers.

![Channels](channels.png)

By default, channels appear below Scene Lights, but all panels can be drag-dropped to reorder and collapsed when additional screen space is required.


![Collapsed](collapsed.png)

Each channel header contains the name of the associated light and a Delete button. Note that clicking the Delete button only removes the channel from Lightdesk and will not delete the associated light object.

![Channel](channel.png)

Operators within each channel are, from left to right:

1. Show/hide the light in the viewport

2. Show/hide the light in the render

3. Light power

4. Light color


Lightdesk channels and settings are configured per scene and are saved with the .blend file, so your channel setup will be recreated next time you load your project. Note that, at present, Lightdesk cannot preserve custom ordering of channels between file loads or scene switches and instead will recreate channels in the order that they were originally added.


## Disclaimer

Lightdesk was initially developed to help with lighting setups in my own personal projects, where adjusting a large number of lights was proving a tedium of clicking back and forth between view window, outliner, and property panel. This add-on is provided as-is and free for use under GNU GPL. I am not a professional developer and make no claims for the quality of the design or implementation, nor its robustness, safety, performance, usefulness, or indeed any other characteristic.

Although I do not intend any further development or to provide ongoing support, kindly report any issues here and I will address them as best I can. Thanks in advance for your feedback, and I hope that Lightdesk might prove of some small help to you in your creative endeavours.
