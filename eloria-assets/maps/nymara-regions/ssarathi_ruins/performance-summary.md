# Ssarathi Ruins performance summary — September 2026

Measured from the current exporter output. Collision counts in performance.json
describe the initial build; world.json contains the authoritative corrected grid.

| Metric | Full package | LOD2 |
| --- | ---: | ---: |
| GLB bytes | 26,215,864 | 16,473,376 |
| Unique triangles | 481,289 | 431,630 |
| Instanced triangles | 1,847,337 | 978,596 |
| Nodes | 7,352 | 3,534 |

Full export: 2,755 placements, 42 materials and
104 embedded images. The exporter reports
256.9 MiB of uncompressed textures.
LOD2 reduces instanced triangles by 47.0% and GLB bytes by 37.2%.

This pass adds 1,406,480 bytes and
26,681 instanced triangles to the previous full
package. Surveyed bridges, working docks and the cistern platform account for
the added route geometry; the two redundant southern bridges and obstructing
dressing were removed.

The historical 1.5 million visible-triangle and 512 MiB texture guidelines are
not a frame-time guarantee. The full export remains above that triangle count;
LOD2 is below it. No GPU profiling or draw-call timing was performed. See
[layout-review.md](layout-review.md) for reachability, geometry and capture proof.
