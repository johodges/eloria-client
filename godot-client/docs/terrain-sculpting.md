# Sculpt saved terrain

Open one of the twelve authored territory scenes. In **Territories**, turn on
**Sculpt terrain in 3D**, choose **Raise**, **Lower**, **Smooth**, or **Flatten**,
then drag the left mouse button over the active ground. Set the radius,
strength, and edge softness in the dock. For Flatten, enter a target Y height or
press **Pick** and click the desired terrain height. The cursor ring shows the
brush radius; a missed ray or protected border reports why it cannot paint.

Each drag is one undo step. **Escape** cancels a drag. Releasing the mouse,
switching scenes, or using a camera gesture ends or cancels it safely. Alt,
right mouse, and middle mouse remain camera controls. Asset placement and
terrain sculpting are mutually exclusive. **Ctrl+Z** and **Ctrl+Y** use the
scene's normal editor history; **Ctrl+S** saves the sculpt layer in the active
scene. The region root's **Bake continent authoring snapshot** button exports an
active-scene diagnostic. The normal continent build consumes the saved layer.

The brush changes a sparse saved layer above the original height grid. It does
not rewrite the imported base file or any neighboring scene. The true
ownership polygon protects a strip at least two terrain cells wide; the next
two cells fade the brush inward. This also protects diagonal border triangles.
References temporarily step aside during a drag so the current active terrain
is visible, then return when the drag ends. Save/reopen keeps the layer.

Terrain patches, road shaping, and river shaping still run after the sculpted
base. Existing objects and water do not automatically snap to edited ground;
inspect them after large height changes. Image heightmap import is not part of
this first sculpting phase.
