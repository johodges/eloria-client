class_name LookProfile
extends RefCounted
## The frame-level look pass: its one switch and every constant it tunes.
##
## The pass is an experiment the owner asked to see before deciding on it, so
## nothing it adds may change what a player gets by default. Every layer asks
## `enabled()` first and does nothing unless the client was started with
## ELORIA_LOOK=1. With the variable unset or 0 the client is exactly develop.
##
## The constants live here, not beside the code that uses them, so the whole
## look can be read, compared and retuned in one place. They are tuned for the
## isometric camera's default framing (pitch -60, 26 m away). There four
## fifths of the frame is ground, so the grade matters more than the sky; only
## the low views (pitch -30 and -20) reach the horizon.

## The environment variable that turns the pass on.
const ENABLE_VARIABLE := "ELORIA_LOOK"
## Picks another tone curve for an A/B capture ("agx", "aces" or "filmic").
## Unset, the pass uses TONEMAP_CURVE.
const TONEMAP_VARIABLE := "ELORIA_LOOK_TONEMAP"

# --- Grade (layer L1) --------------------------------------------------------

## The tone curve every outdoor map is graded through. The manifests disagree:
## Lantern Reach declares Filmic with a white of 1, which clips every bright
## channel and is why its grass and trail read neon; Four Gates declares
## Filmic with a white of 9, which folds its pale stone into flat grey; and
## Amberwood declares nothing, so it falls back to a linear curve that leaves
## its ground dull and dark. One curve gives the three places one exposure
## language, and the continent's seams need one anyway: the lighting manifest
## blends between neighbours every 100 ms, but the curve is only chosen at
## bind, so a player who walked in from Four Gates saw Amberwood through Four
## Gates' curve and one who logged in there saw it linear.
##
## AgX, from a compatibility-renderer A/B at matched mid-grey: ACES had the
## most contrast but blew Four Gates' paving out (luminance 167 against 144)
## and crushed 3 % of Lantern Reach's low view to black; Filmic kept Lantern
## Reach's trail neon orange; AgX rolled the pale stone off softly, turned the
## trail to sand and the red maples towards copper, and crushed nothing.
const TONEMAP_CURVE := "agx"
## Each curve with the exposure that puts mid-grey near the same display
## value, so an A/B compares the curves' shapes rather than their brightness.
## AgX's contrast is its own; the other two shape contrast by their white.
## AgX carries all of the grade's contrast (see CONTRAST): 1.35 against its
## default 1.25 opens Amberwood's value spread from 26 to 33.
const TONEMAP_CURVES := {
	"agx": {"mode": Environment.TONE_MAPPER_AGX, "exposure": 1.15,
		"white": 1.0, "agx_white": 16.29, "agx_contrast": 1.35},
	"aces": {"mode": Environment.TONE_MAPPER_ACES, "exposure": 1.0,
		"white": 3.0},
	"filmic": {"mode": Environment.TONE_MAPPER_FILMIC, "exposure": 1.15,
		"white": 4.0},
}

## The adjustment's own contrast, left neutral. It is a straight line through
## display mid-grey applied to each channel after the curve, so it drives the
## smallest channel of a dark saturated colour to zero: at 1.08 the dark side
## of the red maples went from (32, 23, 16) to (16, 6, 1) and the navy slate at
## Four Gates' east gate to (2, 12, 25). Even 1.03 crushed 3 % of that frame.
## Raising AgX's own contrast instead gave the same value spread with those
## colours intact, because its curve eases into black rather than clipping.
const CONTRAST := 1.0
## Saturation for a map that declares none. Below 1 because the tone curve adds
## chroma: AgX's contrast acts on each channel apart, and at 1.0 it took
## Amberwood's orange leaf litter and Four Gates' lime grass most of the way to
## neon. At 0.9 Amberwood still measured 0.60 (the reference frames average
## 0.51).
const SATURATION := 0.86
## How much of a manifest's own saturation boost survives. Amberwood declares
## 1.3, which has never been visible because nothing enabled the adjustment;
## at full strength it turns the red maple kit neon. A third of it warms the
## autumn palette without that.
const SATURATION_BOOST_SHARE := 0.33

## The key light is warmed, not re-aimed: the continent's regions share one
## sun heading and a crossing must not turn it. Multiplied into whatever colour
## the manifest and the hour give it.
const SUN_WARMTH := Color(1.0, 0.98, 0.94)
## A little more key than the manifests give, and no more: at 1.1 the first
## capture bleached Four Gates' pale stone without shading anything better.
const SUN_ENERGY_SCALE := 1.04

