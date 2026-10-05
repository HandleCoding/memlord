"""Unit tests for weighted RRF fusion helpers (no DB)."""

from memlord.search import fuse_rrf, strong_fts_ids


def test_strong_fts_ids_drops_weak_relative_hits():
    ts = {1: 1.0, 2: 0.5, 3: 0.2, 4: 0.05}
    assert strong_fts_ids(ts, 0.3) == {1, 2}
    assert strong_fts_ids(ts, 0.0) == {1, 2, 3, 4}
    assert strong_fts_ids({}, 0.3) == set()


def test_strong_fts_ids_keeps_all_when_max_nonpositive():
    assert strong_fts_ids({1: 0.0, 2: 0.0}, 0.3) == {1, 2}


def test_fuse_rrf_weights_and_name_boost():
    # With k=20: rank-1 contrib = 1/21 ≈ 0.04762
    fused = fuse_rrf(
        doc_ids={1, 2, 3},
        bm25_ranks={1: 1, 2: 1},
        vec_ranks={1: 2, 3: 1},
        name_boost={3: 0.025},
        k=20,
        w_fts=0.5,
        w_vec=1.0,
    )
    total1, fts1, vec1, name1 = fused[1]
    total2, fts2, vec2, name2 = fused[2]
    total3, fts3, vec3, name3 = fused[3]

    assert abs(fts1 - 0.5 / 21) < 1e-9
    assert abs(vec1 - 1.0 / 22) < 1e-9
    assert name1 == 0.0
    assert abs(total1 - (fts1 + vec1)) < 1e-9

    # Doc 2: FTS only (weighted)
    assert abs(fts2 - 0.5 / 21) < 1e-9
    assert vec2 == 0.0
    assert abs(total2 - fts2) < 1e-9

    # Doc 3: vec rank-1 + partial name boost, no FTS
    assert fts3 == 0.0
    assert abs(vec3 - 1.0 / 21) < 1e-9
    assert name3 == 0.025
    assert abs(total3 - (vec3 + 0.025)) < 1e-9
    assert total3 > total1 > total2


def test_fuse_rrf_local_weights_equal_legs():
    fused = fuse_rrf(
        doc_ids={1},
        bm25_ranks={1: 1},
        vec_ranks={1: 1},
        name_boost={},
        k=20,
        w_fts=1.0,
        w_vec=1.0,
    )
    total, fts, vec, name = fused[1]
    assert abs(fts - 1.0 / 21) < 1e-9
    assert abs(vec - 1.0 / 21) < 1e-9
    assert name == 0.0
    assert abs(total - 2.0 / 21) < 1e-9


def test_fuse_rrf_lower_k_steepens_rank_gaps():
    """Smaller k widens the gap between rank-1 and rank-N (generic corpora)."""
    wide = fuse_rrf(
        doc_ids={1, 2},
        bm25_ranks={},
        vec_ranks={1: 1, 2: 10},
        name_boost={},
        k=20,
        w_fts=0.5,
        w_vec=1.0,
    )
    flat = fuse_rrf(
        doc_ids={1, 2},
        bm25_ranks={},
        vec_ranks={1: 1, 2: 10},
        name_boost={},
        k=60,
        w_fts=0.5,
        w_vec=1.0,
    )
    gap_wide = wide[1][0] - wide[2][0]
    gap_flat = flat[1][0] - flat[2][0]
    assert gap_wide > gap_flat
