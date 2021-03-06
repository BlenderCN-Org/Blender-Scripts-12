bl_info = {
	"name": "Distance Weighted Weight Transfer",
	"description": "Smart Transfer Weights operator",
	"author": "Mets 3D",
	"version": (1, 2),
	"blender": (2, 80, 0),
	"location": "Search -> Smart Weight Transfer",	# TODO: Add to Weights menu.
	"category": "Object"
}

import bpy
import mathutils
from mathutils import Vector
import math
from bpy.props import *

def build_weight_dict(obj, vgroups=None, mask_vgroup=None, bone_combine_dict=None):
	""" Builds and returns a dictionary that matches the vertex indicies of the object to a list of tuples containing the vertex group names that the vertex belongs to, and the weight of the vertex in that group.
		vgroups: If passed, skip groups that aren't in vgroups.
		bone_combine_dict: Can be specified if we want some bones to be merged into others, eg. passing in {'Toe_Main' : ['Toe1', 'Toe2', 'Toe3']} will combine the weights in the listed toe bones into Toe_Main. You would do this when transferring weights from a model of actual feet onto shoes.
	"""
	
	weight_dict = {}	# {vert index : [('vgroup_name', vgroup_value), ...], ...}
	
	if(vgroups==None):
		vgroups = obj.vertex_groups
	
	for v in obj.data.vertices:
		# TODO: instead of looking through all vgroups we should be able to get only the groups that this vert is assigned to via v.groups[0].group which gives the group id which we can use to get the group via Object.vertex_groups[id]
		# With this maybe it's useless altogether to save the weights into a dict? idk.
		# Although the reason we are doing it this way is because we wanted some bones to be considered the same as others. (eg. toe bones should be considered a single combined bone)
		for vg in vgroups:
			w = 0
			try:
				w = vg.weight(v.index)
			except:
				pass
			
			# Adding the weights from any sub-vertexgroups defined in bone_combine_dict
			if(vg.name in bone_combine_dict.keys()):
				for sub_vg_name in bone_combine_dict[vg.name]:
					sub_vg = obj.vertex_groups.get(sub_vg_name)
					if(sub_vg==None): continue
					try:
						w = w + sub_vg.weight(v.index)
					except RuntimeError:
						pass
			
			if(w==0): continue
			
			# Masking transfer influence
			if(mask_vgroup):
				try:
					multiplier = mask_vgroup.weight(v.index)
					w = w * multiplier
				except:
					pass
			
			# Create or append entry in the dict.
			if(v.index not in weight_dict):
				weight_dict[v.index] = [(vg.name, w)]
			else:
				weight_dict[v.index].append((vg.name, w))
	
	return weight_dict
			
def build_kdtree(obj):
	kd = mathutils.kdtree.KDTree(len(obj.data.vertices))
	for i, v in enumerate(obj.data.vertices):
		kd.insert(v.co, i)
	kd.balance()
	return kd

