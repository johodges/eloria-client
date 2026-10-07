extends SceneTree
## Exercise combined generated armour through the real attachment path.
## Optional user argument: directory containing candidate leg/boot/head GLBs.

var failures := 0
var checks := 0

const FACE_DEFAULT := 0
const FACE_RETAIN := 1
const FACE_REMOVE := -1
const ORUN_PROFILE_SURFACE := 3
## Spikes and loose shards a cut through the generic neck bridge may drop per
## mesh beyond the per-face rule (measured up to 48 on 2026-10-06; re-measure
## after any race GLB regeneration).
const BRIDGE_DEBRIS_CEILING := 64
const ORUN_PROFILE_FACES := [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12,
	14, 15, 16, 17, 18, 20, 21, 27, 28, 36, 37, 50, 51, 57, 63, 64, 67,
	68, 69, 71, 86, 88, 89, 95, 101, 109, 112, 125, 128, 129, 151, 152,
	160, 192, 213, 219, 220, 249, 251, 278, 342, 343, 344, 346, 387, 409,
	414, 415, 432, 433, 443, 453, 461, 462, 467, 468, 470, 490, 491, 492,
	504, 508, 509, 510, 512, 517, 523, 524, 525, 526, 531, 537, 538, 545,
	546]

func _init() -> void:
	call_deferred("run")

