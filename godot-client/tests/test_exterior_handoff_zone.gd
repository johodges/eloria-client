extends SceneTree

## A surveyed road crossing is continuous within the interpolation slack of the
## seam, even when the continent frame's collar is only its two-metre
## threshold-floor extent; remote map changes remain cold.
var failures := 0

func _init() -> void:
	call_deferred("_run")

func _expect(ok: bool, message: String) -> void:
	if not ok:
		failures += 1
		push_error(message)
	else:
		print("PASS: ", message)

func _run() -> void:
	_expect(ExteriorRegionStream.continuous_crossing(true, 2.77, 2.0), "a crossing 2.77 m from a two-metre continent collar is continuous")
	_expect(ExteriorRegionStream.continuous_crossing(true, 7.9, 2.0), "a crossing inside the eight-metre slack is continuous")
	_expect(not ExteriorRegionStream.continuous_crossing(true, 8.0, 2.0), "a change eight metres from the seam is not continuous")
	_expect(not ExteriorRegionStream.continuous_crossing(true, 120.0, 2.0), "an admin teleport far from any seam is a cold load")
	_expect(ExteriorRegionStream.continuous_crossing(true, 30.0, 42.0), "the legacy 42 m collar keeps its whole approach continuous")
	_expect(not ExteriorRegionStream.continuous_crossing(false, 1.0, 42.0), "a ferry or visual-only link is never continuous")
	_expect(not ExteriorRegionStream.continuous_crossing(true, INF, 2.0), "an unknown crossing distance is never continuous")
	print("handoff zone test: %d failures" % failures)
	quit(1 if failures > 0 else 0)
