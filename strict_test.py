                      
import os
import sys
import json
import time
import argparse
import tempfile
import numpy as np
import cv2
import soundfile as sf
from core.crypto import hash_str, seeded_shuffle
from core.grid_utils import get_blocks, get_outer_blocks, find_best_grid
from core.image_processor import process_image_file
from core.audio import process_audio_file
GOLD_HASH_TEST_KEY = 4243324813
GOLD_SHUFFLE16 = [9, 5, 3, 12, 1, 0, 13, 15, 7, 11, 6, 10, 8, 4, 14, 2]
GOLD_SHUFFLE10 = [6, 3, 2, 0, 5, 8, 1, 9, 7, 4]
GOLD_BLOCKS_10x10_4x4_FIRST = (0, 0, 2, 2)                             
GOLD_BLOCKS_10x10_4x4_LAST = (8, 8, 10, 10)
GOLD_BLOCKS_PRIME_FIRST3 = [(0, 0, 25, 19), (25, 0, 51, 19), (51, 0, 76, 19)]
GOLD_BLOCKS_PRIME_LAST = (102, 112, 127, 131)
REPORT = {"checks": [], "passed": 0, "failed": 0}
def check(name, fn):
    t0 = time.time()
    entry = {"name": name, "status": "PASS", "metrics": {}}
    try:
        metrics = fn() or {}
        entry["metrics"] = metrics
        REPORT["passed"] += 1
        metric_str = ", ".join(f"{k}={v}" for k, v in metrics.items())
        print(f"  [PASS] {name} ({time.time()-t0:.2f}s)  {metric_str}")
    except AssertionError as e:
        entry["status = "] = None                                            
        del entry["status = "]
        entry["status"] = "FAIL"
        entry["error"] = str(e)
        REPORT["failed"] += 1
        print(f"  [FAIL] {name}  :: {e}")
    REPORT["checks"].append(entry)
def meanabs(a, b):
    return float(np.mean(np.abs(a.astype(np.int32) - b.astype(np.int32))))