func expect(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		push_error(message)

func verify_body(actor: ReplicatedActor3D, active: Dictionary, label: String) -> void:
	var regions: Array = []
	var backing_parts: Array = []
	for part: int in active:
		for piece: Node in actor._equipment_nodes.get(part, []):
			if piece.has_meta("replaces_torso_body") and not piece.has_meta("generated_body_cover"):
				regions.append(Vector3(.95, 1.535, .665))
				backing_parts.append(part)
			if piece.has_meta("generated_body_cover"):
				regions.append(piece.get_meta("generated_body_cover"))
				backing_parts.append(part)
	for part: int in [4, 5, 6]:
		expect(backing_parts.has(part) == active.has(part), label + " backing metadata for slot " + str(part))
	var visible_boot_backings := 0
	for piece: Node in actor._equipment_nodes.get(6, []):
		if piece.has_meta("boot_backing_with_legs"):
			var expected_visible := bool(piece.get_meta("boot_backing_with_legs")) == active.has(4)
			expect((piece as MeshInstance3D).visible == expected_visible, label + " chooses the matching cuff lining")
			visible_boot_backings += int((piece as MeshInstance3D).visible)
	if active.has(6):
		expect(visible_boot_backings == 1, label + " has exactly one boot lining")
	var visible_leg_backings := 0
	for piece: Node in actor._equipment_nodes.get(4, []):
		if piece.has_meta("leg_backing_with_boots"):
			var expected_visible := bool(piece.get_meta("leg_backing_with_boots")) == active.has(6)
			expect((piece as MeshInstance3D).visible == expected_visible, label + " chooses the matching trouser hem")
			visible_leg_backings += int((piece as MeshInstance3D).visible)
	if active.has(4):
		expect(visible_leg_backings == 1, label + " has exactly one trouser lining")
	var changed := 0
	var removed := 0
	var retained := 0
	var profile_removed := 0
	var collar_cover := false
	for region: Vector3 in regions:
		collar_cover = collar_cover or (TorsoBodyCover.NECK_ENVELOPE_MIN_Y > region.x
			and TorsoBodyCover.NECK_ENVELOPE_MIN_Y < region.y and region.z > 0.0)
	for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
		var instance := node as MeshInstance3D
		if instance.name.to_lower() in ["hair", "eyes"]:
			expect(not instance.has_meta("uncovered_body_mesh"), "hair and eyes stay intact")
		if not instance.has_meta("uncovered_body_mesh"):
			continue
		var original := instance.get_meta("uncovered_body_mesh") as Mesh
		if regions.is_empty():
			expect(instance.mesh == original, label + " exact resource restored")
			continue
		changed += int(instance.mesh != original)
		var transform := actor._native_skeleton.global_transform.affine_inverse() * instance.global_transform
		var bridged_mesh := false
		for surface: int in range(original.get_surface_count()):
			var surface_material := original.surface_get_material(surface)
			bridged_mesh = bridged_mesh or (surface_material != null
				and surface_material.resource_name == "Shared neck bridge")
		var bridge_debris := 0
		for surface: int in range(original.get_surface_count()):
			var before := original.surface_get_arrays(surface)
			var after := instance.mesh.surface_get_arrays(surface)
			var material := original.surface_get_material(surface)
			var bridge_surface := (material != null
				and material.resource_name == "Shared neck bridge")
			var profile_driven_bridge := (actor.rig_name() == "orun_male"
				and collar_cover and bridge_surface
				and surface == ORUN_PROFILE_SURFACE)
			for field: int in [Mesh.ARRAY_TEX_UV, Mesh.ARRAY_BONES, Mesh.ARRAY_WEIGHTS]:
				expect(before[field] == after[field], label + " preserves vertex data " + str(field))
			# Positions too, apart from the levelled hems of a cut neck bridge.
			expect(hem_moves_only(before[Mesh.ARRAY_VERTEX], after[Mesh.ARRAY_VERTEX],
				transform, actor.rig_fit_scale(), bridged_mesh and collar_cover
				and actor.rig_name() != "orun_male"),
				label + " preserves vertex positions apart from the neck-bridge hems")
			# ArrayMesh repacks octahedral normals when rebuilding an index buffer.
			# Allow its quantization, but no change in surface direction.
			var before_normals: PackedVector3Array = before[Mesh.ARRAY_NORMAL]
			var after_normals: PackedVector3Array = after[Mesh.ARRAY_NORMAL]
			var normal_error := 0.0
			for i: int in range(before_normals.size()):
				normal_error = maxf(normal_error, before_normals[i].distance_to(after_normals[i]))
			expect(normal_error < .0002, label + " normal quantization " + str(normal_error))
			var vertices: PackedVector3Array = before[Mesh.ARRAY_VERTEX]
			var expected := PackedInt32Array()
			var indices: PackedInt32Array = before[Mesh.ARRAY_INDEX]
			for i: int in range(0, indices.size(), 3):
				var center := transform * ((vertices[indices[i]] + vertices[indices[i + 1]] + vertices[indices[i + 2]]) / 3.0)
				center /= actor.rig_fit_scale()
				var covered := false
				for region: Vector3 in regions:
					covered = covered or (center.y > region.x and center.y < region.y and absf(center.x) < region.z)
				# A torso replaces the complete default collar, including its
				# few tips above the chest band's upper bound.
				if active.has(5) and instance.name.to_lower() == "wardrobe_shirt":
					covered = covered or (center.y > 1.40 and center.y < 1.65 and absf(center.x) < .20)
				var disposition := protected_face_disposition(instance, before, indices, i,
					transform, actor.rig_fit_scale(), collar_cover, bridge_surface,
					profile_driven_bridge, covered,
					actor.rig_name() == "orun_male" and collar_cover)
				if disposition == FACE_RETAIN:
					covered = false
				elif disposition == FACE_REMOVE:
					covered = true
				# Independent literal oracle for the data-selected Orun rear-neck
				# profile. It applies only while a torso/collar region is active;
				# bare, leg-only and boot-only states preserve the closed source.
				if (actor.rig_name() == "orun_male" and collar_cover
						and instance.name.to_lower() in ["body", "char1", "mesh_node"]
						and surface == ORUN_PROFILE_SURFACE
						and ORUN_PROFILE_FACES.has(i / 3)):
					covered = true
					profile_removed += 1
				if actor.rig_name().begins_with("ssarathi_") and TorsoBodyCover.is_tail(center):
					covered = false
				# Independent anatomical sentinel: the posterior tail core must
				# survive every outfit/removal order, regardless of band metadata.
				if actor.rig_name().begins_with("ssarathi_") and center.z < -.35 and center.y < .90:
					expect(not covered, label + " preserves the posterior tail core")
				if instance.name.to_lower() == "body" and not collar_cover \
						and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y \
						and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH:
					expect(not covered, label + " leaves the neck intact without torso coverage")
				if covered:
					removed += 1
				else:
					retained += 1
					expected.append_array(indices.slice(i, i + 3))
			if expected.is_empty():
				expected = PackedInt32Array([0, 0, 0])
			# A cut through the generic bridge may also drop its spikes and
			# loose shards; nothing else may differ.
			var debris := dropped_faces(expected, after[Mesh.ARRAY_INDEX])
			expect(debris == 0 or (debris > 0 and bridge_surface and collar_cover),
				label + " retains exactly the uncovered triangles, less neck-bridge debris")
			bridge_debris += maxi(debris, 0)
		expect(bridge_debris <= BRIDGE_DEBRIS_CEILING,
			label + " drops %d neck-bridge debris faces, ceiling %d"
			% [bridge_debris, BRIDGE_DEBRIS_CEILING])
	if not regions.is_empty():
		expect(changed > 0 and removed > 20 and retained > 20, label + " has active, bounded clothing replacement")
	var expected_profile_removed := (ORUN_PROFILE_FACES.size()
		if actor.rig_name() == "orun_male" and collar_cover else 0)
	expect(profile_removed == expected_profile_removed,
		label + " applies the exact coverage-active Orun profile rows")

func run() -> void:
	var models: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/models.json"))["models"]
	var equipment: Dictionary = JSON.parse_string(FileAccess.get_file_as_string("res://data/actors/equipment.json"))
	var candidate_args := OS.get_cmdline_user_args()
	if not candidate_args.is_empty():
		for key: String in equipment["models"]:
			if int(key.get_slice(":", 0)) not in [3, 4, 6]:
				continue
			var entry: Dictionary = equipment["models"][key]
			var path := candidate_args[0].path_join(str(entry.get("scene", "")).get_file())
			if FileAccess.file_exists(path):
				entry["scene"] = path
	var sets: Array = [
		["legendary_hero_cuirass_01", "legendary_leg_armor_01", "legendary_sabatons_01", "legendary_eloria_helm_01"],
		["amberwood_woodland_cuirass_04", "amberwood_woodland_legguards_04", "amberwood_woodland_boots_04", "amberwood_forest_helm_04"],
		["eloria_arcane_armor_03", "arcane_leg_armor_03", "arcane_fantasy_boots_03", "arcane_ethereal_circlet_03"]]
	var outfits: Array = []
	for slugs: Array in sets:
		var outfit: Dictionary = {}
		for key: String in equipment["models"]:
			var scene: String = equipment["models"][key].get("scene", "")
			if scene.get_file().get_basename() in slugs:
				outfit[int(key.get_slice(":", 0))] = int(key.get_slice(":", 1))
		expect(outfit.size() == 4, "complete outfit resolves in catalogue")
		outfits.append(outfit)
	var races := 0
	var transitions := 0
	for path: String in DirAccess.get_files_at("res://assets/actors/native/races"):
		if not path.ends_with(".glb"):
			continue
		var race := path.get_basename()
		var actor := ReplicatedActor3D.new()
		root.add_child(actor)
		var config: Dictionary = models[race]
		var animations: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(config["animationMap"]))
		var errors := actor.configure({"actor_id": 992, "x": 0, "y": 0, "rotation": 0,
			"kind": 1, "name": race, "appearance": {}, "equipment_visuals": {}},
			CoordinateAdapter.new({"walkingHeight": 0.0}), config, animations, equipment)
		expect(errors.is_empty(), race + " configures: " + str(errors))
		var initial_hair: Dictionary = {}
		var has_feature_head := actor.find_child("race_feature_head", true, false) != null
		for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
			if node.name.to_lower() in ["hair", "scalp"]:
				initial_hair[node.get_instance_id()] = (node as MeshInstance3D).visible
		for outfit: Dictionary in outfits:
			# Every single slot, then two different removal orders from a full set.
			var states: Array = [{4: outfit[4]}, {6: outfit[6]}, {3: outfit[3]}, outfit,
				{3: outfit[3], 5: outfit[5], 6: outfit[6]}, {3: outfit[3], 6: outfit[6]}, {},
				outfit, {3: outfit[3], 4: outfit[4], 5: outfit[5]}, {4: outfit[4]}, {}]
			for active: Dictionary in states:
				actor.apply_equipment_visuals(active)
				verify_body(actor, active, race + " " + str(active.keys()))
				var covered_hair := active.has(3) and int(active[3]) != int(outfits[2][3])
				# A hood whose policy shows race features hides the hair only, on a
				# body that carries race_feature_head; any other body hides its
				# scalp with the hair.
				var covered_scalp := covered_hair and (not has_feature_head or str((equipment["models"]["3:%d" % int(active[3])]
					as Dictionary).get("raceFeatures", "")) != "show")
				for node: Node in actor.find_children("*", "MeshInstance3D", true, false):
					var mesh := node as MeshInstance3D
					if mesh.name.to_lower() in ["hair", "scalp"]:
						var covered := covered_scalp if mesh.name.to_lower() == "scalp" else covered_hair
						expect(mesh.visible == (bool(initial_hair[mesh.get_instance_id()]) and not covered), race + " restores sculpted hair visibility")
					if mesh.name.to_lower() == "eyes":
						expect(mesh.visible, race + " preserves eyes")
				for node: Node in actor._native_skeleton.get_children():
					if node.name.begins_with("AppearanceHair_"):
						expect((node as Node3D).visible != covered_hair, race + " restores chosen hairstyle for circlets and unequip")
				transitions += 1
		actor.free()
		races += 1
		print("ARMOUR COVER: %s complete, %d failures" % [race, failures])
	expect(races == 16, "all sixteen races exercised")
	print("ARMOUR COVER: %d races, %d transitions, %d checks, %d failures" % [races, transitions, checks, failures])
	quit(1 if failures else 0)

