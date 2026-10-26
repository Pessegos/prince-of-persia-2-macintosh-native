# Native column arithmetic and offscreen serpent progression

Temple distance research exposed an overlooked mixed-width operation shared
by character-column and supporting-foot distance calculations. GetCharCol
4:3ad6 first subtracts22 from native X in a word. The callee5:48b0 extends
that argument before subtracting4 in its low word. For arguments0..3, the
32-bit dividend is65532..65535. Negative arguments preserve their original
upper sign-extension word, including the signed minimum boundary. A fresh
sign extension after subtraction is also incorrect.

The former runtime treated the subtraction as ordinary integer arithmetic
and did not normalize the earlier word subtraction. It differed at26 of
65,536 signed native X values. Four lie far outside the left edge of a
visible room: native X22..25 (scene X-185..-182). The native column/remainder
there is(1280,48),(1280,49),(1280,50),(1281,0). These are original quirks,
not proposed screen coordinates or legitimate in-room cell numbers.

`coordinates.character_column_parts` now implements that exact arithmetic.
The existing character_column API delegates to it; supporting-foot edge
distance and the ruins' cached column remainder use the same division.
Callers still choose the actor X or its frame-derived supporting-foot X.
No new helper silently chooses between those different coordinates.
Normal visible-room conversion remains unchanged.

## Independent native checks

`tools/probe_character_columns.py` executes GetCharCol and both-facing
GetDist1 for every signed native X:196,608 original calls. Only the native
division remainder may change in the complete A5 bank. No endpoint is
supplied or stubbed. The before report records26 mismatching coordinates;
the updated runtime agrees at all65,536, zero mismatches. Original output
SHA256 is`68d6f47aec708d11e2afda9d2086dadf5a719c267573006ea31ffccf91435d1e`.
Frames, foot-offset loading, cells, controllers and FrameAdv are excluded.

The earlier overnight exploratory serpent trace had four unresolved
differences after travelling past the left edge in level9 rooms1/18.
They disappear with the corrected column/remainder, without wall clamps or
hand-coded room rules. `tools/probe_serpent_progression.py` formalizes the
follow-up:19 actual spawn records,76 prepared stationary-Prince/alert traces,
180 repeated native controller/frame/animation/movement steps each.
All13,680 frames match, including generator mode, ordered sound requests
and seeded random draws. Trace-output SHA256:
`9e9387ccc2b29713df7d2ac6206ac7197c7e79281955fa97a1de544afb885dd9`.

The caller refresh is4:2a72 (frame **and supporting column**, as2:6512), not
just4:2a8e. Initial exploratory traces missing that caller step were invalid
fixtures and are not counted as production failures. The initializer,
cached idle Prince and constant alerts0/3 remain supplied. Existing native
animation harness boundaries provide resource handles, inert memory traps,
seeded RNG and draw/audio services. This is not native LOS, damage resolution,
room-bank persistence/Cut or a complete physically reachable FrameAdv trace.
It improves the demonstrated serpent progression; broader AI remains open.

```powershell
.venv\Scripts\python.exe -m tools.probe_character_columns --source ..\PoP2-Mac-Code-Recovery --output rendered\character_columns.json
.venv\Scripts\python.exe -m tools.probe_serpent_progression --source ..\PoP2-Mac-Code-Recovery --output rendered\serpent_progression.json
.venv\Scripts\python.exe -m unittest -q tests.test_coordinates tests.test_opponent_generation tests.test_terrain tests.test_ruins_ai tests.test_ruins_playtest
```

The174 focused tests pass. The earlier coordinate test that asserted scene
X-185 maps to-4 was based on the simplified arithmetic; its expectation now
uses independently executed original output1280. New regressions pin all
four offscreen boundary values, remainder/edge agreement and signed X wrap.
Full shared-desktop gameplay discovery passes2994 tests518.608s, with10
explicit desktop skips, after this shared arithmetic correction.
Original resources and detailed before/after reports remain local/ignored.
