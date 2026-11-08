import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
import like


class FakeMPD:
    def __init__(self, liked):
        self.liked = list(liked)

    def listplaylist(self, name):
        return list(self.liked)

    def playlistadd(self, name, file, pos):
        self.liked.insert(pos, file)

    def playlistdelete(self, name, pos):
        del self.liked[pos]


def test_selection_beats_current_song():
    assert like.targets({"SELECTED_SONGS": "a\nb", "CURRENT_SONG": "c"}) == ["a", "b"]
    assert like.targets({"CURRENT_SONG": "c"}) == ["c"]
    assert like.targets({}) == []


def test_like_missing_ones_newest_on_top():
    m = FakeMPD(["x", "b"])
    assert like.apply(m, ["a", "b"]) is True
    assert m.liked == ["a", "x", "b"]


def test_all_liked_means_unlike_all():
    m = FakeMPD(["a", "x", "b"])
    assert like.apply(m, ["a", "b"]) is False
    assert m.liked == ["x"]