func protected_face_disposition(instance: MeshInstance3D, arrays: Array,
		ids: PackedInt32Array, start: int, transform: Transform3D, fit: float,
		collar_cover: bool, bridge_surface: bool,
		profile_driven_bridge: bool, covered: bool, profiled_rig: bool = false) -> int:
	if instance.name.to_lower() not in ["body", "char1", "mesh_node"] or instance.skin == null:
		return FACE_DEFAULT
	var bones: PackedInt32Array = arrays[Mesh.ARRAY_BONES]
	var weights: PackedFloat32Array = arrays[Mesh.ARRAY_WEIGHTS]
	var vertices: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	var stride: int = bones.size()/vertices.size()
	var mean_weight := 0.0
	var all_corners_protected := true
	var lowest_corner_weight := 1.0
	for corner: int in range(3):
		var corner_weight := 0.0
		for slot: int in range(stride):
			var offset := ids[start+corner]*stride+slot
			var bone_name := instance.skin.get_bind_name(bones[offset])
			if bone_name.is_empty():
				var skeleton := instance.get_node(instance.skeleton) as Skeleton3D
				bone_name = skeleton.get_bone_name(instance.skin.get_bind_bone(bones[offset]))
			if bone_name in [&"Head", &"neck_01"]:
				corner_weight += weights[offset]
		mean_weight += corner_weight / 3.0
		all_corners_protected = all_corners_protected and corner_weight > .5
		lowest_corner_weight = minf(lowest_corner_weight, corner_weight)
	var center := (vertices[ids[start]] + vertices[ids[start+1]]
		+ vertices[ids[start+2]]) / 3.0
	center = (transform * center) / fit
	var neck_envelope := (collar_cover
		and covered
		and center.y > TorsoBodyCover.NECK_ENVELOPE_MIN_Y
		and absf(center.x) < TorsoBodyCover.NECK_ENVELOPE_HALF_WIDTH)
	# The generic shared bridge is the visible neck from the jaw down. Under a
	# collar its flared rows go: below 1.53 m behind the canonical neck_01
	# (0, 1.452, -.051) -> Head (0, 1.568, .011) axis and, except on Orun's
	# profiled rig, beside it below a line falling to 1.49 m at 60 degrees
	# from the front. In front of the axis the rest is the throat inside an
	# open collar and stays while every corner keeps a quarter of its
	# Head/neck_01 weight. Orun's fingerprint-pinned face profile still owns
	# its reviewed rows.
	var axis_z := lerpf(-.051, .011, (center.y - 1.452) / (1.568 - 1.452))
	if neck_envelope and bridge_surface and not profile_driven_bridge:
		if center.y < bridge_trim_y(center, not profiled_rig):
			return FACE_REMOVE
		if center.z >= axis_z:
			return FACE_RETAIN if lowest_corner_weight > .25 else FACE_REMOVE
	var protected_face := (bridge_surface or mean_weight > .5
		if profile_driven_bridge else all_corners_protected)
	if neck_envelope:
		return FACE_RETAIN if protected_face else FACE_REMOVE
	return FACE_RETAIN if protected_face else FACE_DEFAULT