## Shadows read cool against a warm key. Every outdoor manifest's ambient is
## lerped this far towards AMBIENT_COOL.
const AMBIENT_COOL := Color(0.56, 0.68, 0.92)
const AMBIENT_COOL_SHARE := 0.4
## On a map lit by its sky the ambient colour is inert: the manifests declare a
## cool grey-blue ambient but no `skyContribution`, so the sky is the whole
## ambient. Amberwood's sky has a warm grey horizon over a brown ground, which
## tints its shade brown. Keeping this share of the sky lets the cool colour
## reach the shade.
const AMBIENT_SKY_SHARE := 0.75
## The fill keeps its strength. Cutting it to 0.88 for contrast moved the
## captures' value spread by less than one step and only darkened the shade
## that SSAO already darkens in Forward+; the tone curve does that job better.
const AMBIENT_ENERGY_SCALE := 1.0

## Per-map trims on the exposure and saturation above. Only for a map that is
## never streamed beside another: a trim changes the moment the active map
## does, which on the continent would be a visible step at every crossing, so
## the continent's regions share one grade. Lantern Reach is an island reached
## only by boat. Its ground is saturated vertex colour that its old Filmic
## curve (white 1) lifted a long way; under the shared curve it went a fifth
## darker than any other place. Its saturation is left alone: AgX already
## pales the gold trail towards sand, and trimmed to 0.85 it went grey.
const MAP_TRIMS := {
	"lantern_reach": {"exposure": 1.35},
}

## Depth fog instead of the manifests' exponential haze. An exponential curve
## at the densities declared (0.0001-0.0007) is either invisible or a uniform
## wash, because a -60 degree view spans only about 20-40 m of depth. Depth fog
## leaves the player's surroundings clear and gathers only beyond them, where
## the low views reach the world's edge. It only replaces fog a manifest
## already enables.
const FOG_BEGIN := 38.0
const FOG_END := 320.0
const FOG_CURVE := 1.4
## The haze at FOG_END. A map that declares denser exponential fog gets more
## of it, up to FOG_DENSITY_MAX, so Amberwood stays mistier than the city.
const FOG_DENSITY := 0.3
const FOG_DENSITY_PER_DECLARED := 250.0
const FOG_DENSITY_MAX := 0.5
## How much of the distant haze takes the sky's colour rather than the fog's,
## so the far ground melts into the horizon instead of into grey.
const FOG_AERIAL_PERSPECTIVE := 0.55
const FOG_SKY_AFFECT := 0.25

## Contact shade under eaves, trees and props. Forward+ only (see
## `screen_space_effects()`), so they cost the compatibility renderer nothing.
const SSAO_RADIUS := 1.6
const SSAO_INTENSITY := 1.4
const SSAO_POWER := 1.4
const SSAO_DETAIL := 0.5
## Some occlusion reaches direct light too, or noon AO vanishes in the sun.
## More than this blacked out the coppice's eaves.
const SSAO_LIGHT_AFFECT := 0.1
## Bounce light from sunlit ground into the shade beside it. Forward+ only.
const SSIL_RADIUS := 4.0
const SSIL_INTENSITY := 0.6

## Only what is already brighter than white glows, and softly: sunlit pale
## stone and water glints, not the whole frame.
const GLOW_INTENSITY := 0.35
const GLOW_STRENGTH := 0.9
const GLOW_BLOOM := 0.0
const GLOW_HDR_THRESHOLD := 0.9
const GLOW_BLEND_MODE := Environment.GLOW_BLEND_MODE_SCREEN

# --- Ground (layer L2) -------------------------------------------------------

