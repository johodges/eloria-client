# Territory authoring workspace

The **Territories** dock keeps one saved authored territory active while showing
other territories as read-only spatial references. Sunmane Steppe and Amethyst
Barrens become editable when both their saved scene and authoring specification
exist. Every other exterior territory is labeled **Published reference only**.

Use **Open** to switch to an editable territory. The action opens its native
scene tab through Godot, so an already open tab and its unsaved changes remain
under the editor's normal save/prompt behavior. The workspace never reloads,
rewrites, or auto-saves an inactive scene.

Select any number of rows under **Read-only references**. Saved authored source
is preferred when available; otherwise the dock loads the territory's current
published `world.glb`. The row and tooltip identify the source kind, revision,
path, and digest. Reference placement uses:

```text
reference position = reference continent translation - active continent translation
```

The displayed terrain is clipped against the current manifest ownership
polygon. An authored scene is hidden if its saved ownership hash does not match
that polygon. The cyan line is the ownership boundary. The clip changes only
temporary editor display meshes; it does not alter either territory's terrain,
paths, objects, gameplay, or ownership.

Reference nodes are internal and ownerless. They do not appear as editable
gameplay controls, cannot receive Map Assets palette placement, and are excluded
from saved scene bytes and continent-authoring snapshots. **Hide all** removes
the references and restores the active generated terrain preview to its prior
visibility.

Saving and **Bake continent authoring snapshot** always apply only to the active
scene. Boundary alignment remains an explicit review and validation task; the
workspace does not reshape a neighbor or reconcile seams automatically.