def checkerboard(w, h, cell=16, base=(40, 40, 40), phase=0):
    yy, xx = np.mgrid[0:h, 0:w]
    on = (((xx + phase) // cell) + ((yy + phase) // cell)) % 2 == 0
    img = np.zeros((h, w, 3), dtype=np.uint8)
    inv = (255 - base[0], 255 - base[1], 255 - base[2])
    img[on] = base
    img[~on] = inv
    return img
def t1_goldens():
    assert hash_str("test_key") == GOLD_HASH_TEST_KEY,
        f"hash drift: {hash_str('test_key')} != {GOLD_HASH_TEST_KEY}"
    assert seeded_shuffle(list(range(16)), GOLD_HASH_TEST_KEY) == GOLD_SHUFFLE16,
        "LCG shuffle drift on 16 elements"
    assert seeded_shuffle(list(range(10)), 12345) == GOLD_SHUFFLE10,
        "LCG shuffle drift on 10 elements"
    assert get_blocks(10, 10, 4, 4)[0] == GOLD_BLOCKS_10x10_4x4_FIRST,
        f"grid drift: {get_blocks(10,10,4,4)[0]}"
    assert get_blocks(10, 10, 4, 4)[-1] == GOLD_BLOCKS_10x10_4x4_LAST
    assert get_blocks(127, 131, 5, 7)[:3] == GOLD_BLOCKS_PRIME_FIRST3
    assert get_blocks(127, 131, 5, 7)[-1] == GOLD_BLOCKS_PRIME_LAST
    for n, seed in [(1, 7), (2, 7), (17, 999), (64, 1), (100, 424242)]:
        p = seeded_shuffle(list(range(n)), seed)
        assert sorted(p) == list(range(n)), f"non-bijective shuffle n={n} seed={seed}"
    return {"goldens": "7/7 exact"}
def t2_grid_sweep():
    worst_gap = 0
    tested = 0
    for (w, h, c, r) in [(127, 131, 5, 7), (10, 10, 4, 4), (1920, 1080, 16, 9),
                         (101, 103, 7, 7), (33, 17, 8, 8), (160, 120, 4, 4),
                         (128, 96, 4, 4), (1000, 1000, 10, 10)]:
        blocks = get_blocks(w, h, c, r)
        assert len(blocks) == c * r, f"{w}x{h} {c}x{r}: count {len(blocks)}"
        mask = np.zeros((h, w), dtype=np.uint8)
        for (x1, y1, x2, y2) in blocks:
            assert 0 <= x1 < x2 <= w and 0 <= y1 < y2 <= h, f"oob {(x1,y1,x2,y2)}"
            mask[y1:y2, x1:x2] += 1
        uncovered = int(np.sum(mask == 0))
        overlap = int(np.sum(mask > 1))
        worst_gap = max(worst_gap, uncovered + overlap)
        assert uncovered == 0 and overlap == 0,
            f"{w}x{h} {c}x{r}: uncovered={uncovered} overlap={overlap}"
        tested += 1
    outer, inner, _ = get_outer_blocks(4, 4, 128, 96, center_size="1/4")
    assert len(outer) + len(inner) == 16 and set(outer).isdisjoint(inner)
    return {"cases": tested, "uncovered_or_overlap_max": worst_gap}
def t3_image(tmp):
    prog = {}
    orig = checkerboard(120, 120)
    pin, penc, pdec = (os.path.join(tmp, f"cb_{s}.png") for s in ("orig", "enc", "dec"))
    cv2.imwrite(pin, orig)
    process_image_file(pin, penc,
                       {"process_video": True, "reverse": False, "cols": 4, "rows": 4,
                        "seed": 8888, "export_svg": False}, prog, "s_enc")
    process_image_file(penc, pdec,
                       {"process_video": True, "reverse": True, "cols": 4, "rows": 4,
                        "seed": 8888, "export_svg": False}, prog, "s_dec")
    enc = cv2.imread(penc)
    dec = cv2.imread(pdec)
    enc_diff = meanabs(enc, orig)
    maxdiff = int(np.max(np.abs(orig.astype(int) - dec.astype(int))))
    assert enc_diff > 25.0, f"encrypt did not scramble? enc-vs-orig meanabs={enc_diff:.2f}"
    assert maxdiff == 0, f"divisible roundtrip NOT bit-exact, maxdiff={maxdiff}"
    pdec_wrong = os.path.join(tmp, "cb_dec_wrong.png")
    process_image_file(penc, pdec_wrong,
                       {"process_video": True, "reverse": True, "cols": 4, "rows": 4,
                        "seed": 9999, "export_svg": False}, prog, "s_dec_wrong")
    wrong_diff = meanabs(cv2.imread(pdec_wrong), orig)
    assert wrong_diff > 25.0, f"wrong-seed decrypt restored?! diff={wrong_diff:.2f}"
    orig2 = checkerboard(127, 131)
    qin, qenc, qdec = (os.path.join(tmp, f"odd_{s}.png") for s in ("orig", "enc", "dec"))
    cv2.imwrite(qin, orig2)
    process_image_file(qin, qenc,
                       {"process_video": True, "reverse": False, "cols": 5, "rows": 7,
                        "seed": 1234, "export_svg": False}, prog, "s_oenc")
    process_image_file(qenc, qdec,
                       {"process_video": True, "reverse": True, "cols": 5, "rows": 7,
                        "seed": 1234, "export_svg": False}, prog, "s_odec")
    enc2_diff = meanabs(cv2.imread(qenc), orig2)
    dec2_diff = meanabs(cv2.imread(qdec), orig2)
    assert enc2_diff > 10.0, f"odd encrypt did not scramble? diff={enc2_diff:.2f}"
    assert dec2_diff < 8.0, f"odd decrypt did not restore, diff={dec2_diff:.2f}"
    return {"div_exact_maxdiff": maxdiff, "div_enc_meanabs": round(enc_diff, 2),
            "wrongseed_meanabs": round(wrong_diff, 2),
            "odd_enc_meanabs": round(enc2_diff, 2), "odd_dec_meanabs": round(dec2_diff, 2)}
def t4_audio(tmp):
    sr = 48000
    t = np.linspace(0, 0.5, int(sr * 0.5), endpoint=False)
    sig = 0.4 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 1200 * t)
    stereo = np.vstack((sig, sig)).T
    pin, penc, pdec = (os.path.join(tmp, f"au_{s}.wav") for s in ("orig", "enc", "dec"))
    sf.write(pin, stereo, sr, subtype="PCM_16")
    out = {}
    for method in ("inversion", "band_scramble", "combined"):
        process_audio_file(pin, penc, is_decrypt=False, method=method, key=777, carrier_freq=8000)
        process_audio_file(penc, pdec, is_decrypt=True, method=method, key=777, carrier_freq=8000)
        o, _ = sf.read(pin)
        e, _ = sf.read(penc)
        d, _ = sf.read(pdec)
        corr_enc = float(np.corrcoef(o[:, 0], e[:, 0])[0, 1])
        corr_dec = float(np.corrcoef(o[:, 0], d[:, 0])[0, 1])
        if method == "inversion":
            process_audio_file(penc, pdec, is_decrypt=True, method=method,
                               key=777, carrier_freq=12000)
        else:
            process_audio_file(penc, pdec, is_decrypt=True, method=method,
                               key=778, carrier_freq=8000)
        w, _ = sf.read(pdec)
        corr_wrong = float(np.corrcoef(o[:, 0], w[:, 0])[0, 1])
        assert abs(corr_enc) < 0.60, f"{method}: not scrambled (corr_enc={corr_enc:.3f})"
        floor = 0.70 if method == "band_scramble" else 0.85
        assert corr_dec >= floor, f"{method}: fidelity low (corr_dec={corr_dec:.3f} < {floor})"
        assert corr_wrong < 0.90, f"{method}: wrong key still restores?! ({corr_wrong:.3f})"
        out[f"{method}_enc"] = round(corr_enc, 3)
        out[f"{method}_dec"] = round(corr_dec, 3)
        out[f"{method}_wrong"] = round(corr_wrong, 3)
    return out
def t5_video(tmp):
    from core.video_processor import process_video_file
    from core.crypto import hash_str as _hs
    W, H, N = 128, 96, 6
    bgr, ctn = (os.path.join(tmp, f"v_{s}.mp4") for s in ("bg", "ct"))
    for path, base in ((bgr, (40, 40, 40)),):
        wr = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (W, H))
        for i in range(N):
            wr.write(checkerboard(W, H, phase=(i * 4) % 32, base=base))
        wr.release()
    seed = _hs("strict_video")
    enc, dec = os.path.join(tmp, "v_enc.mp4"), os.path.join(tmp, "v_dec.mp4")
    base_opts = {"process_video": True, "process_audio": False, "cols": 4, "rows": 4,
                 "seed": seed, "export_svg": False, "vid_codec": "libx264",
                 "vid_bitrate": "2000k", "vid_preset": "ultrafast"}
    process_video_file(bgr, enc, dict(base_opts, reverse=False), {}, "sv_enc")
    process_video_file(enc, dec, dict(base_opts, reverse=True), {}, "sv_dec")
    def frames(p):
        cap = cv2.VideoCapture(p)
        fs = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            fs.append(f)
        cap.release()
        return fs
    fo, fe, fd = frames(bgr), frames(enc), frames(dec)
    assert len(fe) == len(fo) == len(fd) == N,
        f"frame count {len(fo)}/{len(fe)}/{len(fd)} != {N}"
    enc_diffs = [meanabs(a, b) for a, b in zip(fe, fo)]
    dec_diffs = [meanabs(a, b) for a, b in zip(fd, fo)]
    assert min(enc_diffs) > 15.0, f"video encrypt left frames near-plain: {enc_diffs}"
    assert max(dec_diffs) < 25.0, f"video decrypt did not restore: {dec_diffs}"
    return {"frames": N, "enc_meanabs_min": round(min(enc_diffs), 2),
            "enc_meanabs_max": round(max(enc_diffs), 2),
            "dec_meanabs_max": round(max(dec_diffs), 2)}
