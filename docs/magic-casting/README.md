# Magic casting prototype

Branch: `feature/magic-casting-prototype`, based on develop at `2191b7608`.

Run `test-magic-prepared.bat` for the recommended interaction, or
`test-magic-aimed.bat` for the explicit-target comparison. Both launch an
offline practice courtyard with the production spellbook, loadout model,
casting bar, targeting controller, and utility picker. No login is needed.
The mode selector on the casting bar switches between them during play.

Run `test-magic-live.bat` to use the prototype with the normal login screen.
Choose your server/account there. This is the actual game client: normal
server rules and resource consumption apply after login. For a local server,
the launcher accepts `-Server 127.0.0.1 -Port 2000`.

## What to compare

| Version | Targeted spell behavior |
| --- | --- |
| Prepared (recommended) | Casts on an eligible selected recipient. Otherwise arms a target click. |
| Aimed | Always arms a target click, even with someone selected. |

Self/Allies spells are immediate in both modes. Burst and Blink use a ground
preview followed by a click. Switching to another spell replaces targeting;
Escape or right clicking the world cancels. Selecting a recipient retains it
for subsequent casts. Changing mode never casts by itself.

Both versions provide twelve editable slots, independent power per slot,
family browsing, the effect/target comparison grid, and feedback beside the
cursor. The spellbook closes when a spell is launched, exposing the world.

## Five-minute evaluation

1. Select Tavin, then cast Heal Target twice. Compare Prepared and Aimed.
2. Cast Fire Burst near the wisp; move outside range and try again.
3. Arm Blink, switch to Heal Target, then cancel with Escape or right click.
4. Open the spellbook. Select a family, choose its target and power, then
   choose a slot and click **Assign to slot**. Alternatively drag a grid icon.
5. Right click a casting slot to edit its spell/power or clear it. Put the
   same spell into two slots at different powers; each keeps its own setting.
6. Close and reopen the launcher. Practice slots should be remembered.

Existing Alt+1–0, Alt+minus and Alt+equals bindings still cast the twelve slots.
Ctrl+S opens the book. The live client's Settings / Controls can rebind them;
the casting bar tooltips read the actual bindings. Its title bar is draggable.

## Draft boundaries

The offline courtyard simulates outcomes and provides unlimited materials.
It demonstrates selection, target retention, power and area placement; it is
not a balance simulation. Real costs, success/failure, targeting permissions,
and effects are evaluated by the existing server in live play. Ground previews
use the current server's 15-tile Chebyshev range and four-tile Burst radius;
they do not guarantee line of sight or a legal Blink landing. Automatic target
selection is conservative about friendly creatures; explicit targeting remains
available and the server makes the final decision.

The prototype uses a separate Godot user-data directory named
**Eloria Magic Prototype**. Loadouts are keyed by server, port and character;
the practice profile is separate. A slot's saved power is capped to the
server's current allowed power when casting. Both comparison modes share the
same loadout so changing mode does not change the spells being compared.

This local worktree shares artwork and imported textures with the existing
`eloria-client` checkout. The `.bat` files run the game directly; use those
launchers rather than importing the shared artwork through the editor.
The PowerShell launcher also accepts `-GodotPath` for a different installation
of the pinned Godot 4.7.2 runtime.

## Validation

`powershell -File tools/run-magic-prototype.ps1 -Check` runs the prototype
regressions without opening a game window. Logs and rendered review captures
are written under `godot-client/test-artifacts/magic-casting/`.

Verified with Godot 4.7.2: prototype loadout/casting regressions, spell-window
tests, magic-book UI tests, and world-input tests pass. Both batch launchers
were exercised with `-Check`. Practice views and the live client HUD were
rendered and inspected at 1280 × 720. Live gameplay against a logged-in server
has not been playtested as part of this draft.
