# Start-screen scenes

Six silent, seamless 16-second Theora loops, 1600×900 at 30 fps, with JPEG stills.
`src/ui/login_backdrop.gd` plays one selected scene and releases the decoder when
entry is hidden. Low graphics quality uses the selected still. The picker saves
the stable scene ID under `[start_screen] backdrop` in `user://eloria_hud.cfg`.
Oldcraft Waygate is the default for a new player or an unknown saved ID.

The five regional paintings and motion were approved in the start-screen art
review. Oldcraft uses the existing `eloria_login_waygate_background.jpg`. Motion
was rendered locally with periodic displacement, lighting and particles; the
login and crest remain separate live controls. Reproduction scripts, sources,
MP4 previews and export validation are in the project workspace's
`concept_art/start-screen-backdrops/2026-10-09-motion-v2/` collection.
