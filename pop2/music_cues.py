"""Shared prepared-music requirements, without importer/audio dependencies."""

# Temple ambient bank2 (200/216/232), level/opponent/death songs and the
# already-wired flaming-sword/altar/shadow cues. Native counts15/15/3 are
# inclusive Rnd bounds, selecting all16/16/4 ambient tracks.
INSCRIPTION_SONG = 292  # Chasm, shared with the level-nine crossing.
# JPoof 244 (TriggerJinnee 4:1ebe), JGrows 245 and JFight 246 (SpecialMusic
# 5:53c2-53ea, a fight whose first opponent is type 12 or the flaming sword).
TEMPLE_SONGS = (187, 188, 189, 194, *range(200, 236), 237, 238, 244, 245, 246,
                *range(250, 255), INSCRIPTION_SONG)

# Level 14 (environment 6, no ambient bank): the mental rooms' themes
# Escher 262, ChessRm 267, Spider 268 and Crystal 269 (9:1a90, 1d84, 0654),
# JaffKill 263, LoseSwd 264 (the body's dissolve), ThroFire 265 (the
# spell), JafPoof 270 and Shadow 290 (the shadow form). Happy1 266 (a .gmf
# song) renders silent and is left out.
FINAL_SONGS = (262, 263, 264, 265, *range(267, 271), 290)
