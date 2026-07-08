import uuid

from retrieval.hybrid_search import RRF_K, _fuse

A, B, C = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


def test_item_in_both_lists_beats_single_list_items():
    scores = _fuse([[A, B], [A, C]])
    assert scores[A] > scores[B]
    assert scores[A] > scores[C]


def test_rank_position_matters():
    scores = _fuse([[A, B]])
    assert scores[A] == 1.0 / (RRF_K + 1)
    assert scores[B] == 1.0 / (RRF_K + 2)
    assert scores[A] > scores[B]


def test_empty_lists_fuse_to_empty():
    assert _fuse([[], []]) == {}
