# Temple music preparation (2026-11-04)

The user could not assess the horse scene's music ending because temple
gameplay was silent. The missing part was audio preparation, not a new
ambient controller: the MIDI files and cue metadata were imported, but the
renderer whitelist omitted all temple songs. AudioEngine.available therefore
rejected their requests. This fix adds their prepared WAVs and detects the
incomplete older cache when Temple.rsrc is installed.

## Existing rules retained

PlayAmbient `5:4fd0-50c2` reads the level's environment bank and cell group.
The shared A5 tables are starts at `-0x40fe`, counts at `-0x40e2`, and combat
group at `-0x40c6`. Levels10-13 have environment2, with cell groups at LEVL
`0x424a`. Their bank2 starts are200/216/232, counts15/15/3, combat group2.
Rnd `17:6e06` is inclusive: these are16/16/4 songs, including the pool tails.

| Selection | Prepared cues |
| --- | --- |
| Cell group0 | 200-215, Temple1A-P |
| Cell group1 | 216-231, Temple2A-P |
| Combat group2 | 232-235, Temple3A-D |

The47-song preparation set also includes187-189,194,237-238 and250-254:
the associated level/opponent/death/flaming-sword/altar/shadow music. Making
these files available does not add or certify every original trigger. It
allows the already-implemented requests to reach the existing audio engine.
The frame order, cue arbitration, room-group table, random selection,
foreground protection and native imported instruments are unchanged.

The cue list lives in `pop2/music_cues.py`, shared by the importer and launcher
without importing the synthesis tools during installation validation. New
imports render the songs using the existing renderer and fixed headroom.
An installed Temple.rsrc with missing prepared metadata now requests reimport
instead of silently accepting an installation with no temple music. Existing
waveform-file validation also checks that the referenced files exist.

## Local preparation and checks

The existing local cache had all47 original MIDI files and its instrument
bank. Prepare the missing songs from those sources, preserving every previous
cue and all original resource/MIDI files. Verify conventional stereo16-bit,
48kHz WAV headers and nonzero samples; all47 files pass. The original source
MIDI durations and actual playback durations remain distinct manifest fields.
The prepared files stay ignored and are not published in Git.

Regressions require the importer to render the temple cues, reject missing
temple music during validation, and keep validation independent of synthesis
imports. Real imported-asset checks exercise both room groups and combat in
all four temple levels, forcing the inclusive last pool member215/231/235,
and request ambient music at the level10 arrival through the real environment.
The importer/validation regressions reject de419c9 in both methods (six cases).

No original-code CPU probe or independent Sound Manager waveform comparison
was added: this reuses the previously implemented ambient rules and sampler.
It does not certify all temple music triggers or synthesizer/native parity.
Full gameplay discovery is not required for these importer/cache changes;
focused audio/import/temple checks and a real fresh GUI import cover the path.

Validation:217 focused tests pass without skips (28.042s). A separate final
fresh-import/launcher test passes (73.055s): cancellation6.2s, complete
import62.8s, maximum UI heartbeat gap0.219s. Dependencies, Ruff F/E9,
catalogue and whitespace checks pass. The prepared primary cache uses the
same original inputs as the validated worktree:82 MIDI/instrument/config
files matched before copying the47 newly generated WAVs. Original metadata
and unrelated cues are preserved; only file/playback-duration fields are
added. Users with older caches on other installations need to reimport.

The horse scene remains unchanged: current music onset16.922598s, immediate
transition on scene end, approved doorway and seamless cuts. Whether its last
music should carry into level10 remains a user decision after hearing the
temple. No outro hold/fade/carry-over policy is introduced here.
