# Blender UE4 map import tools

## Basic steps

- Dump the game's models and textures using UE Viewer.
	- Export models as GLTF
	- Export textures as TGA
	- Use the ACL compatible version of UE Viewer if necessary https://www.gildor.org/smf/index.php/topic,8304.0.html
- Save the .umap file as .json using FModel (https://fmodel.app)
- Open `map_mesh_import.py` in Blender's script editor
	- Adjust the variables as instructed in the script
- Run the script
	- Monitor Blender system console for output for errors
	- If models imported correctly, continue with next script
- Open `map_mesh_import.py` in the Blender script editor
	- Edit the `mat_dir` variable
- Run script
	- Monitor Blender system console for output for errors
	- If materials show up in material preview mode, clean up any trash remaining in the scene


## Limitations

- No UI
- Model script will fail silently and continue if GLTF file is not found

- Texture file name matching only returns first file found.
	- When multiple files in different directories have the same name, this may result in the wrong image textures being assigned to materials.
- Texture names are read from .mat files.
	- If the wrong textures end up in a .mat file's Diffuse and Normal slots, the wrong textures will be assigned.
	- Script can't reliably read anything except Diffuse and Normal.
		- No consistent naming convention exists. For Hogwarts Legacy, you may find _SRXO and _MRO files for Specular/Metallic, Roughness and Occlusion, but there is no automatic matching for this.
	
## Credits
- Aetheras Veras (main script)
- Ganonmaster (refactoring)
- AmmoBlender (testing)