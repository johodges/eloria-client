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
	"lantern_reach": {"exposure": 1.6, "exposure_forward": 1.07},
}
## Forward+ draws the continent darker than the compatibility renderer does
## (Four Gates luminance 92 against 123, Amberwood 58 against 72, mostly its
## SSAO and linear lighting), so it takes this much more exposure everywhere.
## A per-map trim cannot close the gap on the continent, whose regions share
## one grade (Amberwood streams beside Four Gates); Lantern Reach's own trim
## is divided by it (1.2 before it, 1.07 after).
const FORWARD_EXPOSURE := 1.12

## Depth fog instead of the manifests' exponential haze. An exponential curve
## at the densities declared (0.0001-0.0007) is either invisible or a uniform
## wash, because a -60 degree view spans only about 20-40 m of depth. Depth fog
## leaves the player's surroundings clear and gathers only beyond them, where
## the low views reach the world's edge. It only replaces fog a manifest
## already enables. The sky layer (L5) then re-shapes it as the horizon haze
## (HAZE_BEGIN and after) on every map whose sky it paints.
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
## paving instead of lighter: a warm brick-brown cobble about 0.55 of the
## paving's display value, as the reference fountain court lays a warm, darker
## floor under its pale buildings. Lifted like a country road, the hub's
## avenue matched the plaza (168 against 178) and the square lost the dark
## ground its monument stood on; at 0.075 in the road's dusty stone it read as
## a taupe-grey concrete strip (Y 121, saturation 0.2) and the square went
## greige (value spread 35 against develop's 49). ROAD_UNDER_PAVING_TINT is its
## hue (about 22 degrees, display saturation about 0.4 after the grade).
## Paving is recognised by its authored tint (see PAVING_TINT_VALUE); a road
## counts as inside it this many metres in from the paving's bounds, so it
## darkens as it enters the square rather than at a line.
const ROAD_UNDER_PAVING_LUMA := 0.046
const ROAD_UNDER_PAVING_CHROMA := 1.0
const ROAD_UNDER_PAVING_TINT := Color(0.74, 0.52, 0.4)
const PAVING_INSET_METRES := 3.0
## An authored ground patch is pale stone paving when its tint is at least this
## bright and at most this saturated (the Four Gates crystal paving is #ccba9c,
## value 0.8, saturation 0.24). Soil (#ffa85c), leaf litter (#f29e52), the
## east forecourt's worn cobble (#ad9e82, value 0.68) and the yards are not.
const PAVING_TINT_VALUE := 0.75
const PAVING_TINT_SATURATION := 0.3
## The pale paving itself steps down a little and warms, so the square's
## floor is not the brightest thing in it (the paving came out at Y 175 under
## a cream monument base) and the warm cobble reads as part of it.
const PAVING_SURFACE_TINT := Color(0.87, 0.83, 0.75)
## A patch at least this bright (display value) and at most this saturated is
## worn cobble or stone (the east gate's forecourt, #ad9e82): drawn solid, not
## as a PATCH_OPACITY glaze, through which the grass beneath tinted its stone
## green-grey. The grass layer keeps cobble bare by the same test
## (GRASS_BARE_PATCH).
const COBBLE_TINT := Vector2(0.6, 0.35)
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
## After the first pass the trail still read pale sand in the compatibility
## renderer (199, 167, 92) and dull ochre in Forward+ (152, 122, 63), and the
## island lost the coastal gold that was its signature; the reference gold is
## about (215, 170, 60). Both take more chroma, Forward+ at the trail's full
## value (its exposure trim is lower); the compatibility renderer keeps it
## under AgX's highlight roll-off, which pales a brighter gold back to sand.
const GOLD_HUE := Vector2(35.0, 56.0)
const GOLD_SATURATION := 0.5
const GOLD_VALUE := 1.0
const GOLD_VALUE_COMPAT := 0.78
const GOLD_CHROMA := 1.45
const GOLD_CHROMA_COMPAT := 2.6
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
## The verge keeps this share of its texture's grain around the texture's
## mean colour; the painted mottle and variation carry its variety instead.
## Kept whole, the grass texture's fine grain came through the deeper verge
## and the AgX curve as a camouflage mottle, the frame's busiest texture
## after the grass beds (high-frequency energy 15 against 14 here, in the
## south gate's field).
const VERGE_GRAIN := 0.55
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
## Where a road runs through pale paving its band is a curb, darker.
const EDGE_BAND_PAVING := 0.45
const EDGE_BAND_FROM := 0.1
const EDGE_BAND_PUSH_METRES := 0.03