def t6_gridmap(tmp):
    import hashlib
    from core.gridmap import load_gridmap_json
    prog = {}
    orig = checkerboard(120, 120)
    pin = os.path.join(tmp, "gm_orig.png")
    penc = os.path.join(tmp, "gm_enc.png")
    cv2.imwrite(pin, orig)
    process_image_file(pin, penc,
                       {"process_video": True, "reverse": False, "cols": 4, "rows": 4,
                        "seed": 8888, "export_svg": False, "export_map": True},
                       prog, "s_gmenc")
    base, _ = os.path.splitext(penc)
    gm = load_gridmap_json(f"{base}_gridmap.json")
    assert gm["format"] == "media-encrypt-gridmap/1", "format tag drift"
    assert (gm["w"], gm["h"], gm["cols"], gm["rows"], gm["seed"]) == (120, 120, 4, 4, 8888)
    assert gm["has_center"] is False and gm["perm"]["mode"] == "full"
    assert gm["blocks"] == [list(b) for b in get_blocks(120, 120, 4, 4)],
        "gridmap blocks != pipeline grid"
    assert gm["perm"]["shuffled"] == seeded_shuffle(list(range(16)), 8888),
        "gridmap perm != pipeline shuffle (SVG could never catch this)"
    assert sorted(gm["perm"]["shuffled"]) == list(range(16)), "perm not bijective"
    assert all(isinstance(v, int) for b in gm["blocks"]
               for v in b + gm["perm"]["shuffled"]), "non-integer in JSON map"
    png1 = f"{base}_gridmap.png"
    img1 = cv2.imread(png1)
    assert img1 is not None and img1.shape == (120, 120, 3), "preview unreadable/wrong size"
    assert len(np.unique(img1.reshape(-1, 3), axis=0)) > 2, "preview is blank"
    with open(png1, "rb") as f:
        digest1 = hashlib.sha256(f.read()).hexdigest()
    from core.gridmap import build_gridmap, export_gridmap_png
    png2 = os.path.join(tmp, "gm_redo.png")
    export_gridmap_png(png2, build_gridmap(120, 120, 4, 4, 8888))
    with open(png2, "rb") as f:
        digest2 = hashlib.sha256(f.read()).hexdigest()
    assert digest1 == digest2, "PNG preview not byte-deterministic"
    bg = np.full((120, 160, 3), 40, dtype=np.uint8)
    ct = np.full((60, 80, 3), 200, dtype=np.uint8)
    pbg, pct = os.path.join(tmp, "gm_bg.png"), os.path.join(tmp, "gm_ct.png")
    cv2.imwrite(pbg, bg)
    cv2.imwrite(pct, ct)
    penc2 = os.path.join(tmp, "gm_cenc.png")
    process_image_file(pbg, penc2,
                       {"process_video": True, "reverse": False, "cols": 4, "rows": 4,
                        "seed": 1234, "center": True, "center_size": "1/4",
                        "center_path": pct, "video_encrypt_mode": "both",
                        "export_svg": False, "export_map": True},
                       prog, "s_gmcenc")
    base2, _ = os.path.splitext(penc2)
    gm2 = load_gridmap_json(f"{base2}_gridmap.json")
    c = gm2["center"]
    assert gm2["has_center"] is True and c is not None
    assert len(c["outer"]) + len(c["inner"]) == 16
    assert set(c["outer"]).isdisjoint(c["inner"]), "outer/inner overlap"
    assert sorted(c["shuffled_outer"]) == sorted(c["outer"]), "outer shuffle corrupt"
    assert sorted(c["shuffled_center"]) == list(range(len(c["shuffled_center"]))),
        "center shuffle not bijective"
    return {"json_checks": "exact", "png_sha256": digest1[:12],
            "center_outer": len(c["outer"]), "center_inner": len(c["inner"])}
