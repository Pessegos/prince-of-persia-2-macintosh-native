"""Shared prepared-music requirements, without importer/audio dependencies."""

# Temple ambient bank2 (200/216/232), level/opponent/death songs and the
# already-wired flaming-sword/altar/shadow cues. Native counts15/15/3 are
# inclusive Rnd bounds, selecting all16/16/4 ambient tracks.
TEMPLE_SONGS = (187, 188, 189, 194, *range(200, 236), 237, 238, *range(250, 255))