## Banks and cliffs darken with slope: from this world-up component of the
## surface normal (about 31 degrees) to this one (about 53), down to
## SLOPE_SHADE of their value. The terrain's facets change slope at straight
## cell edges, so shade that began at 20 degrees drew a gentle field's rise
## as a straight step across the frame (ten levels at the south gate).
const SLOPE_UP := Vector2(0.86, 0.6)
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
## Amberwood's earthy verge is deepened less than the default (0.9): at 0.8
## the wood's floor sank to olive mud under its crowns.
const GROUND_TRIMS := {
	"amberwood": {"path_luma": 0.1, "path_tint": Color(0.74, 0.62, 0.46),
		"verge_value_earth": 0.9},
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
## Now that the sun falls across the crown as one volume (CROWN_VOLUME) the
## light itself shades the underside, so the painted gradient under it is
## milder than the first pass's 0.6.
const CROWN_TOP := Color(1.16, 1.08, 0.92)
const CROWN_UNDER := Color(0.78, 0.82, 0.9)
const CROWN_UNDER_WARM := Color(0.8, 0.66, 0.62)
const CROWN_LIGHT_POWER := 0.7
## How much of a crown's shading normal is the ellipsoid its box holds rather
## than the leaf card's own. Card by card, the maple read as a heap of
## vermilion cards with dark edges, the reference's trees as a few top-lit
## lobes. Some of the card's own normal is kept so the leaves still catch the
## light one by one inside a lobe.
const CROWN_VOLUME := 0.6
## The volume normal leans this far up (added to the unit box position):
## taken straight off the box, a tall dark fir's normals faced sideways and it
## fell from luminance 74 to 52; leaning them all the way up (0.8) lit every
## crown flat and the maple read as a pink blob.
const CROWN_VOLUME_LIFT := 0.55
## Fake occlusion towards the crown's centre: at the centre of the crown's
## box the albedo is scaled by CROWN_CORE, reaching 1 at CROWN_CORE_EDGE of
## the way out to its shell. Leaves inside the crown and the gaps between its
## clumps read darker, which is what makes a clump read at all.
const CROWN_CORE := 0.84
const CROWN_CORE_EDGE := Vector2(0.25, 0.85)
## Painted clumps: a value mottle in mesh space, CROWN_LOBES of them across
## a crown's width, this far either side of the mean, so a crown lit as one
## volume still breaks into three to five lobes - lit masses with shaded gaps
## between them - as the reference trees do. A fixed size in metres could not
## do that: the kit's meshes are in their own units, scaled by their nodes.
const CROWN_LOBES := 3.5
const CROWN_CLUMP := 0.3
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
const TAME_CEILING := 0.95
const TAME_MAGENTA_FLOOR := -2.0
## The maple's hue is held near crimson (355-5 degrees) with the value, not
## the hue, carrying the top light: walked to 9 degrees on top it read coral.
const TAME_HUE_TOP := 0.0
const TAME_HUE_UNDER := -8.0
## Bright texels (display value from TAME_VALUE_FROM.x to .y) lose this much
## value, so a tamed crown's lit top stays a deep warm red or amber rather
## than a pale neon one. Lit card by card at 0.8 it took the maple from
## luminance 92 to 78 and Amberwood with it; lit as a volume the maple's top
## takes more sun, and above 0.8 AgX paled it to pink.
const TAME_VALUE := 0.8
const TAME_VALUE_FROM := Vector2(0.5, 0.9)

## Wind: a crown sways by up to this many metres at its top, weighted by the
## square of the height within the mesh, so the trunk's foot never moves; one
## cycle takes about 2 pi / CROWN_SWAY_SPEED seconds, each crown on its own
## phase. Gentle: the camera is 26 m away.
const CROWN_SWAY_METRES := 0.07
const CROWN_SWAY_SPEED := 1.1

## The occluder fade opens a hole round the player instead of blending the
## whole occluder (LookFade, look_fade_hole.gdshaderinc); its timing stays
## OccluderFade's (FADE_SECONDS). The hole is FADE_HOLE_METRES in radius across
## the view at the player's depth - at the default 26 m framing about 95
## pixels, a player and a stride of ground either side - or FADE_HOLE_SHARE of
## a wider occluder's width, up to FADE_HOLE_MAX_METRES (a giant canopy). Its
## rim is dithered over FADE_RIM_METRES or FADE_RIM_SHARE of the radius,
## whichever is wider, and it cuts only what stands in front of the player's
## chest or at most FADE_BEHIND_METRES behind it. Dithering the whole occluder
## at 35 % coverage covered up to a fifth of the frame in a one-pixel
## crosshatch (high-frequency energy 51 in the deep grove against the
## reference's 13-18).
const FADE_HOLE_METRES := 2.6
const FADE_HOLE_SHARE := 0.2
const FADE_HOLE_MAX_METRES := 6.5
const FADE_RIM_METRES := 0.4
const FADE_RIM_SHARE := 0.15
const FADE_BEHIND_METRES := 0.4

# --- Grass beds (layer L4) ---------------------------------------------------

## Grass grows around the camera's focus, out to GRASS_RADIUS metres, and its
## tufts shrink to nothing over the last GRASS_FADE_METRES, so the bed never
## ends in a line. The default framing (pitch -60, 26 m) shows about 45 by
## 35 m of ground, so 34 m reaches the frame's corners; the low views see past
## it, where the grass thins out. A 44 m bed spread the same budget over two
## thirds more ground the camera never shows, and its beds read as a scatter
## of single tufts.
const GRASS_RADIUS := 34.0
const GRASS_FADE_METRES := 8.0
## Placement is worked out in square tiles this many metres across, each
## GRASS_TILE_CELLS candidates a side (one every 0.62 m), and a tile is kept
## until the focus leaves it behind or the ground under it changes (a chunk
## or a neighbour streams in or out). Every candidate casts one ray down the
## walk collision, so a tile costs about 170 rays and 2 ms.
const GRASS_TILE_METRES := 8.0
const GRASS_TILE_CELLS := 13
## The focus has to move this far before the set of tiles is looked at again.
const GRASS_REFOCUS_METRES := 2.0
## Never more than this many tufts: the tiles nearest the focus fill first, so
## a budget that runs out thins the far edge, never the ground underfoot.
const GRASS_INSTANCE_BUDGET := 12000
## How long placement may take per frame, in microseconds: more while the
## ground the camera frames (GRASS_BARE_METRES around the focus) is still bare
## after a map load, a teleport or a chunk that changed under it, less while
## the bed only extends ahead of a walking player.
const GRASS_BUILD_USEC := 2000
const GRASS_BUILD_USEC_BARE := 6000
const GRASS_BARE_METRES := 24.0
## Tufts per square metre. Verge is the strip along a road's edge where its
## deck has run out (the edge band the ground layer darkens), the dense bed
## that frames every road in the reference frames. Open grass carries beds
## where a slow noise (GRASS_BED_METRES across) rises through GRASS_BED_EDGE,
## and a light scatter everywhere else, both scaled by how grassy the ground
## layer under them is.
## A bed has to cover its ground to read as one from the -60 degree camera:
## at 4.5 tufts a square metre the first capture showed single tufts, dark
## stars on the grass, with the ground between them. Between the beds there
## is only a sprinkle of tall tufts: at 0.25 a square metre the scatter's lone
## tufts were most of what the open fields showed, one- and two-pixel specks
## that doubled the frame's high-frequency energy; with none at all the low
## views lost the dry grass standing in their foreground. The bed's edge (the
## noise from GRASS_BED_EDGE.x to .y) is narrow, so grass gathers into beds
## with bare ground between them, and its fringe shrinks (GRASS_THIN_SCALE)
## rather than thinning out.
const GRASS_VERGE_DENSITY := 12.0
const GRASS_BED_DENSITY := 9.0
const GRASS_SCATTER_DENSITY := 0.04
const GRASS_BED_METRES := 7.0
const GRASS_BED_EDGE := Vector2(0.47, 0.6)
## A tuft on thin ground (low grassiness, a bed's fringe) is scaled down
## towards this. At 0.5 Amberwood's moss (half as grassy as a meadow) grew
## tufts too small to read from the low views.
const GRASS_THIN_SCALE := 0.7
## Most tufts a single candidate may carry, so a verge stays a bed of tufts
## rather than a pile of them.
const GRASS_TUFTS_PER_CELL := 6
## A road deck's coverage (its vertex alpha: 0 at its edge, 1 one strip in)
## from which it is verge, and from which it is road. The ground layer cuts
## the road at 0.5 with a 0.1 wobble, and a verge tuft's blades reach 0.4 m
## out from its foot, so grass stops well short of it: from 0.4 the tufts
## covered 6-11 % of the roads' own metric boxes, and from 0.3 they still
## stood a little way into Amberwood's pale camp deck.
const GRASS_VERGE_ALPHA := Vector2(0.02, 0.24)
## The verge bed feathers in over this much coverage from the deck's outer
## edge, with as much jitter, so it does not end in the straight line the
## deck's geometry ends on (a hard hedge edge at the east gate), and from
## coverage GRASS_VERGE_ROADSIDE.x up to the road it thins by
## GRASS_VERGE_ROADSIDE.y, so its tufts stand back from the road's edge.
const GRASS_VERGE_FEATHER := 0.14
const GRASS_VERGE_ROADSIDE := Vector2(0.12, 0.5)
## An authored patch (a yard, a forecourt, leaf litter) at or above
## LookProfile.PATCH_RIM coverage keeps this share of the grass, and its rim
## (from GRASS_PATCH_RIM_FROM up to PATCH_RIM) is verge. Pale paving keeps none
## from LookProfile.PAVING_RIM up. None: dark spiky tufts on Amberwood's
## copper leaf litter read as dirt specks, and yards are trodden ground.
const GRASS_ON_PATCH := 0.0
const GRASS_PATCH_RIM_FROM := 0.3
## A patch at least this bright (display value) and at most this saturated is
## worn cobble or stone, like paving if not as pale (the east gate's forecourt,
## #ad9e82): no grass where it covers the ground. Soil, dirt yards and leaf
## litter are warmer and keep GRASS_ON_PATCH.
const GRASS_BARE_PATCH := Vector2(0.6, 0.35)
## No grass within pale paving's bounds, nor this many metres beyond them:
## judged by its coverage, the grass came up through the one-cell seams
## between the Four Gates plaza's patches and along the rims of the avenue
## decks that cross it.
const GRASS_PAVING_MARGIN := 0.5
## A terrain road (the worn colour the exporter paints into the terrain's
## vertex colour, LookProfile.TERRAIN_ROAD_COLOUR) is road from this weight
## and verge from this one.
const GRASS_TERRAIN_ROAD := Vector2(0.25, 0.5)
## Grass stands on ground whose world-up normal component is at least the
## second value and thins out down to the first (about 39 to 26 degrees).
const GRASS_SLOPE_UP := Vector2(0.78, 0.9)
## How grassy each biome layer is, by a word in its texture's file name. The
## blend's layers differ from cell to cell (Four Gates' grass is layer 1 in
## one cell, Amberwood's layer 2 in another, beside alpine scree, snow crust
## and moor heather), so the textures are what say which is grass. A layer
## whose texture has none of these words counts GRASS_LAYER_DEFAULT.
const GRASS_LAYER_WORDS := {
	"ground-basecolor": 1.0, "grass": 1.0, "meadow": 1.0, "lawn": 1.0,
	"heather": 0.6, "moor": 0.6, "moss": 0.5, "forest-floor": 0.5,
	"gravel": 0.12, "mud": 0.2, "scree": 0.0, "snow": 0.0, "sand": 0.0,
	"rock": 0.0, "cliff": 0.0,
}
const GRASS_LAYER_DEFAULT := 0.3
## Maps outside the continent colour their ground by vertex colour (Lantern
## Reach's island is one mesh: green grass at value 0.45, a sand-gold trail
## at 0.82, and a one-vertex blend between, which the ground layer paints as
## trail from about its middle). Ground at the second value or brighter is
## path, between the two it is the verge along it, and below the first it is
## grass when its green leads red and blue by GRASS_VERTEX_GREEN. From 0.62
## the tufts stood on the trail's painted margin (up to 9 % of its metric box
## dark) and took the trail's path/ground ratio from 1.6 to 1.3; the verge is
## now only the blend's grassy foot.
const GRASS_VERTEX_PATH_VALUE := Vector2(0.46, 0.49)
const GRASS_VERTEX_GREEN := 0.06

## The tufts: GRASS_TUFTS blades each (4 to 6), in three sizes - short and
## splayed for the verge, mid-height for the beds, taller and upright for a
## few in each bed - each blade a tapered two-segment strip that arcs
## outward, so a tuft still reads as a star of strokes from the -60 degree
## camera. Every tuft is turned, scaled within GRASS_SCALE and tilted halfway
## to the ground. At 0.065 m a blade was one or two pixels wide at the 26 m
## framing, which with no anti-aliasing crawls as it sways; blades are wider
## and fewer (the three averaged 21 triangles a tuft, now 15), and the verge's
## are about a third shorter, with more spread in length, so a verge is a low
## bed rather than a hedge.
const GRASS_TUFTS := [
	{"blades": 6, "length": Vector2(0.2, 0.46), "splay": Vector2(20.0, 46.0),
		"width": 0.1, "spread": 0.1},
	{"blades": 5, "length": Vector2(0.36, 0.66), "splay": Vector2(16.0, 40.0),
		"width": 0.1, "spread": 0.08},
	{"blades": 4, "length": Vector2(0.52, 0.84), "splay": Vector2(8.0, 28.0),
		"width": 0.095, "spread": 0.06},
]
const GRASS_SCALE := Vector2(0.7, 1.1)
## A verge tuft stands on the road's dark edging band (EDGE_BAND), so its
## palette is taken down this far: a verge bed at the band's value frames the
## road, where at the open grass's value the east gate's read as a bright
## hedge along it.
const GRASS_VERGE_SHADE := 0.82
const GRASS_GROUND_TILT := 0.5
## Each region's grass, root to tip, as display (sRGB) colours: a root darker
## than the verge it grows from and a tip lighter and warmer, averaging about
## the verge's own value, so the bed reads as depth and light rather than as a
## paler carpet (roads stay the palest thing on the ground). Four Gates' lush green, Amberwood's dry straw and
## amber (its floor is half as bright as Four Gates' grass, so its grass is
## too), Lantern Reach's coastal green. The first entry is for any other map.
## The order is the shader's palette index; at most four. `value_compat` and
## `value_forward` trim a region's palette in one renderer, measured against
## its painted ground (tufts at 0.9-1.05 of the ground under them): Lantern
## Reach's tufts stood 1.2 times brighter than its grass in the compatibility
## renderer and crowded the trail's value step, and 0.7 times as bright in
## Forward+, where they read as dark speckle (Forward+ trims act on linear
## colour: 1.7 there is about 1.3 on screen).
const GRASS_PALETTES := [
	{"region": "", "root": Color(0.09, 0.15, 0.06), "tip": Color(0.52, 0.6, 0.28)},
	{"region": "four_gates", "root": Color(0.09, 0.17, 0.06), "tip": Color(0.52, 0.62, 0.28),
		"value_forward": 1.2},
	{"region": "amberwood", "root": Color(0.13, 0.1, 0.05), "tip": Color(0.56, 0.44, 0.23)},
	{"region": "lantern_reach", "root": Color(0.05, 0.14, 0.05), "tip": Color(0.4, 0.55, 0.22),
		"value_compat": 0.9, "value_forward": 1.7},
]
## The palettes' value in each renderer. The compatibility renderer lights
## the display-encoded colour, Forward+ its linear value with SSIL's bounce
## on top: at 1 in both, Forward+ drew Four Gates' tufts at luminance 125
## over grass at 83, the compatibility renderer at 99 over 118.
const GRASS_VALUE_COMPAT := 1.3
const GRASS_VALUE_FORWARD := 0.3
## And their chroma: the compatibility renderer's grade drove Four Gates'
## tufts to (64, 101, 20), a blue channel near zero, while Forward+ drew the
## same palette a grey olive (71, 78, 46).
const GRASS_CHROMA_COMPAT := 0.85
const GRASS_CHROMA_FORWARD := 1.35
## The root-to-tip blend's power (above 1, most of a blade is the root's
## colour and only its end lights up) and the vertex-colour shade at the root.
const GRASS_GRADIENT_POWER := 1.4
const GRASS_ROOT_SHADE := 0.75
## Every tuft's value moves by up to this much either way, and a slow noise
## (GRASS_TONE_METRES across) turns whole beds warmer or cooler by up to
## GRASS_WARM, so a field reads as painted patches rather than one colour. Both
## are mild: a tuft also takes the ground paint's own mottle at its foot, and
## at 0.1 the jitter alone made single tufts stand out as specks.
const GRASS_VALUE_JITTER := 0.05
const GRASS_TONE_METRES := 11.0
const GRASS_WARM := Color(1.05, 1.0, 0.9)
const GRASS_SPECULAR := 0.15
## Wind: the tips lean downwind by up to GRASS_WIND_METRES and sway on a wave
## GRASS_WIND_WAVE_METRES long that rolls across the field, swelling and
## easing with gusts. Directions are in the continent frame (x east, z south).
const GRASS_WIND_DIRECTION := Vector2(0.8, -0.6)
const GRASS_WIND_METRES := 0.1
const GRASS_WIND_SPEED := 1.7
const GRASS_WIND_WAVE_METRES := 6.5
const GRASS_GUST_SPEED := 0.37
## The render layer the grass draws on: the main camera's gameplay layer,
## which the map cameras do not render (the maps are navigation aids).
const GRASS_RENDER_LAYER := 2
## ELORIA_LOOK_GRASS_DEBUG=1 prints each finished build's placement census;
## =none grows no grass at all, for measuring the tufts against the bare
## painted ground under them (l4/diffpix.py).
const GRASS_DEBUG_VARIABLE := "ELORIA_LOOK_GRASS_DEBUG"

# --- Sky and haze (layer L5) -------------------------------------------------

## The painted sky starts from the region's own declared sky colours (after
## the hour has moved them, as DayNightBinder would), so Four Gates keeps its
## clear blue and Amberwood its dusky autumn sky. A map that declares no sky
## takes its colours from here; Lantern Reach declared only a dark background
## colour, which the grade lifted to a flat pale cyan wall above its sea. Any
## other map without a sky gets the binder's own defaults (3d7ec2, bcc9cd).
const SKY_FALLBACKS := {
	"lantern_reach": {"top": Color(0.16, 0.42, 0.8), "horizon": Color(0.66, 0.82, 0.9)},
}
## The reference skies are blue down to a thin warm pale haze at the horizon,
## where the manifests' horizons are cool grey-blue (Four Gates) or a dull
## warm grey (Amberwood). Daylight warms the sky's horizon colour only this far
## towards SKY_WARM (display colours), a warm cream, and the haze band (which
## is also the fog) SKY_HAZE_WARMTH further, lifted a little, so the far ground
## melts into light rather than into grey. The first capture warmed the whole
## horizon by 0.35: the sky above the haze went cream-grey, an overcast day.
const SKY_WARM := Color(1.0, 0.87, 0.68)
const SKY_HORIZON_WARMTH := 0.12
const SKY_HAZE_WARMTH := 0.45
const SKY_HAZE_LIFT := 0.1
## The zenith is taken this far towards a clear, deep blue, which lifts
## Amberwood's murky navy (0.15, 0.25, 0.42) and deepens Four Gates' blue
## (0.24, 0.45, 0.73). AgX and the grade's saturation pale a blue sky a long
## way: Four Gates' own zenith drew about (122, 166, 207), the low reference
## skies are nearer (70, 130, 210).
const SKY_ZENITH_DEEP := Color(0.08, 0.3, 0.78)
const SKY_ZENITH_DEPTH := 0.45
## The gradient from horizon to zenith: 1 - (1 - sin(elevation))^power, so the
## zenith's blue takes over soon above the haze: two thirds of it 10 degrees
## up. A low camera sees at most about 13 degrees of sky, and at 2.6 (a third
## there) that sky was the pale horizon's.
const SKY_GRADIENT_POWER := 6.0
## The haze band: in the sky it fades from exactly the haze colour at the
## horizon to none at this sine of elevation (about 6 degrees); below the
## horizon, where nothing has loaded or the world has ended, it carries on and
## gives way to the old ground colour by this sine (about 17 degrees). A map
## camera looking straight down still sees only that ground colour.
const SKY_HAZE_HEIGHT := 0.1
const SKY_HAZE_DEPTH := 0.3
## Brushed cumulus: four octaves of value noise on a flat cloud layer, the
## noise this many cells per unit of the layer's plane (larger, smaller
## clouds), stretched across the wind (x) by SKY_CLOUD_STRETCH so the masses
## read as horizontal brush strokes. The noise is pushed SKY_CLOUD_CONTRAST
## times further from its mean, then cut at SKY_CLOUD_THRESHOLD with a soft
## edge of SKY_CLOUD_SOFTNESS either side (about a quarter of the sky covered,
## a tenth solid), at most SKY_CLOUD_OPACITY opaque: uncut, most of the noise
## sits inside the soft edge and the clouds were one thin grey veil. A
## cloud is SKY_CLOUD_LIT, brighter than the sky, on its sun-facing side and
## towards the sky behind it at SKY_CLOUD_SHADE of its value in its core and
## underside. They fade in between the two elevations (sines) of
## SKY_CLOUD_BAND, above the haze. Shaded half-way to the sky, the first
## capture's clouds read as a grey overcast.
const SKY_CLOUD_SCALE := 2.2
const SKY_CLOUD_STRETCH := 0.5
const SKY_CLOUD_CONTRAST := 1.8
const SKY_CLOUD_THRESHOLD := 0.62
const SKY_CLOUD_SOFTNESS := 0.06
const SKY_CLOUD_OPACITY := 0.9
const SKY_CLOUD_LIT := Color(1.0, 0.97, 0.9)
const SKY_CLOUD_NIGHT := Color(0.3, 0.33, 0.42)
const SKY_CLOUD_SHADE := 0.94
const SKY_CLOUD_BAND := Vector2(0.03, 0.2)
## A warm glow round the sun: a wide halo and a tighter core, this colour over
## the sun's own light. At noon the sun stands 62 degrees up, out of every
## camera framing; it matters at dawn and dusk.
const SKY_SUN_GLOW := Color(1.0, 0.82, 0.55)
const SKY_SUN_HALO := 0.25
const SKY_SUN_CORE := 0.6
## The haze is depth fog in the haze colour, and it replaces the grade's fog
## (FOG_BEGIN and after). The grade's fog left the ground 70 % clear at 320 m,
## so wherever streaming stopped the ground ended in a hard line against the
## sky. This gathers from HAZE_BEGIN to HAZE_END along a smoothstep raised to
## HAZE_CURVE, up to HAZE_DENSITY: nothing in the default -60 degree framing
## (its far edge is about 50 m away: under 0.1 %), 6 % at 150 m, 31 % at
## 250 m, 59 % at 330 m and 75 % from 420 m. A map that declares denser fog
## gets more, as the grade did, so Amberwood stays mistier than the city. At
## 0.8 from 380 m the far Four Gates town beyond the south gate bleached into
## the haze at the -15 degree view: a landmark lost to hide the world's edge.
const HAZE_BEGIN := 40.0
const HAZE_END := 420.0
const HAZE_CURVE := 1.6
const HAZE_DENSITY := 0.75
const HAZE_DENSITY_PER_DECLARED := 100.0
const HAZE_DENSITY_MAX := 0.92
## How much of the haze also veils the sky itself, clouds and zenith alike.
## Little: the painted sky draws its own haze where it belongs, at the horizon.
const HAZE_SKY_AFFECT := 0.1
## ELORIA_LOOK_SKY_DEBUG=1 draws the painted sky flat magenta above the
## horizon and cyan below it, for counting how much of a capture is sky; =2
## leaves the clouds out; =3 and =4 draw the zenith's and the horizon's colour
## flat, for reading what AgX and the grade make of them.
const SKY_DEBUG_VARIABLE := "ELORIA_LOOK_SKY_DEBUG"

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

## The exposure trim for the renderer in use (FORWARD_EXPOSURE in Forward+).
static func renderer_exposure() -> float:
	return FORWARD_EXPOSURE if forward_plus() else 1.0

## The key light's warmth for the renderer in use.
static func sun_warmth() -> Color:
	return SUN_WARMTH_FORWARD if forward_plus() else SUN_WARMTH

## The depth fog's density at FOG_END for a manifest's exponential density.
static func fog_density(declared: float) -> float:
	return clampf(FOG_DENSITY + maxf(declared, 0.0) * FOG_DENSITY_PER_DECLARED,
		0.0, FOG_DENSITY_MAX)

## The sky colours (`top`, `horizon`) for a map that declares no sky.
static func sky_fallback(map_id: String) -> Dictionary:
	if SKY_FALLBACKS.has(map_id):
		return SKY_FALLBACKS[map_id]
	return {"top": Color("3d7ec2"), "horizon": Color("bcc9cd")}

## The haze's density at HAZE_END for a manifest's exponential density.
static func haze_density(declared: float) -> float:
	return clampf(HAZE_DENSITY + maxf(declared, 0.0) * HAZE_DENSITY_PER_DECLARED,
		0.0, HAZE_DENSITY_MAX)

## A region's ground trim on `key`, or `fallback` when it has none.
static func ground_value(region: String, key: String, fallback: Variant) -> Variant:
	var trims: Variant = GROUND_TRIMS.get(region)
	if trims is Dictionary:
		return (trims as Dictionary).get(key, fallback)
	return fallback