def smart_transfer_weights(obj_from, obj_to, weights, max_verts=30, max_dist=10, dist_multiplier=1000, ):
	""" Smart Vertex Weight Transfer.
		The number of nearby verts which it searches for depends on how far the nearest vert is. (This is controlled by max_verts, max_dist and dist_multiplier)
		This means if a very close vert is found, it won't look for any more verts.
		If the nearest vert is quite far away(or dist_multiplier is set high), it will average the influences of a larger number few verts.
		The averaging of the influences is also weighted by their distance, so that a vertex which is twice as far away will contribute half as much influence to the final result.
		weights: a dictionary of vertex weights that needs to be built with build_weight_dict().
	"""
	kd = build_kdtree(obj_from)
	
	for v in obj_to.data.vertices:
		# Finding the nearest vertex on source object
		nearest_co, nearest_idx, nearest_dist = kd.find(v.co)

		# Determine how many verts in total should be checked, based on the distance of the closest vert.
		number_of_source_verts = 1 + round( pow( (nearest_dist * dist_multiplier), 2 ) )
		number_of_source_verts = max_verts if number_of_source_verts > max_verts else number_of_source_verts
		
		
		# Find the previously calculated amount of nearest verts. Save their index and distance to a list of (index, distance) tuples.
		source_verts = []
		
		for(co, index, dist) in kd.find_n(v.co, number_of_source_verts):
			if( (index not in weights) or (dist > max_dist) ):	# If the found vert doesn't have any weights OR is too far away
				continue
			source_verts.append((index, dist))
		
		# Sort valid verts by distance (least to most distance)
		source_verts.sort(key=lambda tup: tup[1])
		
		# Iterating through the source verts, from closest to furthest, and accumulating our target weight for each vertex group.
		vgroup_weights = {}	# Dictionary of Vertex Group Name : Weight
		for i in range(0, len(source_verts)):
			vert = source_verts[i]
			# The closest vert's weights are multiplied by the farthest vert's distance, and vice versa. The 2nd closest will use the 2nd farthest, etc.
			# Note: The magnitude of the distance vectors doesn't matter because at the end they will be normalized anyways.
			pair_distance = source_verts[-i-1][1]
			for vg_name, vg_weight in weights[vert[0]]:
				new_weight = vg_weight * pair_distance
				if(vg_name not in vgroup_weights):
					vgroup_weights[vg_name] = new_weight
				else:
					vgroup_weights[vg_name] = vgroup_weights[vg_name] + new_weight
		
		# The sum is used to normalize the weights. This is important because otherwise the values would depend on object scale, and in the case of very small or very large objects, stuff could get culled.
		weights_sum = sum(vgroup_weights.values())
		
		# Assigning the final, normalized weights of this vertex to the vertex groups.
		for vg_avg in vgroup_weights.keys():
			target_vg = obj_to.vertex_groups.get(vg_avg)
			if(target_vg == None):
				target_vg = obj_to.vertex_groups.new(name=vg_avg)
			target_vg.add([v.index], vgroup_weights[vg_avg]/weights_sum, 'REPLACE')
	
	bpy.ops.object.mode_set(mode='WEIGHT_PAINT')

w3_bone_dict_str = """{
	'Hip_Def' : ['Gens_Root', 'Vagoo_Root', 'Anus_Root', 'Gens_Mid', 'Butt_Mid', 
	'Vagoo_Top', 'Vagoo.L', 'Vagoo.R', 'Vagoo_Bottom', 
	'Anus_Top', 'Anus_Bottom', 
	'Anus.L.004', 'Anus.L.003', 'Anus.L.002', 'Anus.L.001', 'Anus.L', 
	'Anus.R', 'Anus.R.001', 'Anus.R.002', 'Anus.R.003', 'Anus.R.004'],

	'Butt.L' : ['Butt_Top.L', 'Butt_Inner.L', 'Butt_Bot.L', 'Butt_Outer.L'],

	'Butt.R' : ['Butt_Top.R', 'Butt_Outer.R', 'Butt_Bot.R', 'Butt_Inner.R'],

	'Breast.L' : ['Breast_Top.L', 'Breast_Outer.L', 'Breast_Inner.L', 'Breast_Bot.L', 'Breast_Nipple.L'],

	'Breast.R' : ['Breast_Top.R', 'Breast_Inner.R', 'Breast_Outer.R', 'Breast_Bot.R'],

	'Toe_Def.L' : ['Toe_Thumb1.L', 'Toe_Thumb2.L', 'Toe_Index1.L', 'Toe_Index2.L', 'Toe_Middle1.L', 'Toe_Middle2.L', 'Toe_Ring1.L', 'Toe_Ring2.L', 'Toe_Pinky1.L', 'Toe_Pinky2.L'],

	'Toe_Def.R' : ['Toe_Thumb1.R', 'Toe_Thumb2.R', 'Toe_Index1.R', 'Toe_Index2.R', 'Toe_Middle1.R', 'Toe_Middle2.R', 'Toe_Ring1.R', 'Toe_Ring2.R', 'Toe_Pinky1.R', 'Toe_Pinky2.R'],

	'Hand_Def.L' : ['l_thumb_roll', 'l_pinky0', 'l_index_knuckleRoll', 'l_middle_knuckleRoll', 'l_ring_knuckleRoll'],

	'Hand_Def.R' : ['r_thumb_roll', 'r_pinky0', 'r_index_knuckleRoll', 'r_middle_knuckleRoll', 'r_ring_knuckleRoll'],
}"""