## The painted ground's value hierarchy. The reference frames read because
## their roads are the palest thing on the ground (a path is 1.25-1.72 times
## the luminance of the grass beside it); Four Gates' roads were darker than
## the grass they cross (0.5) and Amberwood's matched their floor (1.0). The
## values below act on linear albedo, before the light and the AgX curve, and
## the grade pulls chroma down by about 14 %, so they are authored a little
## richer than they would look in a paint program.
##
## A path is lifted towards this albedo luminance, never darkened, and never
## by more than PATH_LIFT_MAX. The worn-road decks the exporter lays over the
## ground are a saturated orange-brown of luminance 0.056 (measured: the
## shared ground texture under the worn tint #997a4f), below the biome grass
## beside them (0.17). Lifted to 0.28 and stripped to half their chroma they
## read as white concrete in every capture; 0.24 with two thirds of it is a
## warm tan cobble, 1.23 (compatibility) to 1.31 (Forward+) times the
## luminance of the grass at the east gate, the reference's lower margin.
const PATH_LUMA := 0.24
const PATH_LIFT_MAX := 6.0
## Paths warm slightly and keep this share of their chroma as they lift, so a
## brown track turns to warm dust rather than to orange. At 0.5 they went grey.
const PATH_WARMTH := Color(1.06, 1.0, 0.86)
const PATH_SATURATION := 0.65
## The authored ground patches (yards, forecourts, market aprons, and
## Amberwood's leaf litter) sit between the verge and the roads: lifted
## towards a lower luminance, by less, and with most of their chroma. Their
## albedo runs from 0.009 (a dark garden margin) to 0.24 (crystal sand); the
## leaf litter is 0.12, so it only brightens a little and stays copper.
const YARD_LUMA := 0.15
const YARD_LIFT_MAX := 3.0
const YARD_SATURATION := 0.85
## Ground whose albedo is already pale (paving, sand, the Lantern Reach gold
## trail) is a path's value by itself. Between these two luminances it moves
## from the verge treatment to being left as it is. Not for the biome blend,
## which is verge by definition: Four Gates mixes a pale limestone gravel into
## its grass, and protected as "pale" that grass stayed bright lime.
const PALE_LUMA := Vector2(0.16, 0.3)
## Grass, moss, forest floor: deeper and a little richer, so the paths have
## something to stand out against. Green grass deepens most, towards the
## reference's deep green; earthy verge (Amberwood's olive floor and moss,
## already dark at 0.05) least. Chosen by hue rather than by value: deepening
## bright verge harder, by value, turned a 5 % lighting step at a Four Gates
## chunk seam into a 13 % band, because the albedo there differs by more than
## the light shows. Hue does not change across it.
const VERGE_VALUE_GREEN := 0.66
const VERGE_VALUE_EARTH := 0.8
## The biome grass is already a saturated yellow-green (0.15, 0.19, 0.02
## linear), so it takes little extra chroma.
const VERGE_SATURATION := 1.08
## Low-frequency painterly variation in continent space: two octaves of value
## noise, the coarse one this many metres across. It breaks the flat fields
## and the hard edges of repeated texture patches. VARIATION is the value swing
## either side of the mean; VARIATION_HUE the warm/cool shift that goes with
## it (bright patches warmer, dark ones cooler, as sun and shade would).
const VARIATION_METRES := 16.0
const VARIATION := 0.2
const VARIATION_HUE := 0.06
## An authored patch's vertex alpha is its ground region's weight: the blend
## width at its edge and the region's opacity inside. Honoured as it stands it
## let the grass show through the Four Gates plaza, which develop draws solid,
## so the patch is solid from this weight up and only its rim feathers. A walk
## deck's vertex alpha is already just a rim (0 on the edge, 1 one strip in).
const PATCH_ALPHA_FULL := 0.35

## Paths keep a third of the variation: enough to wear, not enough to blotch.
const PATH_VARIATION_SHARE := 0.35
## Banks and cliffs darken with slope: from this world-up component of the
## surface normal (about 20 degrees) to this one (about 52), down to
## SLOPE_SHADE of their value.
const SLOPE_UP := Vector2(0.94, 0.62)
const SLOPE_SHADE := 0.72
## The continent exporter paints its worn roads into the terrain's vertex
## colour as this linear colour (0.49, 0.435, 0.315 in sRGB, over the grain
## divisor 0.92). The terrain shader treats vertex colour this close to it,
## relative to its length, as road.
const TERRAIN_ROAD_COLOUR := Color(0.2265, 0.1746, 0.0855)
const TERRAIN_ROAD_TOLERANCE := Vector2(0.12, 0.34)
## ELORIA_LOOK_GROUND_DEBUG=1 draws each painted class as a flat colour
## (terrain red, biome blend green, authored patch blue, walk deck magenta),
## =2 its weights (path red, yard green, pale blue) and =3 its reference
## luminance in steps (above 0.08, 0.12, 0.2), for checking what a metric box
## is measuring and what the shader sees.
const GROUND_DEBUG_VARIABLE := "ELORIA_LOOK_GROUND_DEBUG"

## True when the client was started with ELORIA_LOOK=1.
static func enabled() -> bool:
	return OS.get_environment(ENABLE_VARIABLE) == "1"

## True when the renderer has SSAO and SSIL. Only Forward+ does; the others
## ignore the settings but warn about them, so they are not set there at all.
static func screen_space_effects() -> bool:
	return RenderingServer.get_current_rendering_method() == "forward_plus"

## The tone curve in use: TONEMAP_CURVE unless an A/B capture names another.
static func tonemap_curve() -> Dictionary:
	var requested := OS.get_environment(TONEMAP_VARIABLE).to_lower()
	if TONEMAP_CURVES.has(requested):
		return TONEMAP_CURVES[requested]
	return TONEMAP_CURVES[TONEMAP_CURVE]

## The saturation to grade a map with, from what its manifest declares.
static func saturation(declared: float) -> float:
	return SATURATION * (1.0 + (declared - 1.0) * SATURATION_BOOST_SHARE)

## A map's trim on `key` ("exposure" or "saturation"); 1 for most maps.
static func map_trim(map_id: String, key: String) -> float:
	var trims: Variant = MAP_TRIMS.get(map_id)
	if trims is Dictionary:
		return float((trims as Dictionary).get(key, 1.0))
	return 1.0

## The depth fog's density at FOG_END for a manifest's exponential density.
static func fog_density(declared: float) -> float:
	return clampf(FOG_DENSITY + maxf(declared, 0.0) * FOG_DENSITY_PER_DECLARED,
		0.0, FOG_DENSITY_MAX)
