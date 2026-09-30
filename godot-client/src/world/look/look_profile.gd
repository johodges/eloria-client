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
## the manifest and the hour give it. It turns Four Gates' lime grass towards
## chartreuse (hue 81 to 69-71 degrees); holding its blue back to 0.97 fixed
## little of that and cooled every frame (red minus blue down 9 levels) and
## greyed the roads, so the grass is turned back in the ground paint instead
## (LookProfile.VERGE_GREEN_RED).
const SUN_WARMTH := Color(1.0, 0.98, 0.94)
## Forward+ lights in linear light and adds bounce (SSIL) from warm ground, so
## the same warmth landed its roads rose (hue 17-29 degrees against 43 in the
## compatibility renderer) and its grass mustard. It takes a milder warmth.
const SUN_WARMTH_FORWARD := Color(1.0, 0.99, 0.97)
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
## darker than any other place, and the ground layer's deeper verge took it
## darker again (luminance 104 on develop, 86); 1.6 brings it back to about
## the reference's 98. Its saturation is left alone: AgX pales the gold trail
## towards sand, and trimmed to 0.85 it went grey. The gold is restored in the
## ground paint instead (LookProfile.GOLD_HUE), not by the grade. Forward+
## renders the island a quarter brighter than the compatibility renderer
## (luminance 123 against 94 at 1.6: its sea goes pale turquoise and its
## grass pale), so a key with a `_forward` suffix trims that renderer alone.
const MAP_TRIMS := {
	"lantern_reach": {"exposure": 1.6, "exposure_forward": 1.2},
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
## A path is repainted rather than lifted: its texture's grain is kept, but
## its value and colour are set outright, so a road reads the same wherever
## the exporter's worn tint happens to sit. The worn-road decks are a
## saturated orange-brown of luminance 0.056 (the shared ground texture under
## the worn tint #997a4f); lifting that colour kept its red hue, which Forward+
## lit rose and mauve and the compatibility renderer grey. PATH_LUMA is the
## albedo luminance a road is painted at; a region whose verge is much darker
## than Four Gates' grass trims it (GROUND_TRIMS), because the path/ground
## ratio is what the eye reads, and 0.24 over Amberwood's floor (0.04) made its
## paths cream decals 2.2-2.4 times the floor's luminance. Never more than
## PATH_LIFT_MAX times the source.
const PATH_LUMA := 0.24
const PATH_LIFT_MAX := 6.0
## The hue a road is painted in, as an sRGB colour whose own brightness is
## ignored: warm dust and pale stone at about 36 degrees, not the red the worn
## tint lifts to. PATH_CHROMA is how much of this colour's chroma it keeps (1
## all of it, 0 grey).
const PATH_TINT := Color(0.82, 0.68, 0.52)
const PATH_CHROMA := 1.0
## The compatibility renderer lights its gamma-encoded albedo, which washes a
## painted colour's chroma out (the same road measured sat 0.24-0.34 there and
## 0.4 in Forward+), so painted tints carry this much more chroma on it.
const COMPAT_CHROMA := 1.2
## A road keeps its texture's grain, raised to this power, so a worn track
## reads as trodden stones and dust rather than as a poured surface (internal
## luminance spread 9-18 against about 33 on the reference roads).
const PATH_DETAIL := 1.8
## And a fine mottle the size of a cart's width: this many metres across,
## this far either side of the mean.
const PATH_FINE_METRES := 1.5
const PATH_FINE := 0.12

## A road through pale paving (the Four Gates hub square) goes darker than the
## paving instead of lighter: a mid-value warm cobble about 0.65 of the
## paving's display value, as the reference city's gate road is (Y about 126
## against its pale courts). Lifted like a country road, the hub's avenue
## matched the plaza (168 against 178) and the square lost the dark ground its
## monument stood on. Paving is recognised by its authored tint (see
## PAVING_TINT_VALUE); a road counts as inside it this many metres in from the
## paving's bounds, so it darkens as it enters the square rather than at a line.
const ROAD_UNDER_PAVING_LUMA := 0.075
const ROAD_UNDER_PAVING_CHROMA := 0.9
const PAVING_INSET_METRES := 3.0
## An authored ground patch is pale stone paving when its tint is at least this
## bright and at most this saturated (the Four Gates crystal paving is #ccba9c,
## value 0.8, saturation 0.24). Soil (#ffa85c), leaf litter (#f29e52), the
## east forecourt's worn cobble (#ad9e82, value 0.68) and the yards are not.
const PAVING_TINT_VALUE := 0.75
const PAVING_TINT_SATURATION := 0.3
## At most this many paving patches are handed to a root's roads, the largest
## first; a chunk holds two or three.
const PAVING_RECTS_MAX := 8

## The authored ground patches (yards, forecourts, market aprons, and
## Amberwood's leaf litter) keep their own colour and are lifted only a
## little: towards this luminance, by at most YARD_LIFT_MAX. Their albedo runs
## from 0.007 (a dark root margin) to 0.24 (crystal paving); the leaf litter
## is 0.12 and stays exactly the copper the authors gave it. The first pass
## lifted them three times, stripped a sixth of their chroma and warmed them
## like a road, which turned the leaf litter peach and a coppice workyard rust.
const YARD_LUMA := 0.12
const YARD_LIFT_MAX := 2.0
const YARD_SATURATION := 0.9
## A patch (not paving) is a glaze over the ground beneath rather than a
## sticker: drawn solid over its footprint, the leaf litter under the deep
## grove's player became a saturated orange oval, the brightest shape in a dark
## frame. Its region weights (mean 0.33) say it is meant as a wash.
const PATCH_OPACITY := 0.78
## Ground whose albedo is already pale (paving, sand, the Lantern Reach gold
## trail) is a path's value by itself. Between these two luminances it moves
## from the verge treatment to being left as it is. Not for the biome blend,
## which is verge by definition: Four Gates mixes a pale limestone gravel into
## its grass, and protected as "pale" that grass stayed bright lime.
const PALE_LUMA := Vector2(0.16, 0.3)
## Pale ground in this hue window (sRGB degrees) and at least GOLD_SATURATION
## saturated is gold: Lantern Reach's trail. AgX rolls a bright saturated
## colour off towards white, which turned the island's gold thread to sand
## (241, 202, 81 became 188, 157, 90), so gold is painted a little darker and
## richer, where the curve leaves its chroma alone. The compatibility renderer
## washes painted chroma out and takes more: at 1.5 in both, Forward+ drove
## the trail to 159, 120, 15 while the compatibility renderer landed 201,
## 166, 85.
const GOLD_HUE := Vector2(35.0, 56.0)
const GOLD_SATURATION := 0.5
const GOLD_VALUE := 0.8
const GOLD_CHROMA := 1.1
const GOLD_CHROMA_COMPAT := 1.5
## Grass, moss, forest floor: deeper and a little richer, so the paths have
## something to stand out against. Green grass deepens most, towards the
## reference's deep green; earthy verge (Amberwood's olive floor and moss,
## already dark at 0.05) least. Chosen by hue rather than by value: deepening
## bright verge harder, by value, turned a 5 % lighting step at a Four Gates
## chunk seam into a 13 % band, because the albedo there differs by more than
## the light shows. Hue does not change across it. Four Gates' lime fields
## sat at display value 0.6 against the reference greens' 0.33, and at the
## first pass's 0.66 its south gate highway still read no paler than them.
const VERGE_VALUE_GREEN := 0.42
const VERGE_VALUE_EARTH := 0.8
## The biome grass is already a saturated yellow-green (0.15, 0.19, 0.02
## linear), so it takes little extra chroma.
const VERGE_SATURATION := 1.08
## Green verge loses a little red, which turns the biome's yellow-green (hue
## about 70 degrees under the warm key, chartreuse) back towards grass green.
const VERGE_GREEN_RED := 0.84
## A painted mottle on the verge only, finer than the variation below: the
## south gate's field was 64 % of its frame in one flat lime.
const VERGE_FINE_METRES := 4.0
const VERGE_FINE := 0.12
## Low-frequency painterly variation in continent space: two octaves of value
## noise, the coarse one this many metres across. It breaks the flat fields
## and the hard edges of repeated texture patches. VARIATION is the value swing
## either side of the mean; VARIATION_HUE the warm/cool shift that goes with
## it (bright patches warmer, dark ones cooler, as sun and shade would).
const VARIATION_METRES := 16.0
const VARIATION := 0.2
const VARIATION_HUE := 0.06
## Paths keep a third of the variation: enough to wear, not enough to blotch.
const PATH_VARIATION_SHARE := 0.35

## Where a walk deck or authored patch ends. The exporter writes each one's
## coverage into its vertex alpha (a road: 0 on the edge, 1 one strip in; a
## patch: its region's weight), which the imported material never read, so on
## develop both end in hard steps along the terrain cells. Honoured as a
## linear ramp it drew 1-3 m airbrushed rims around sharp textures, two styles
## at once. Instead the coverage is cut at a threshold with a narrow smooth
## step (x: threshold, y: half-width of the step) and a noise wobble (z) about
## RIM_NOISE_METRES across, a broken brush edge rather than a feather.
## Roads cut at the middle of their rim strip.
const DECK_RIM := Vector3(0.5, 0.06, 0.1)
## Patches keep their region's footprint as the exporter weighted it: the
## east forecourt's weight is under 0.35 over half its area, which it means as
## grass, and forcing it solid from there turned that grass into cobble.
const PATCH_RIM := Vector3(0.42, 0.06, 0.1)
## Paving keeps almost all of its geometry, as develop draws it: its low
## weights are where two plaza patches meet, and cut there the grass beneath
## showed through the square as a green veil.
const PAVING_RIM := Vector3(0.12, 0.04, 0.05)
const RIM_NOISE_METRES := 0.9
## Every road is edged: on the far side of its rim, where its coverage has
## run out but its geometry has not (vertex alpha from EDGE_BAND_FROM up to the
## rim), whatever lies under it is darkened by EDGE_BAND (value x0.72) - the
## dark verge that frames the reference's roads, and a curb where a road
## meets paving. The band is drawn EDGE_BAND_PUSH_METRES behind its own plane,
## so where two coplanar road decks overlap the other road hides it rather
## than taking a dark line across its middle.
const EDGE_BAND := 0.28
const EDGE_BAND_FROM := 0.1
const EDGE_BAND_PUSH_METRES := 0.03

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

## Per-region ground trims over the constants above, keyed by the region's id
## (a continent chunk's `<region>__chunk_<x>_<z>` names its region). Unlike a
## grade trim these are safe on the continent: they are baked into a chunk's
## painted materials when it loads, so they change where the ground changes (at
## the region's border, where the biome changes too), never when the player
## crosses it.
##
## Amberwood's floor is moss and olive litter at albedo 0.04-0.05, a sixth of
## Four Gates' grass, so its roads are painted a half as bright and in the
## wood's ochre-tan rather than in pale stone. Lantern Reach's grass came out
## of the verge treatment a deep saturated green (sat 0.77 in its ground box,
## blue channel 17), above the reference's 0.51: it keeps more of its value
## and none of the extra chroma.
const GROUND_TRIMS := {
	"amberwood": {"path_luma": 0.1, "path_tint": Color(0.74, 0.62, 0.46)},
	"lantern_reach": {"verge_value_green": 0.82, "verge_saturation": 0.92},
}

## ELORIA_LOOK_GROUND_DEBUG=1 draws each painted class as a flat colour
## (terrain red, biome blend green, authored patch blue, walk deck magenta),
## =2 its weights (path red, yard green, pale blue) and =3 its reference
## luminance in steps (above 0.08, 0.12, 0.2), for checking what a metric box
## is measuring and what the shader sees.
const GROUND_DEBUG_VARIABLE := "ELORIA_LOOK_GROUND_DEBUG"

# --- Foliage and fade (layer L3) ---------------------------------------------

## What counts as a crown. The authored trees split crown and trunk into
## separate nodes (Tree_<n>_<species>_Canopy / _Wood), and every crown there
## draws with one of these alpha-cut leaf materials; the trunks' bark is never
## painted. The kit's Meshy trees and shrubs are one surface with one atlas
## material for crown and trunk together, so they are recognised by the
## species words in their node names (kit-crimson-maple-3, kit-dark-fir-12)
## and split inside the shader by height (see CROWN_FLOOR).
const CROWN_MATERIALS := ["foliage_amber", "foliage_rust", "foliage_gold", "undergrowth"]
## Kit species with a trunk under a crown.
const KIT_TREE_WORDS := ["tree", "maple", "oak", "fir", "pine", "birch", "sapling", "cypress"]
## Kit plants that are foliage from the ground up.
const KIT_SHRUB_WORDS := ["shrub", "hedge", "fern", "undergrowth", "bramble", "bracken", "reed", "juniper"]
## Kit plants whose colour is the point (blossom), so their hue is not tamed.
const KIT_UNTAMED_WORDS := ["flower"]
## A foliage mesh this much wider than it is tall, and wider than
## CROWN_MERGED_METRES, is many plants merged into one mesh (Lantern Reach's
## wind pines are one 74 m mesh): its bounds say nothing about any one crown,
## so it is left as it is.
const CROWN_MERGED_RATIO := 2.5
const CROWN_MERGED_METRES := 20.0

## Where a kit tree's crown begins, as a fraction of the mesh's height. Below
## it is trunk. Measured by sampling each kit tree's atlas at its vertices: the
## crimson maple's lowest fifth is bark (saturation 0.25, value 0.36) and the
## rest crown (0.8-0.93, 0.71-0.81); the great amber oak, the autumn maple and
## the dark fir split at the same fifth. Saturation alone does not split
## them: the resin-tapped pine's bark is as saturated (0.52) as its needles
## (0.45). Shrubs are crown from the ground up.
const CROWN_FLOOR := 0.2
## The painted top light: a crown's top is warmed and lifted, its underside
## (and the trunk beneath it) cooled and deepened, across the crown's height
## in mesh space, eased by CROWN_LIGHT_POWER (below 1, the light holds most of
## the crown and falls off towards its underside). Linear multipliers on
## albedo, before the sun; the grade adds its own warm key and cool shade on
## top. The first capture (under 0.5, 0.56, 0.68; core 0.62; power 0.8) took
## the dark firs from luminance 83 to 51 and, by adding blue under a red crown,
## turned the crimson maple's shaded side pink. So the value is redistributed
## rather than taken away, and a tamed (warm, saturated) texel's underside
## goes towards CROWN_UNDER_WARM, a deep red-brown, instead of blue.
const CROWN_TOP := Color(1.16, 1.08, 0.92)
const CROWN_UNDER := Color(0.6, 0.65, 0.76)
const CROWN_UNDER_WARM := Color(0.62, 0.5, 0.46)
const CROWN_LIGHT_POWER := 0.7
## Fake occlusion towards the crown's centre: at the centre of the crown's
## box the albedo is scaled by CROWN_CORE, reaching 1 at CROWN_CORE_EDGE of
## the way out to its shell. Leaves inside the crown and the gaps between its
## clumps read darker, which is what makes a clump read at all.
const CROWN_CORE := 0.72
const CROWN_CORE_EDGE := Vector2(0.25, 0.85)
## Painted clumps: a value mottle in mesh space, this many metres across,
## this far either side of the mean, so a flat-shaded blob breaks into lit
## and shaded masses.
const CROWN_CLUMP_METRES := 2.2
const CROWN_CLUMP := 0.16
## Every crown is a little different: its hue turns by up to this many
## degrees and its value by this fraction either way, from a hash of its
## position in its region (not in the world, which a seam crossing rebases).
const CROWN_JITTER_HUE := 7.0
const CROWN_JITTER_VALUE := 0.1
## The jitter comes in this many variants, so the copies of one kit tree
## share that many painted materials rather than one each.
const CROWN_JITTER_VARIANTS := 8

## The autumn crowns' tame. The kit's crimson maple is saturation 0.9 at hue
## 300-349 (magenta, not crimson) and its great amber oak 0.9 at hue 25: flat
## neon blobs beside the painted canopies (0.45-0.6). A warm, saturated texel
## (hue in the window below, in sRGB degrees, above TAME_FROM saturation) has
## its saturation compressed past TAME_KNEE towards TAME_CEILING, its magenta
## pulled towards crimson (no bluer than TAME_MAGENTA_FLOOR degrees, i.e.
## 358), and its hue walked across the crown: towards scarlet and amber at the
## top (TAME_HUE_TOP degrees) and towards maroon underneath (TAME_HUE_UNDER).
## Hues are judged on display-encoded colour in both renderers. Compressed to
## 0.68 at the same value, the maple went salmon (luminance 92 to 100,
## saturation 0.80 to 0.67): the tame keeps more chroma and takes value off
## the bright texels instead, which is what a painter deepening a neon red
## would do.
const TAME_HUE := Vector2(268.0, 60.0)
const TAME_FROM := Vector2(0.4, 0.6)
const TAME_KNEE := 0.55
const TAME_CEILING := 0.8
const TAME_MAGENTA_FLOOR := -2.0
const TAME_HUE_TOP := 9.0
const TAME_HUE_UNDER := -5.0
## Bright texels (display value from TAME_VALUE_FROM.x to .y) lose this much
## value, so a tamed crown's lit top stays a deep warm red or amber rather
## than a pale neon one.
const TAME_VALUE := 0.8
const TAME_VALUE_FROM := Vector2(0.5, 0.9)

## Wind: a crown sways by up to this many metres at its top, weighted by the
## square of the height within the mesh, so the trunk's foot never moves; one
## cycle takes about 2 pi / CROWN_SWAY_SPEED seconds, each crown on its own
## phase. Gentle: the camera is 26 m away.
const CROWN_SWAY_METRES := 0.07
const CROWN_SWAY_SPEED := 1.1

## The occluder fade dithers instead of blending (LookFade). It has no
## constants of its own: its timing and opacity stay OccluderFade's
## (FADE_SECONDS, FADED_ALPHA and a manifest's occluderFadeAlpha).

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
		var map_trims := trims as Dictionary
		if forward_plus() and map_trims.has(key + "_forward"):
			return float(map_trims[key + "_forward"])
		return float(map_trims.get(key, 1.0))
	return 1.0

## True in the Forward+ renderer, which some trims tell apart (see
## SUN_WARMTH_FORWARD).
static func forward_plus() -> bool:
	return RenderingServer.get_current_rendering_method() == "forward_plus"

## The key light's warmth for the renderer in use.
static func sun_warmth() -> Color:
	return SUN_WARMTH_FORWARD if forward_plus() else SUN_WARMTH

## The depth fog's density at FOG_END for a manifest's exponential density.
static func fog_density(declared: float) -> float:
	return clampf(FOG_DENSITY + maxf(declared, 0.0) * FOG_DENSITY_PER_DECLARED,
		0.0, FOG_DENSITY_MAX)

## A region's ground trim on `key`, or `fallback` when it has none.
static func ground_value(region: String, key: String, fallback: Variant) -> Variant:
	var trims: Variant = GROUND_TRIMS.get(region)
	if trims is Dictionary:
		return (trims as Dictionary).get(key, fallback)
	return fallback