w3_vgroups = ['Hip_Def', 'Butt_Mid', 'Neck_Def', 'Head_Def', 'Breast.R', 'Breast.L', 'Clavicle_Def.R', 'Clavicle_Adjust.R', 'Clavicle_Def.L', 'Clavicle_Adjust.L', 'Spine3_Def', 'Spine2_Def', 'Spine1_Def', 'Adjust_Knee.R', 'Twist_Leg_2.R', 'Twist_Leg_1.R', 'Foot_Def.R', 'Toes_Def.R', 'Toe_Def.R', 'Butt.R', 'Thigh_Def.R', 'Twist_Leg_3.R', 'Adjust_Thigh_Front.R', 'Adjust_Thigh_Side.R', 'Twist_Leg_4.R', 'Adjust_Knee.L', 'Twist_Leg_2.L', 'Twist_Leg_1.L', 'Foot_Def.L', 'Toes_Def.L', 'Toe_Def.L', 'Butt.L', 'Thigh_Def.L', 'Twist_Leg_3.L', 'Adjust_Thigh_Front.L', 'Adjust_Thigh_Side.L', 'Twist_Leg_4.L', 'Elbow_Def.R', 'Adjust_Elbow_Lower.R', 'Shoulder_Def.R', 'Adjust_Elbow_Upper.R', 'Twist_Arm_5.R', 'Twist_Arm_6.R', 'Twist_Arm_2.R', 'Twist_Arm_1.R', 'Twist_Arm_4.R', 'Twist_Arm_3.R', 'Hand_Def.R', 'Elbow_Def.L', 'Adjust_Elbow_Lower.L', 'Shoulder_Def.L', 'Adjust_Elbow_Upper.L', 'Twist_Arm_5.L', 'Twist_Arm_6.L', 'Twist_Arm_1.L', 'Twist_Arm_2.L', 'Twist_Arm_4.L', 'Twist_Arm_3.L', 'Hand_Def.L']