## Number of faces in `expected` missing from `actual`, or -1 when `actual`
## is not an ordered subset of it (a face added, reordered or re-wound).
func dropped_faces(expected: PackedInt32Array, actual: PackedInt32Array) -> int:
	var placeholder := PackedInt32Array([0, 0, 0])
	if actual == placeholder and expected != placeholder:
		actual = PackedInt32Array()
	var cursor := 0
	var dropped := 0
	for start: int in range(0, expected.size(), 3):
		if (cursor < actual.size() and actual[cursor] == expected[start]
				and actual[cursor + 1] == expected[start + 1]
				and actual[cursor + 2] == expected[start + 2]):
			cursor += 3
		else:
			dropped += 1
	return dropped if cursor == actual.size() else -1

## The generic bridge's trim line in rest space: 1.53 m behind the canonical
## neck axis and, with `side`, falling beside it to 1.49 m at 60 degrees from
## the front.
func bridge_trim_y(point: Vector3, side: bool) -> float:
	var ahead := point.z - lerpf(-.051, .011, (point.y - 1.452) / (1.568 - 1.452))
	if ahead < 0.0:
		return 1.53
	var angle := rad_to_deg(atan2(absf(point.x), ahead))
	return -INF if not side or angle < 60.0 else lerpf(1.49, 1.53, (angle - 60.0) / 30.0)

## Positions are untouched except a cut neck bridge's hems, levelled in rest
## space: points within 3 cm of the trim line go onto it, points within 50
## degrees of the front move under 2 cm in height.
func hem_moves_only(before: PackedVector3Array, after: PackedVector3Array,
		transform: Transform3D, fit: float, may_move: bool) -> bool:
	if before.size() != after.size():
		return false
	for vertex: int in range(before.size()):
		if before[vertex] == after[vertex]:
			continue
		if not may_move:
			return false
		var point := (transform * before[vertex]) / fit
		var moved := (transform * after[vertex]) / fit
		if (absf(moved.x - point.x) > .0001 or absf(moved.z - point.z) > .0001
				or absf(point.x) >= .18):
			return false
		var trim_y := bridge_trim_y(point, true)
		var ahead := point.z - lerpf(-.051, .011, (point.y - 1.452) / (1.568 - 1.452))
		if trim_y > -INF:
			if absf(moved.y - trim_y) > .0001 or absf(point.y - trim_y) >= .03:
				return false
		elif absf(moved.y - point.y) >= .02 or absf(point.x) >= ahead * tan(deg_to_rad(50.0)):
			return false
	return true
