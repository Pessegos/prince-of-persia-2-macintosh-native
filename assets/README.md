# Local Game Files

Original game files are not included in the source distribution. On the first
launch, select a compatible Macintosh Prince of Persia 2 HFS disk image.
The importer creates the resource files, per-level scenery exports,
`enemy_profiles.json`, cutscene/demo programs and `audio/` here. Audio contains
the original PCM samples, voices, MIDI sequences and instrument bank, plus
prepared WAV music and an extracted cue manifest. Story sounds retain their
separate music and effect banks even when resource numbers match.
These WAVs are an import-time playback cache, not gameplay test recordings.
The game application itself is read during import but is not copied here.

These generated files are ignored by Git. Keep your disk image outside this
folder. See [the project README](../README.md) for setup and supported images.
