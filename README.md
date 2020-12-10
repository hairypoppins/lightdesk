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

Select a light from the list and click Add Selected to create a new lighting channel and assign the selected light to it.
Optionally, click Add All to quickly create channels for all the lights currently displayed in the light list.

![Light selection](channels.png)

By default, channels appear below Scene Lights, but all panels can be drag-dropped to reorder and collapsed when additional screen space is required.

Each channel header contains the name of the associated light and a Delete Channel button. Note that clicking the Delete Channel button will not delete the associated light, only remove that channel from Lightdesk.

Operators within each channel are, from left to right:

1. Show/hide the light in the viewport

2. Show/hide the light in the render

3. Light power

4. Light color


Lightdesk channels and settings are configured per scene and are saved with the .blend file, so your channel setup will be recreated next time you load your project.


## Note

Lightdesk was initially developed to help with lighting setups in my own personal projects, where adjusting a large number of lights was proving a tedium of clicking back and forth between views and property panels. It is provided as-is and without restriction for use under GNU GPL. Feel free to use, distribute, fork, modify, or extend this in any manner that you wish. I am not a professional developer and make no claims for the quality of the design or implementation, nor its robustness, safety, performance, usefulness, or indeed any other characteristic. It might make you 0.2% more sexy... though this may prove difficult to measure.

I do not currently intend any further development or to provide ongoing support. Kindly report any issues here and, if it's a serious defect and a fix is within my grasp, I will address it as soon as I can. Thanks in advance for your feedback, and I hope that Lightdesk proves of some help to you in your creative endeavours.
