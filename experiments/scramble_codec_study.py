                      
import argparse
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import cv2
import numpy as np
PROJ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJ)
from core.grid_utils import get_blocks              
from core.video_processor import _scramble_frame_ordinary              
W, H, FPS, NFRAMES = 1280, 720, 30, 60
SEED = 777
BITRATE = "2500k"
BUF = "5000k"
GRIDS = {
    "G10": (10, 10),                                                
    "G20": (20, 15),                                       
    "G21": (21, 16),                                                                  
    "G40": (40, 30),                                
    "G100": (100, 100),                                                    
}
LINES = {
    "L2": 2,                                           
    "L8": 8,                           
}
def line_perm(n, seed):
    rng = np.random.RandomState(seed)
    return rng.permutation(n)
def line_shuffle_frame(frame, lh, seed, reverse=False):
    n = H // lh
    perm = line_perm(n, seed)
    if reverse:
        perm = np.argsort(perm)
    blocks = frame[:n * lh].reshape(n, lh, W, 3)
    out = frame.copy()
    out[:n * lh] = blocks[perm].reshape(n * lh, W, 3)
    return out
def build_content():
    frames = []
    yy, xx = np.mgrid[0:H, 0:W]
    base_chk = ((xx // 16 + yy // 16) % 2 * 255).astype(np.uint8)
    for f in range(NFRAMES):
        img = np.zeros((H, W, 3), dtype=np.uint8)
        img[:, :, 0] = base_chk
        img[:, :, 1] = 255 - base_chk
        img[:, :, 2] = ((xx // 16 + yy // 32) % 2 * 255).astype(np.uint8)
        img[:, :, 0] = (img[:, :, 0].astype(np.uint16)
                        + (xx * 60 / W)).astype(np.uint8)                          
        img[:, :, 2] = (img[:, :, 2].astype(np.uint16)
                        + (yy * 60 / H)).astype(np.uint8)
        img[::4, :, :] = img[::4, :, :] // 2 + 40                           
        sq, mv = 120, int(f * (W - 160) / (NFRAMES - 1))
        img[300:300 + sq, 20 + mv:20 + mv + sq, :] = 255                       
        img[300:300 + sq, 20 + mv:20 + mv + sq, 1] = 0
        sq2, mv2 = 90, int((NFRAMES - 1 - f) * (W - 130) / (NFRAMES - 1))
        img[100:100 + sq2, 20 + mv2:20 + mv2 + sq2, 0] = 255                    
        frames.append(img)
    return frames
def seam_edges(cols, rows):
    xs, ys = set(), set()
    for (x1, y1, x2, y2) in get_blocks(W, H, cols, rows):
        xs.add(x1); xs.add(x2); ys.add(y1); ys.add(y2)
    xs = sorted(x for x in xs if 0 < x < W)
    ys = sorted(y for y in ys if 0 < y < H)
    return xs, ys
def run_ffmpeg(args, data_in=None):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
                       + args, input=data_in,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {p.stderr.decode()[:500]}")
    return p.stdout
def decode_frames(path):
    raw = run_ffmpeg(["-i", path, "-f", "rawvideo", "-pix_fmt", "bgr24", "-"])
    n = len(raw) // (W * H * 3)
    arr = np.frombuffer(raw, dtype=np.uint8)[:n * W * H * 3]
    return [arr[i * W * H * 3:(i + 1) * W * H * 3].reshape(H, W, 3)
            for i in range(n)]
def psnr(a, b):
    mse = float(np.mean((a.astype(np.float64) - b.astype(np.float64)) ** 2))
    return 99.0 if mse <= 0 else 10.0 * math.log10(255.0 ** 2 / mse)
def gray(f):
    return (0.299 * f[:, :, 2] + 0.587 * f[:, :, 1]
            + 0.114 * f[:, :, 0])
def psnr_chroma(a, b):
    ca = cv2.cvtColor(a, cv2.COLOR_BGR2YCrCb)[:, :, 1:].astype(np.float64)
    cb = cv2.cvtColor(b, cv2.COLOR_BGR2YCrCb)[:, :, 1:].astype(np.float64)
    mse = float(np.mean((ca - cb) ** 2))
    return 99.0 if mse <= 0 else 10.0 * math.log10(255.0 ** 2 / mse)
def lossless_roundtrip(cols, rows):
    ps = []
    for i in [0, 30, 59]:
        s = _scramble_frame_ordinary(CONTENT[i], cols, rows, SEED)
        b = _scramble_frame_ordinary(s, cols, rows, SEED, reverse=True)
        ps.append(psnr(CONTENT[i], b))
    return round(float(np.mean(ps)), 3)
def lossless_line_roundtrip(lh):
    ps = []
    for i in [0, 30, 59]:
        s = line_shuffle_frame(CONTENT[i], lh, SEED)
        b = line_shuffle_frame(s, lh, SEED, reverse=True)
        ps.append(psnr(CONTENT[i], b))
    return round(float(np.mean(ps)), 3)
def scramble_fwd(frame, grid):
    if grid in LINES:
        return line_shuffle_frame(frame, LINES[grid], SEED)
    cols, rows = GRIDS[grid]
    return _scramble_frame_ordinary(frame, cols, rows, SEED)
def descramble_rev(frame, grid):
    if grid in LINES:
        return line_shuffle_frame(frame, LINES[grid], SEED, reverse=True)
    cols, rows = GRIDS[grid]
    return _scramble_frame_ordinary(frame, cols, rows, SEED, reverse=True)
def edges_for(grid):
    if grid in LINES:
        lh = LINES[grid]
        return [], [k * lh for k in range(1, H // lh)]
    cols, rows = GRIDS[grid]
    return seam_edges(cols, rows)
def seam_stats(frame, xs, ys):
    g = gray(frame.astype(np.float64))
    gx = np.abs(np.diff(g, axis=1))
    gy = np.abs(np.diff(g, axis=0))
    mx = np.zeros((H, W - 1), bool)
    for x in xs:
        mx[:, max(0, x - 1):min(W - 1, x + 1)] = True
    my = np.zeros((H - 1, W), bool)
    for y in ys:
        my[max(0, y - 1):min(H - 1, y + 1), :] = True
    seam_e = np.concatenate([gx[mx], gy[my]]).mean()
    bg_e = np.concatenate([gx[~mx], gy[~my]]).mean()
    return seam_e, (seam_e / bg_e if bg_e > 0 else 0.0)
CASES = []
def case(name, codec, extra, grid="G20", group="flags", bitrate=BITRATE):
    CASES.append({"name": name, "codec": codec, "extra": extra,
                  "grid": grid, "group": group, "bitrate": bitrate})
def define_cases():
    x264_base = ["-preset", "medium"]
    x264_combo = x264_base + ["-x264-params", "no-deblock=1",
                              "-psy", "0", "-tune", "ssim",
                              "-chromaoffset", "-2"]
    case("x264/G20/base", "libx264", x264_base)
    case("x264/G20/nodeblock", "libx264", x264_base + ["-x264-params", "no-deblock=1"])
    case("x264/G20/psy0+tune", "libx264", x264_base + ["-psy", "0", "-tune", "ssim"])
    case("x264/G20/combo", "libx264", x264_combo)
    case("x264/G20/gop30", "libx264", x264_base + ["-g", "30"], group="gop")
    case("x264/G20/base@8M", "libx264", x264_base, bitrate="8000k", group="bitrate")
    case("x264/G20/combo@8M", "libx264", x264_combo, bitrate="8000k", group="bitrate")
    case("x264/G100/combo", "libx264", x264_combo, grid="G100", group="grids")
    x265_base = ["-preset", "medium"]
    case("x265/G20/base", "libx265", x265_base)
    case("x265/G20/nodeblock", "libx265", x265_base + ["-x265-params", "no-deblock=1"])
    case("x265/G20/tune", "libx265", x265_base + ["-tune", "ssim"])
    case("x265/G20/combo", "libx265",
         x265_base + ["-x265-params", "no-deblock=1", "-tune", "ssim"])
    vp9_base = ["-deadline", "good", "-cpu-used", "2"]
    case("vp9/G20/base", "libvpx-vp9", vp9_base)
    case("vp9/G20/screen", "libvpx-vp9", vp9_base + ["-tune-content", "1"])
    case("vp9/G20/arnr0", "libvpx-vp9", vp9_base + ["-arnr-strength", "0"])
    av1_base = ["-cpu-used", "6"]
    case("av1/G20/base", "libaom-av1", av1_base)
    case("av1/G20/nosmooth", "libaom-av1",
         av1_base + ["-enable-cdef", "0", "-enable-restoration", "0"])
    case("av1/G20/combo", "libaom-av1",
         av1_base + ["-tune", "1", "-enable-cdef", "0",
                     "-enable-restoration", "0"])
    for g in ["G10", "G21", "G40", "G100"]:
        case(f"x264/{g}/base", "libx264", x264_base, grid=g, group="grids")
    for g in ["G10", "G21", "G40", "G100"]:
        case(f"x265/{g}/base", "libx265", x265_base, grid=g, group="grids")
    for g in ["G10", "G100"]:
        case(f"vp9/{g}/base", "libvpx-vp9", vp9_base, grid=g, group="grids")
    case("av1/G10/base", "libaom-av1", av1_base, grid="G10", group="grids")
    case("av1/G100/base", "libaom-av1", av1_base, grid="G100", group="grids")
    case("x264/G20/444", "libx264",
         ["-preset", "medium", "-pix_fmt", "yuv444p", "-profile:v", "high444"],
         group="pixfmt")
    case("x265/G20/444", "libx265",
         ["-preset", "medium", "-pix_fmt", "yuv444p"], group="pixfmt")
    case("x264/G20/combo@2M", "libx264", x264_combo, bitrate="2000k",
         group="bitrate")
    for g in ["G10", "G20", "G21", "G40", "G100", "L2", "L8"]:
        case(f"lossless/{g}", "none", [], grid=g, group="lossless")
    case("x264/L2/base", "libx264", x264_base, grid="L2", group="lines")
    case("x264/L2/combo", "libx264", x264_combo, grid="L2", group="lines")
    case("x264/L8/base", "libx264", x264_base, grid="L8", group="lines")
    case("x265/L2/base", "libx265", x265_base, grid="L2", group="lines")
    case("x265/L2/combo", "libx265",
         x265_base + ["-x265-params", "no-deblock=1", "-tune", "ssim"],
         grid="L2", group="lines")
    case("x264/G20/10bit", "libx264",
         ["-preset", "medium", "-pix_fmt", "yuv420p10le"], group="depth")
    case("x265/G20/10bit", "libx265",
         ["-preset", "medium", "-pix_fmt", "yuv420p10le"], group="depth")
def run_case(c, frames_by_grid, out_dir):
    key = c["grid"]
    if key not in frames_by_grid:
        frames_by_grid[key] = [scramble_fwd(f, key) for f in CONTENT]
    xs, ys = edges_for(key)
    path = os.path.join(out_dir, c["name"].replace("/", "_") + ".mp4")
    bitrate = c.get("bitrate", BITRATE)
    buf = f"{int(bitrate.rstrip('k')) * 2}k"
    cmd_extra = [a.replace(BITRATE, bitrate) for a in c["extra"]]
    deep = any("10le" in a for a in cmd_extra)
    if deep:
        frames = [(f.astype(np.uint16) * 257) for f in frames_by_grid[key]]
        in_fmt = "bgr48le"
    else:
        frames = frames_by_grid[key]
        in_fmt = "bgr24"
    blob = b"".join(f.tobytes() for f in frames)
    cmd = ["-f", "rawvideo", "-pix_fmt", in_fmt, "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-",
           "-c:v", c["codec"], "-b:v", bitrate, "-maxrate", bitrate,
           "-bufsize", buf] + cmd_extra + [path]
    t0 = time.time()
    run_ffmpeg(cmd, data_in=blob)
    enc_s = time.time() - t0
    size = os.path.getsize(path)
    dec = decode_frames(path)
    idx = [0, 15, 30, 45, 59]
    psnrs, chromas, ratios, seams = [], [], [], []
    for i in idx:
        if i >= len(dec):
            break
        back = descramble_rev(dec[i], key)
        psnrs.append(psnr(CONTENT[i], back))
        chromas.append(psnr_chroma(CONTENT[i], back))
        s, r = seam_stats(back, xs, ys)
        seams.append(s); ratios.append(r)
    return {"name": c["name"], "codec": c["codec"], "grid": c["grid"],
            "group": c["group"], "bitrate": bitrate,
            "extra": " ".join(c["extra"]),
            "size_bytes": size,
            "psnr_mean": round(float(np.mean(psnrs)), 3),
            "psnr_chroma": round(float(np.mean(chromas)), 3),
            "seam_abs": round(float(np.mean(seams)), 3),
            "seam_ratio": round(float(np.mean(ratios)), 3),
            "enc_seconds": round(enc_s, 1)}
CONTENT = None
def main():
    global CONTENT
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="", help="substring filter on case name")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--out", default="")
    args = ap.parse_args()
    define_cases()
    if args.list:
        for c in CASES:
            print(f'{c["name"]:22s} {c["codec"]:12s} grid={c["grid"]} [{c["group"]}]')
        print(f"TOTAL: {len(CASES)}")
        return
    out_dir = args.out or tempfile.mkdtemp(prefix="scramble_study_")
    os.makedirs(out_dir, exist_ok=True)
    res_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "results.json")
    done = {}
    if os.path.exists(res_path):
        try:
            done = {r["name"]: r for r in json.load(open(res_path))
                    if "name" in r}
        except Exception:
            pass
    todo = [c for c in CASES if args.only in c["name"]
            and (args.redo or c["name"] not in done)]
    print(f"cases: {len(todo)} (out={out_dir})", flush=True)
    CONTENT = build_content()
    frames_by_grid = {}
    redo_names = {c["name"] for c in todo}
    results = [r for r in done.values() if r["name"] not in redo_names]
    for i, c in enumerate(todo):
        print(f"[{i + 1}/{len(todo)}] {c['name']} ...", flush=True)
        try:
            if c["codec"] == "none":
                grid = c["grid"]
                if grid in LINES:
                    lp = lossless_line_roundtrip(LINES[grid])
                else:
                    cols, rows = GRIDS[grid]
                    lp = lossless_roundtrip(cols, rows)
                r = {"name": c["name"], "codec": "none", "grid": grid,
                     "group": "lossless", "lossless_psnr": lp}
            else:
                r = run_case(c, frames_by_grid, out_dir)
        except Exception as e:
            print(f"  FAILED: {e}", flush=True)
            r = {"name": c["name"], "error": str(e)[:200]}
        results.append(r)
        json.dump(results, open(res_path, "w"), indent=1)
        print(f"  -> {r}", flush=True)
    print(f"results -> {res_path}")
if __name__ == "__main__":
    main()