class SmartWeightTransferOperator(bpy.types.Operator):
	"""Transfer weights from active to selected objects based on weighted vert distances."""
	bl_idname = "object.smart_weight_transfer"
	bl_label = "Smart Transfer Weights"
	bl_options = {'REGISTER', 'UNDO'}
	
	opt_source_vgroups: EnumProperty(name="Source Groups",
		items=[("ALL", "All", "All"),
				("SELECTED", "Selected Bones", "Selected Bones"),
				("DEFORM", "Deform Bones", "Deform Bones"),
				],
		description="Which vertex groups to transfer from the source object",
		default="ALL")
	
	opt_wipe_originals: BoolProperty(name="Wipe originals", 
		default=True, 
		description="Wipe original vertex groups before transferring. Recommended. Does not wipe vertex groups that aren't being transferred in the first place")
	
	opt_max_verts: IntProperty(name="Max considered verts", 
		default=5, 
		description="Increase this if your mesh is very high poly or decrease for very low poly. Set to 1 will give the same result as the built-in Transfer Weights operator")
	
	opt_max_dist: FloatProperty(name="Max distance", 
		default=1000, 
		description="Higher values allow weights from further away verts to contribute to the result.")
	
	opt_dist_multiplier: FloatProperty(name="Smoothness", 
		default=1000, 
		description="Higher values will consider more verts based on the distance of the closest vert. Has less effect on verts that are close to the source mesh. If the source and the target mesh are exactly the same, this has no effect. Increasing this after a certain point will have no effect since the maximum allowed verts will be reached before the maximum distance")
	
	def get_vgroups(self, context):
		items = [('None', 'None', 'None')]
		for vg in context.object.vertex_groups:
			items.append((vg.name, vg.name, vg.name))
		return items
	
	opt_mask_vgroup: EnumProperty(name="Operator Mask",
		items=get_vgroups,
		description="The operator's effect will be masked by this vertex group, unless 'None'")
	
	opt_bone_combine_dict: StringProperty(name='Combine Dict',
		description="If you want some groups to be considered part of others(eg. to avoid transferring individual toe weights onto shoes), you can enter them here in the form of a valid Python dictionary, where the keys are the parent group name, and values are lists of child group names, eg: {'Toe_Main.L' : ['Toe1.L', 'Toe2.L'], 'Toe_Main.R' : ['Toe1.R', 'Toe2.R']}",
		default=w3_bone_dict_str
	)

	@classmethod
	def poll(cls, context):
		return (context.object is not None) and (context.object.mode=='WEIGHT_PAINT')
	
	def draw(self, context):
		operator = self.layout.operator(SmartWeightTransferOperator.bl_idname, text=SmartWeightTransferOperator.bl_label)

	def execute(self, context):
		assert len(context.selected_objects) > 1, "At least two objects must be selected. Select the source object last, and enter weight paint mode."
		
		bone_dict = ""
		if(self.opt_bone_combine_dict != ""):
			bone_dict = eval(self.opt_bone_combine_dict)
		
		source_obj = context.object
		for o in context.selected_objects:
			if(o==source_obj or o.type!='MESH'): continue
			bpy.ops.object.mode_set(mode='OBJECT')
			bpy.ops.object.select_all(action='DESELECT')
			
			vgroups = []
			error = ""
			if(self.opt_source_vgroups == "ALL"):
				vgroups = o.vertex_groups
				error = "the source has no vertex groups."
			elif(self.opt_source_vgroups == "SELECTED"):
				assert context.selected_pose_bones, "No selected pose bones to transfer from."
				vgroups = [source_obj.vertex_groups.get(b.name) for b in context.selected_pose_bones]
				error = "no bones were selected."
			elif(self.opt_source_vgroups == "DEFORM"):
				vgroups = [source_obj.vertex_groups.get(b.name) for b in context.pose_object.data.bones if b.use_deform]
				error = "there are no deform bones"
			
			# Using hard coded vertex group names because it's easier than selecting all the right bones, I guess? TODO: could turn that hardcoded list into a parameter, just like the bone dict.
			# vgroups = [source_obj.vertex_groups.get(vgn) for vgn in w3_vgroups]
			
			# Clean up
			vgroups = [vg for vg in vgroups if vg != None]
			assert len(vgroups) > 0, "No transferable Vertex Groups were found, " + error
			
			# Delete the vertex groups from the destination mesh first...
			if(self.opt_wipe_originals):
				for vg in vgroups:
					if(vg.name in o.vertex_groups):
						o.vertex_groups.remove(o.vertex_groups.get(vg.name))
			
			mask_vgroup = o.vertex_groups.get(self.opt_mask_vgroup)
			
			weights = build_weight_dict(source_obj, vgroups, mask_vgroup, bone_dict)
			smart_transfer_weights(source_obj, o, weights, self.opt_max_verts, self.opt_max_dist, self.opt_dist_multiplier)
			
			bpy.context.view_layer.objects.active = o
			bpy.ops.object.mode_set(mode='WEIGHT_PAINT')
		
		return { 'FINISHED' }

def register():
	from bpy.utils import register_class
	register_class(SmartWeightTransferOperator)
	bpy.types.VIEW3D_MT_paint_weight.append(SmartWeightTransferOperator.draw)

def unregister():
	from bpy.utils import unregister_class
	unregister_class(SmartWeightTransferOperator)
	bpy.types.VIEW3D_MT_paint_weight.remove(SmartWeightTransferOperator.draw)