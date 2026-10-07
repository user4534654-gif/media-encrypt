"""Encrypt-timeline export for video jobs: where (in milliseconds) the output
video is actually scrambled vs passed through untouched.

Mirrors the per-frame logic in core/video_processor.process_video_file:
  ON(t)  = gate(t) AND cover(t)
  gate   = patch_intervals when set, else the whole timeline
  cover  = union of patch_segments WITH a roi when segments exist,
           else the whole timeline (global roi or full-frame scramble)

Segments without a roi, frames outside every active segment, and frames
outside patch_intervals are passthrough. Decrypt jobs don't write this
(they restore whatever the encrypt timeline scrambled).
"""


def _as_float_pair(item):
    try:
        s, e = float(item[0]), float(item[1])
    except Exception:
        return None
    if not (e > s):
        return None
    return (s, e)


def _merge(intervals):
    ivs = sorted(intervals)
    out = []
    for s, e in ivs:
        if out and s <= out[-1][1]:
            if e > out[-1][1]:
                out[-1][1] = e
        else:
            out.append([s, e])
    return [(s, e) for s, e in out]


def compute_encrypt_intervals(options, duration_sec):
    """(on_intervals_sec, duration_sec): merged encrypt-ON coverage."""
    try:
        dur = max(0.0, float(duration_sec or 0.0))
    except Exception:
        dur = 0.0
    if dur <= 0:
        return [], 0.0

    segs = options.get('patch_segments')
    cover = []
    if isinstance(segs, list) and segs:
        for s in segs:
            if not isinstance(s, dict):
                continue
            try:
                st, en = float(s.get('start', 0.0)), float(s.get('end', dur))
            except Exception:
                continue
            if en > st and s.get('roi'):
                cover.append((max(0.0, st), en))
        cover = _merge([(s, min(e, dur)) for s, e in cover if s < dur])
    else:
        # Global roi or full-frame scramble: spatially covered everywhere.
        cover = [(0.0, dur)]

    gates = options.get('patch_intervals')
    if gates:
        gate_list = []
        for item in gates:
            p = _as_float_pair(item)
            if p and p[0] < dur:
                gate_list.append((max(0.0, p[0]), min(p[1], dur)))
        gate_list = _merge(gate_list)
    else:
        gate_list = [(0.0, dur)]

    on = []
    for cs, ce in cover:
        for gs, ge in gate_list:
            s, e = max(cs, gs), min(ce, ge)
            if e > s:
                on.append((s, e))
    return _merge(on), dur


def render_timeline_txt(options, duration_sec, fps=None, source_name=""):
    """Full-coverage ms timeline text: every millisecond of the output is
    labeled either encrypt or passthrough (no gaps, sorted, merged)."""
    on, dur = compute_encrypt_intervals(options, duration_sec)
    dur_ms = int(round(dur * 1000))
    try:
        fps_f = float(fps) if fps else 0.0
    except Exception:
        fps_f = 0.0

    segs = options.get('patch_segments')
    n_seg = len(segs) if isinstance(segs, list) else 0
    gates = options.get('patch_intervals')
    n_gate = len(gates) if gates else 0
    has_roi = bool(options.get('patch_roi'))

    lines = [
        f"# encrypt timeline for {source_name or 'video'} (video encrypt on/off, milliseconds)",
        f"# duration_ms={dur_ms} fps={fps_f:.2f}",
        f"# source: patch_segments={n_seg} patch_intervals={n_gate} roi={'yes' if has_roi else 'no'}",
    ]
    cur = 0
    for s, e in on:
        s_ms = max(0, min(dur_ms, int(round(s * 1000))))
        e_ms = max(0, min(dur_ms, int(round(e * 1000))))
        if s_ms > cur:
            lines.append(f"{cur}-{s_ms} passthrough")
        if e_ms > s_ms:
            lines.append(f"{s_ms}-{e_ms} encrypt")
            cur = e_ms
        elif s_ms > cur:
            cur = s_ms
    if cur < dur_ms:
        lines.append(f"{cur}-{dur_ms} passthrough")
    if dur_ms <= 0:
        lines.append("0-0 passthrough")
    return "\n".join(lines) + "\n"


def export_timeline_txt(output_txt_path, options, duration_sec, fps=None, source_name=""):
    text = render_timeline_txt(options, duration_sec, fps=fps, source_name=source_name)
    with open(output_txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return output_txt_path