def t7_optical_markers(tmp):
    from core.crypto import (stamp_optical_markers, detect_all_optical_markers,
                             check_marker_presence, _calculate_marker_boxes,
                             effective_marker_placement, hash_str as _hs)
    from core.video_processor import process_video_file
    W, H = 160, 120
    for plc, want in (("outside", (0.25, 0.25, 0.75, 0.75)),
                      ("inside", (0.25, 0.25, 0.75, 0.75))):
        img = np.full((H, W, 3), 128, dtype=np.uint8)
        stamped, _ = stamp_optical_markers(img, 40, 30, 120, 90, placement=plc)
        boxes = _calculate_marker_boxes(W, H, 40, 30, 120, 90, plc, 18)
        assert check_marker_presence(stamped, boxes), f"{plc}: stamped markers not detectable"
        rois = detect_all_optical_markers(stamped, placement=plc)
        assert rois, f"{plc}: no ROI detected"
        assert all(abs(a - b) <= 0.01 for a, b in zip(rois[0], want)),
            f"{plc}: ROI {rois[0]} != {want}"
    assert effective_marker_placement(True, "c.mp4", None, [0.2, 0.2, 0.8, 0.8], True, "inside") == "inside"
    assert effective_marker_placement(False, None, None, [0.2, 0.2, 0.8, 0.8], True, "inside") == "inside"
    assert effective_marker_placement(True, "c.mp4", None, None, False, "inside") == "inside"
    assert effective_marker_placement(True, "c.mp4", None, [0.2, 0.2, 0.8, 0.8], True, "outside") == "outside"
    assert effective_marker_placement(False, None, None, None, False, None) == "outside"
    src = os.path.join(tmp, "m_src.mp4")
    wr = cv2.VideoWriter(src, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (W, H))
    for i in range(6):
        wr.write(checkerboard(W, H, phase=(i * 4) % 32))
    wr.release()
    seed = _hs("strict_markers")
    enc, dec = os.path.join(tmp, "m_enc.mp4"), os.path.join(tmp, "m_dec.mp4")
    eopts = {"process_video": True, "process_audio": False, "cols": 4, "rows": 3,
             "seed": seed, "export_svg": False, "vid_codec": "libx264",
             "vid_bitrate": "2000k", "vid_preset": "ultrafast",
             "patch_roi": [0.25, 0.25, 0.75, 0.75], "optical_markers": True,
             "marker_placement": "inside", "marker_inside_full": False,
             "patch_segments": [{"start": 0.0, "end": 9.9, "roi": [0.25, 0.25, 0.75, 0.75], "invert": False}]}
    process_video_file(src, enc, dict(eopts, reverse=False), {}, "sm_enc")
    dopts = dict(eopts, reverse=True)
    dopts.pop("patch_roi", None)
    dopts.pop("patch_segments", None)
    process_video_file(enc, dec, dopts, {}, "sm_dec")
    def frames(p):
        cap = cv2.VideoCapture(p)
        fs = []
        while True:
            ok, f = cap.read()
            if not ok:
                break
            fs.append(f)
        cap.release()
        return fs
    fo, fd = frames(src), frames(dec)
    assert len(fo) == len(fd) == 6, f"frame count {len(fo)}/{len(fd)} != 6"
    dec_diffs = [meanabs(a, b) for a, b in zip(fo, fd)]
    assert max(dec_diffs) < 30.0, f"optical decrypt did not restore: {dec_diffs}"
    enc2, dec2 = os.path.join(tmp, "m_enc2.mp4"), os.path.join(tmp, "m_dec2.mp4")
    eopts2 = dict(eopts, marker_inside_full=True)
    process_video_file(src, enc2, dict(eopts2, reverse=False), {}, "sm_enc2")
    dopts2 = dict(dopts, marker_inside_full=True)
    process_video_file(enc2, dec2, dopts2, {}, "sm_dec2")
    fo2, fd2 = frames(src), frames(dec2)
    assert len(fo2) == len(fd2) == 6
    dec_diffs2 = [meanabs(a, b) for a, b in zip(fo2, fd2)]
    assert max(dec_diffs2) < 30.0, f"mif decrypt did not restore: {dec_diffs2}"
    csrc = os.path.join(tmp, "zc_ct.mp4")
    wr = cv2.VideoWriter(csrc, cv2.VideoWriter_fourcc(*"mp4v"), 10.0, (W, H))
    for i in range(6):
        wr.write(checkerboard(W, H, phase=(i * 7 + 3) % 32))
    wr.release()
    zenc, zdec = os.path.join(tmp, "zc_enc.mp4"), os.path.join(tmp, "zc_dec.mp4")
    eopts3 = {"process_video": True, "process_audio": False, "cols": 4, "rows": 3,
              "seed": seed, "export_svg": False, "vid_codec": "libx264",
              "vid_bitrate": "2000k", "vid_preset": "ultrafast",
              "center": True, "center_path": csrc, "center_size": "1/4",
              "video_encrypt_mode": "both",
              "patch_roi": [0.2, 0.2, 0.8, 0.8], "optical_markers": True,
              "marker_placement": "inside", "marker_inside_full": True,
              "patch_segments": [{"start": 0.0, "end": 9.9, "roi": [0.2, 0.2, 0.8, 0.8], "invert": False}]}
    process_video_file(src, zenc, dict(eopts3, reverse=False), {}, "sm_zcenc")
    dopts3 = {"process_video": True, "process_audio": False, "cols": 4, "rows": 3,
              "seed": seed, "export_svg": False, "vid_codec": "libx264",
              "vid_bitrate": "2000k", "vid_preset": "ultrafast",
              "center": True, "center_size": "1/4", "video_encrypt_mode": "both",
              "optical_markers": True, "marker_placement": "inside",
              "marker_inside_full": True, "reverse": True}
    process_video_file(zenc, zdec, dopts3, {}, "sm_zcdec")
    fo3, fd3 = frames(src), frames(zdec)
    assert len(fo3) == len(fd3) == 6, f"zc frame count {len(fo3)}/{len(fd3)} != 6"
    dec_diffs3 = [meanabs(a, b) for a, b in zip(fo3, fd3)]
    assert max(dec_diffs3) < 30.0, f"zone+center inside decrypt did not restore: {dec_diffs3}"
    return {"detect": "in+out exact", "key_rule": "inside-kept",
            "dec_meanabs_max": round(max(dec_diffs), 2),
            "mif_meanabs_max": round(max(dec_diffs2), 2),
            "zc_inside_meanabs_max": round(max(dec_diffs3), 2)}
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true", help="skip video test")
    args = ap.parse_args()
    print("=" * 70)
    print("  STRICT TEST — adversarial, quantitative, with negative controls")
    print("=" * 70)
    with tempfile.TemporaryDirectory(prefix="strict_") as tmp:
        check("T1 golden vectors (py<->js contract)", t1_goldens)
        check("T2 grid area-conservation sweep", t2_grid_sweep)
        check("T3 image checkerboard roundtrip + proofs", lambda: t3_image(tmp))
        check("T4 audio scramble/fidelity/wrong-key", lambda: t4_audio(tmp))
        check("T6 gridmap sidecar exactness", lambda: t6_gridmap(tmp))
        if args.fast:
            print("  [SKIP] T5 video (use without --fast to run)")
        else:
            check("T5 video per-frame encrypt/restore", lambda: t5_video(tmp))
            check("T7 optical markers in/outside + probe", lambda: t7_optical_markers(tmp))
    print("-" * 70)
    print(f"  PASS={REPORT['passed']}  FAIL={REPORT['failed']}")
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "strict_report.json"), "w", encoding="utf-8") as f:
        json.dump(REPORT, f, indent=2, ensure_ascii=False)
    print("  report -> strict_report.json")
    print("=" * 70)
    return 1 if REPORT["failed"] else 0
if __name__ == "__main__":
    sys.exit(main())
