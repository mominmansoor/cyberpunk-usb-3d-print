"""
Cyberpunk USB 3D print - parametric source.

Builds a two-sided circuit-trace USB enclosure in two lengths:
  v1  long  (~92 mm)
  v2  short (~70 mm)

Every part is a single colour. Layer stack, mirrored around the USB drive:
  face panel | middle layer (coloured paper / binder plastic / thin print) | body half | drive | body half | middle layer | face panel

Fit your own USB drive: change DRIVE_W, DRIVE_T and DRIVE_L in PROFILES["public"] below.
Requires: pip install manifold3d shapely trimesh numpy matplotlib
Run:      python3 cyberpunk_usb.py      -> stl/public/v1, stl/public/v2, middle-layer template PDF
"""
import os
import numpy as np
import manifold3d as m
from shapely.geometry import Polygon, LineString, box, Point
from shapely.geometry.polygon import orient
from shapely.ops import unary_union
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- shared parameters
# The drive pocket: a plain rectangular pocket at the front for a standard USB-A plug end or a
# slim USB stick (12 x 4.5 mm, 20 mm deep, 12 mm sticking out). Size it to YOUR drive:
#   DRIVE_W / DRIVE_T  width and thickness of the drive (measure with calipers)
#   DRIVE_L            total drive length (DRIVE_OUT of it sticks out of the body)
#   FIT_W              side clearance per side, RIB_H crush-rib height (snug fit)
# Set LOOP=True and the LOOP_HOLE_* values if your drive has a keyring loop: a peg through it
# then locks the drive in.
PROFILES = {
    "public":  dict(DRIVE_W=12.0, DRIVE_T=4.5, FIT_W=0.1, RIB_H=0.25, DRIVE_L=32.0, DRIVE_OUT=12.0, LOOP=False,
                    LOOP_HOLE_L=0.0, LOOP_HOLE_W=0.0, LOOP_HOLE_C=0.0, SKIN_B=0.6, SKIN_T=0.6),
}
PEG_CLR     = 0.5     # clearance around the locking peg inside the loop (per side)
DRIVE_X     = 0.0     # sideways offset of the drive
FIT         = 0.1     # total top/bottom clearance on the drive's thickness (side clearance is FIT_W per profile)

RED_T    = 0.8            # red face panel (already printed - never change)
GREEN_T  = 0.3            # green strip step (binder + paper ~0.3 mm)
FACE     = RED_T + GREEN_T

PROFILE = None
def set_profile(name):
    """Switch every drive-dependent dimension to one of the PROFILES."""
    global PROFILE, DRIVE_W, DRIVE_T, DRIVE_L, DRIVE_OUT, LOOP, LOOP_HOLE_L, LOOP_HOLE_W, LOOP_HOLE_C
    global SKIN_B, SKIN_T, CAV_HALF, PLUG_HALF, H_B, H_T, TOTAL, SPLIT_Z, FIT_W, RIB_H
    p = PROFILES[name]
    PROFILE = name
    DRIVE_W, DRIVE_T, DRIVE_L, DRIVE_OUT = p["DRIVE_W"], p["DRIVE_T"], p["DRIVE_L"], p["DRIVE_OUT"]
    LOOP, LOOP_HOLE_L, LOOP_HOLE_W, LOOP_HOLE_C = p["LOOP"], p["LOOP_HOLE_L"], p["LOOP_HOLE_W"], p["LOOP_HOLE_C"]
    SKIN_B, SKIN_T = p["SKIN_B"], p["SKIN_T"]
    FIT_W, RIB_H = p["FIT_W"], p["RIB_H"]   # side clearance per side, crush-rib height
    CAV_HALF = (DRIVE_T + FIT) / 2         # drive pocket, split over both halves at the drive's mid-plane
    PLUG_HALF = CAV_HALF
    H_B = CAV_HALF + SKIN_B + FACE         # bottom half height
    H_T = CAV_HALF + SKIN_T + FACE         # top half height (no skin = window onto the drive)
    TOTAL = H_B + H_T
    SPLIT_Z = H_B                          # split plane (physical z)

def Hs(side):
    return H_B if side == "bottom" else H_T

set_profile("public")
CLR      = 0.15
GREEN_INSET = 0.8         # green sheet kept this far inside the outer body edge

SLOT_W     = 0.85         # trace channel width
MIN_ISLAND = 0.8          # drop red slivers smaller than this (mm2)
TIE_W      = 0.6          # bridges ("dots") that tie the loose red pieces into one panel: narrow,
TIE_T      = RED_T        # ...but full panel height (flush with the face) so they stay strong
TIE_MAX    = 3            # bridges per loose piece

# Snap pins are built into the bottom half: each stands up from the split face, split into two
# barbed prongs that click past a ledge inside a shaped hole in the top half. They print upright,
# so the prongs are kept wide with a small barb to keep the bending gentle (~1 %).
SNAP_T    = 1.4     # pin thickness
SNAP_NW   = 1.8     # pin width at the neck (two prongs + slit)
SNAP_B    = 0.15    # barb height per side (how far it catches)
SNAP_L    = 2.6     # pin length above the split face
SNAP_SLIT = 2.2     # slit length from the tip (prong flex length)
SNAP_SW   = 0.5     # slit width
SNAP_UC   = 1.5     # distance from the split face to the barb's widest point
SNAP_CLR  = 0.075   # clearance per side in the hole neck

# v2 sliding joint: two dovetail rails run back from each silver front frame and slide lengthwise
# into channels in the red rear body (inside the body, under the microSD slot), then click home.
SLIDE_X      = (-8.6, 8.9)             # rail centre lines: left beside the drive, right into the rear's side strip
SLIDE_LEN    = 9.5                     # how far the rails reach into the rear body
def slide_z(side):                     # channel bottom/top in a half (local z from the outer face)
    return (FACE + 0.6, Hs(side))
SLIDE_W      = (3.5, 2.4)              # channel width at bottom / at top (dovetail: can't lift out)
SLIDE_CLR    = 0.12                    # sliding clearance
SLIDE_BUMP   = 0.12                    # click bump on the rail side
DOVE_CLR     = 0.12

BRIDGE_V2_Y = 13.6                     # v2 microSD bridge centre (from the back end)
RAIL_GROOVE = 0.5                      # v2 bottom: depth of the groove the rail insert presses into

# microSD bridge
SD_W, SD_L, SD_T = 11.0, 15.0, 1.0     # card size
SD_CLR   = 0.2
TRAY_T   = 2.0                         # tray: 0.9 floor + 1.1 card recess
SLOT_T   = TRAY_T + 0.3                # slot height in the body (extra 0.1 so a slightly sagged slot roof can't bind)
PLATE_T  = 0.8                         # side plate of the clip
WRAP_T   = 0.8                         # wraps over top and bottom faces (inside the recess)
WRAP_REC = 0.95                        # recess depth for the wraps
RIDGE_H  = 0.8                         # grip bump stands this far proud of each face
BUMP_IN  = 0.7                         # bump top is inset this much on every side -> trapezium profile
RAIL     = 2.0                         # tray side rails (carry the snap latches)
# snap latch: a cantilever arm on each side of the tray with a hook at its free end.
# u = distance from the side plate into the body.
# Long, slim arms keep the bending strain ~0.5 %, safe for PLA even across layer lines.
LATCH_FIX, LATCH_FREE = 1.0, 10.0      # arm runs from u=1 (fixed) to u=10 (free end)
HOOK_H   = 0.35                        # how far the hook catches behind the ledge
HOOK_STEEP = 0.2                       # retaining face: 0.35 over 0.2 -> ~60 deg (won't shake loose)
HOOK_RAMP  = 1.2                       # lead-in ramp: ~16 deg, pushes in easily
ARM_W    = 0.8                         # arm thickness (flexes sideways)
ARM_GAP  = 0.5                         # gap behind the arm

# ---------------------------------------------------------------- trace pattern
# Digitised from the old-file drawing (3x zoom pixel coords). X along (USB end = high X), Y across.
# All three lines now run out to the USB end.
PATTERN = {
    "A": [(60, 185), (205, 185), (240, 136), (400, 136), (420, 160), (610, 160), (625, 136),
          (725, 136), (830, 245), (870, 245), (880, 265), (965, 265), (985, 233), (1045, 233),
          (1065, 262), (1095, 233), (1180, 233)],
    "B": [(60, 205), (230, 205), (260, 157), (305, 157), (345, 232), (405, 232), (430, 267),
          (640, 267), (690, 166), (885, 166), (910, 208), (1180, 208)],
    "C": [(60, 230), (285, 230), (310, 261), (360, 261), (415, 189), (570, 189), (605, 238),
          (740, 238), (760, 214), (830, 214), (855, 184), (930, 184), (950, 155), (990, 155),
          (1000, 180), (1020, 180), (1045, 146), (1060, 162), (1180, 162)],
}
PAT_CY = 200.5

def pattern_lines(across, x0, y_of_X):
    return {k: [(x0 + (Y - PAT_CY) * across, y_of_X(X)) for X, Y in pts] for k, pts in PATTERN.items()}

# ---------------------------------------------------------------- helpers
def to_cs(geom):
    polys = [geom] if geom.geom_type == "Polygon" else [g for g in geom.geoms if g.area > 1e-6]
    contours = []
    for p in polys:
        p = orient(p, 1.0)
        contours.append(np.array(p.exterior.coords[:-1]))
        contours += [np.array(r.coords[:-1]) for r in p.interiors]
    return m.CrossSection(contours, m.FillRule.EvenOdd)

def prism(geom, z0, h):
    return m.Manifold.extrude(to_cs(geom), h).translate((0, 0, z0))

def prism_y(pts_xz, y0, y1):
    """Extrude a polygon given in (x, z) along Y from y0 to y1."""
    cs = to_cs(Polygon([(x, -z) for x, z in pts_xz]))
    return m.Manifold.extrude(cs, y1 - y0).rotate((-90, 0, 0)).translate((0, y0, 0))

def circ(x, y, d):
    return Point(x, y).buffer(d / 2, 40)

def lines_shape(lines, width, pads=(), pad=1.8, extra=()):
    g = [LineString(l).buffer(width / 2, cap_style=2, join_style=2, mitre_limit=2.5) for l in lines]
    g += [box(x - pad / 2, y - pad / 2, x + pad / 2, y + pad / 2) for x, y in pads]
    g += list(extra)
    return unary_union(g)

def drop_small(geom, min_area):
    parts = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    return unary_union([p for p in parts if p.area >= min_area])

def xr(a, c):
    return (min(a, c), max(a, c))

def to_physical(local, side):
    """Half-pieces are modelled with the outer face at z=0 and the split face at z=H_B / H_T.
    Bottom: as is. Top: mirrored to sit above the split."""
    if side == "bottom":
        return local
    return local.mirror((0, 0, 1)).translate((0, 0, TOTAL))

def snap_pin_profile():
    """2D outline of a snap pin in (u, w): u along the pin (0 = split face), w across (flex direction)."""
    L, uc, nw, b = SNAP_L, SNAP_UC, SNAP_NW / 2, SNAP_B
    end = Polygon([(-0.01, nw), (uc - 0.25, nw), (uc, nw + b), (L, 0.5), (L, -0.5), (uc, -nw - b),
                   (uc - 0.25, -nw), (-0.01, -nw)])
    end = end.difference(box(L - SNAP_SLIT, -SNAP_SW / 2, L + 0.1, SNAP_SW / 2))
    return unary_union([end, affinity.scale(end, -1, 1, origin=(0, 0))])

def snap_pin(x, y):
    """Pin standing up from the bottom half's split face (physical coords). The lower 0.6 mm is
    fused into the half, and a small collar at the base stiffens the root."""
    L, uc, nw, b = SNAP_L, SNAP_UC, SNAP_NW / 2, SNAP_B
    end = Polygon([(-0.6, nw), (uc - 0.25, nw), (uc, nw + b), (L, 0.75), (L, -0.75), (uc, -nw - b),
                   (uc - 0.25, -nw), (-0.6, -nw)])
    end = end.difference(box(L - SNAP_SLIT, -SNAP_SW / 2, L + 0.1, SNAP_SW / 2))
    pin = m.Manifold.extrude(to_cs(end), SNAP_T).translate((0, 0, -SNAP_T / 2)).rotate((0, -90, 0))  # u -> Z, w -> Y
    collar = prism(box(-SNAP_T / 2 - 0.12, -nw - 0.12, SNAP_T / 2 + 0.12, nw + 0.12), -0.6, 0.6 + 0.2)
    return (pin + collar).translate((x, y, H_B))

def snap_hole(x, y):
    """Shaped hole in a half (local coords, split face at z=H_B / H_T): a neck the prongs squeeze through,
    then a wider chamber where the barbs spring out and catch."""
    H = H_T                                   # holes are always in the top half
    tx = SNAP_T / 2 + SNAP_CLR
    neck_w = SNAP_NW / 2 + SNAP_CLR
    ch_w = SNAP_NW / 2 + SNAP_B + 0.15
    neck_d = SNAP_UC - 0.15        # barb catch face sits right on the ledge: halves pull tight, no play
    depth = SNAP_L + 0.2
    neck = prism(box(x - tx, y - neck_w, x + tx, y + neck_w), H - neck_d, neck_d + 1)
    chamber = prism(box(x - tx, y - ch_w, x + tx, y + ch_w), H - depth, depth - neck_d + 0.01)
    lead = prism(box(x - tx - 0.15, y - neck_w - 0.15, x + tx + 0.15, y + neck_w + 0.15), H - 0.25, 1)  # chamfer-ish lead-in
    return neck + chamber + lead

# ================================================================= common design
class Design:
    side_sign = +1        # side the bridge sits on (+1 = +X)

    # ---- inlay regions
    def green_region(self):
        return self.pocket().intersection(self.outline().buffer(-GREEN_INSET, join_style=2))

    def green_sheet_2d(self):
        g = self.green_region().buffer(-CLR - 0.02, join_style=2)
        for h in self.through_holes():
            g = g.difference(h.buffer(CLR, join_style=2))
        return g

    def red_panel_2d(self):
        g = self.pocket().buffer(-CLR, join_style=2).intersection(self.outline().buffer(-CLR, join_style=2))
        g = g.difference(self.channels(SLOT_W))
        for h in self.through_holes():
            g = g.difference(h.buffer(CLR, join_style=2))
        return drop_small(g, MIN_ISLAND)

    def through_holes(self):
        return []

    # ---- bridge (2D regions in physical XY)
    def bridge_regions(self):
        b = self.bridge_spec()
        s, e = self.side_sign, b["edge"]
        y0, y1 = b["y0"], b["y1"]
        inner = e - s * PLATE_T
        U = lambda u: inner - s * u                     # u: distance from the plate into the body
        def ubox(u0, u1, ya, yb):
            x = xr(U(u0), U(u1)); yy = (min(ya, yb), max(ya, yb))
            return box(x[0], yy[0], x[1], yy[1])
        across = SD_W if b["card_across"] == "W" else SD_L
        depth = across + SD_CLR + 0.3 + 0.6
        plate = box(*[xr(e, inner)[0], y0, xr(e, inner)[1], y1])
        wy0, wy1 = b.get("wrap_y", (y0, y1))
        wx = xr(e, e - s * b["wrap_reach"])
        wrap = box(wx[0], wy0, wx[1], wy1)
        tray = ubox(-0.01, depth, y0, y1)
        card = ubox(0.3, depth - 0.6, y0 + RAIL, y1 - RAIL)
        hooks, cuts = [], []
        u_steep = LATCH_FREE - HOOK_RAMP - HOOK_STEEP
        for ye, out in ((y0, -1), (y1, +1)):
            hooks.append(Polygon([(U(u_steep), ye - out * 0.1), (U(u_steep), ye),
                                  (U(LATCH_FREE - HOOK_RAMP), ye + out * HOOK_H),
                                  (U(LATCH_FREE), ye), (U(LATCH_FREE), ye - out * 0.1)]))
            # slot behind the arm, and the cut that frees its end
            cuts.append(ubox(LATCH_FIX, LATCH_FREE + ARM_GAP, ye - out * ARM_W, ye - out * (ARM_W + ARM_GAP)))
            cuts.append(ubox(LATCH_FREE, LATCH_FREE + ARM_GAP, ye + out * 1.0, ye - out * (ARM_W + ARM_GAP)))
        hooks, cuts = unary_union(hooks), unary_union(cuts)
        ledges = hooks.buffer(0.1, join_style=2)          # catch pockets in the body slot walls
        slot = tray.buffer(CLR, join_style=2).union(ledges)
        return dict(plate=plate, wrap=wrap, tray=tray, card=card, hooks=hooks, cuts=cuts, slot=slot,
                    plate_rec=plate.buffer(CLR, join_style=2), wrap_rec=wrap.buffer(CLR, join_style=2),
                    wrap_mid=(wx[0] + wx[1]) / 2)

    def bridge(self):
        r, b = self.bridge_regions(), self.bridge_spec()
        clip = prism(r["plate"], 0, TOTAL)
        # wraps fill the face recess; on each face a small trapezium-section bump stands RIDGE_H proud
        clip += prism(r["wrap"], 0, WRAP_T)
        clip += prism(r["wrap"], TOTAL - WRAP_T, WRAP_T)
        wx0, wy0, wx1, wy1 = r["wrap"].bounds
        top = box(wx0 + BUMP_IN, wy0 + BUMP_IN, wx1 - BUMP_IN, wy1 - BUMP_IN)
        for base_z, sgn in ((TOTAL, 1), (0.0, -1)):
            foot = prism(r["wrap"], base_z - (0.01 if sgn > 0 else 0), 0.01)
            cap = prism(top, base_z + sgn * RIDGE_H - (0.01 if sgn > 0 else 0), 0.01)
            clip += m.Manifold.batch_hull([foot, cap])
        zc = SPLIT_Z
        tray = prism(r["tray"].union(r["hooks"]).difference(r["cuts"]), zc - TRAY_T / 2, TRAY_T)
        floor = zc - TRAY_T / 2 + (TRAY_T - 1.1)
        tray -= prism(r["card"], floor, 5)
        # lower the far end wall to a 0.4 mm lip so the card can be slid in from the tip and dropped in place
        s_, b_ = self.side_sign, self.bridge_spec()
        cx0, cy0, cx1, cy1 = r["card"].bounds
        tip_wall = box(cx0 - 0.7, cy0, cx0 + 0.01, cy1) if s_ > 0 else box(cx1 - 0.01, cy0, cx1 + 0.7, cy1)
        tray -= prism(tip_wall, floor + 0.4, 5)
        clip += tray
        return clip

    def card_ref(self):
        c = self.bridge_regions()["card"].buffer(-0.1, join_style=2)
        return prism(c, SPLIT_Z - TRAY_T / 2 + (TRAY_T - 1.1) + 0.05, SD_T)

    # ---- body half (local: outer face z=0, split face z=H_HALF)
    def half_local(self, region, side):
        H = Hs(side)
        p = prism(region, 0, H)
        p -= prism(self.pocket(), -1, 1 + RED_T)
        p -= prism(self.green_region().buffer(-0.02, join_style=2), -1, 1 + FACE)
        p -= prism(self.drive_cavity(), H - CAV_HALF, 5)
        if H - CAV_HALF <= FACE + 1e-6:          # window half: open the whole pocket area over the drive cleanly
            p -= prism(self.pocket().intersection(self.drive_cavity()), -1, 1 + FACE + 0.01)
        p -= prism(self.plug_cavity(), H - PLUG_HALF, 5)
        r = self.bridge_regions()
        p -= prism(r["slot"], H - SLOT_T / 2, 5)
        p -= prism(r["plate_rec"], -1, 10)
        p -= prism(r["wrap_rec"], -1, 1 + WRAP_REC)
        for h in self.through_holes():
            p -= prism(h, -1, 10)
        if side == "top":
            for x, y in self.dowels():
                p -= snap_hole(x, y)
        p = self.decorate(p, side, region)
        p = self.drive_extras(p, region, side)
        if side == "bottom":                     # bottom half: local == physical, add the built-in pins
            for x, y in self.pins_in(region):
                p += snap_pin(x, y)
        return p

    def pins_in(self, region):
        return [(x, y) for x, y in self.dowels() if region.contains(Point(x, y))]

    def decorate(self, p, side, region):
        return p

    def tie_bridges(self):
        """Small bridges across the trace channels so every red piece joins the main panel."""
        from shapely.ops import nearest_points
        g = self.red_panel_2d()
        pieces = sorted([g] if g.geom_type == "Polygon" else list(g.geoms), key=lambda p: -p.area)
        joined, rest, ties = pieces[0], pieces[1:], []
        while rest:
            # connect the remaining piece closest to what is already joined
            rest.sort(key=lambda p: p.distance(joined))
            p = rest.pop(0)
            a, b = nearest_points(p, joined)
            # add more tie points spread along the piece (at least 3 mm apart), so it can't twist or snap off
            pts = [p.exterior.interpolate(t) for t in np.arange(0, p.exterior.length, 0.3)]
            cand = sorted([q for q in pts if q.distance(joined) < SLOT_W + 0.4], key=lambda q: q.distance(joined))
            spots = [(a, b)]
            for q in cand:
                if len(spots) >= TIE_MAX:
                    break
                if all(q.distance(x) > 3.0 for x, _ in spots):
                    spots.append(nearest_points(q, joined))
            for x, y in spots:
                v = np.array([y.x - x.x, y.y - x.y]); n = np.linalg.norm(v) or 1.0; v /= n
                s0 = (x.x - v[0] * 0.3, x.y - v[1] * 0.3); s1 = (y.x + v[0] * 0.3, y.y + v[1] * 0.3)
                ties.append(LineString([s0, s1]).buffer(TIE_W / 2, cap_style=2))
            joined = unary_union([joined, p] + ties)
        return unary_union(ties) if ties else Polygon()

    def face_panel(self, side):
        ties = self.tie_bridges()
        base = self.red_panel_2d()
        if ties.is_empty:
            return to_physical(prism(base, 0, RED_T), side)
        ties = ties.intersection(self.pocket().buffer(-CLR, join_style=2))
        if TIE_T >= RED_T:      # full height: merge in 2D for a clean single outline
            shape = unary_union([base, ties]).buffer(0.01, join_style=2).buffer(-0.01, join_style=2)
            return to_physical(prism(shape, 0, RED_T), side)
        return to_physical(prism(base, 0, RED_T) + prism(ties, RED_T - TIE_T, TIE_T), side)

    def green_sheet(self, side):
        return to_physical(prism(self.green_sheet_2d(), RED_T, GREEN_T), side)

    def drive_back(self):
        return self.LEN + DRIVE_OUT - DRIVE_L

    def drive_2d(self, front=None):
        y0 = self.drive_back()
        y1 = self.LEN if front is None else front
        return box(DRIVE_X - DRIVE_W / 2, y0, DRIVE_X + DRIVE_W / 2, y1)

    def drive_cavity(self):
        return self.drive_2d(front=self.LEN + 1).buffer(FIT_W, join_style=2)

    def plug_cavity(self):
        return self.drive_cavity()

    def loop_hole(self):
        yc = self.drive_back() + LOOP_HOLE_C
        return box(DRIVE_X - LOOP_HOLE_W / 2, yc - LOOP_HOLE_L / 2, DRIVE_X + LOOP_HOLE_W / 2, yc + LOOP_HOLE_L / 2)

    def drive_extras(self, p, region, side):
        """Crush ribs on the pocket sides (both halves) and the locking peg through the clip loop (bottom half)."""
        H = Hs(side)
        z0 = H - CAV_HALF
        x_wall = DRIVE_W / 2 + FIT_W
        y0, y1 = self.drive_back() + 4, self.LEN - 4
        clip = prism(region, -1, H + 5)
        ribs = []
        for y in np.linspace(y0, y1, 4):
            for sgn in (-1, 1):
                xw = DRIVE_X + sgn * x_wall
                if not region.contains(Point(xw + sgn * 0.4, y)):
                    continue                     # that wall belongs to the other body piece: it gets the rib
                tri = Polygon([(xw + sgn * 0.01, y - 0.5), (xw - sgn * RIB_H, y), (xw + sgn * 0.01, y + 0.5)])
                ribs.append(prism(tri.buffer(0), z0, CAV_HALF))
        for r_ in ribs:
            p += r_ ^ clip
        if side == "bottom" and LOOP:
            peg2d = self.loop_hole().buffer(-PEG_CLR, join_style=2)
            # keep the peg in one piece: only the body part that holds its centre gets it, trimmed to that part
            if region.contains(peg2d.centroid):
                peg2d = peg2d.intersection(region.buffer(-0.3, join_style=2))
                p += prism(peg2d, z0 - 0.01, 2 * CAV_HALF - 0.15)
        return p

    def chip(self):
        """Reference model of the drive (not printed), with its clip loop opening."""
        bar = prism(self.drive_2d(front=self.LEN + DRIVE_OUT), SPLIT_Z - DRIVE_T / 2, DRIVE_T)
        if LOOP:
            bar -= prism(self.loop_hole(), 0, TOTAL)
        return bar

# ================================================================= v1  (long)
class V1(Design):
    LEN, HW, RIDGE, NARROW = 92.0, 8.5, 1.5, 6.5
    SX = 11.4 / 8.5           # widened so the 20 mm drive fits (body core 22.8 mm)
    RIGHT_RIDGES = [(0.0, 7.5, True), (10.0, 20.5, False), (23.0, 28.5, False)]
    LEFT_RIDGES = [(12.0, 39.0, False)]
    # snap-pin positions (physical x, s from the USB end), all clear of the face pocket, drive and card slot
    DOWELS = [(-10.9, 25.0), (-10.8, 34.5), (11.8, 14.2), (11.8, 4.0), (10.5, 25.6), (-8.0, 85.0), (8.0, 85.0)]
    side_sign = +1

    def P(self, x, s):
        return (x * self.SX, self.LEN - s)

    def poly(self, pts):
        return Polygon([self.P(x, s) for x, s in pts])

    def rect(self, x0, s0, x1, s1):
        return box(x0 * self.SX, self.LEN - s1, x1 * self.SX, self.LEN - s0)

    def ridge(self, side, s0, s1, top_square):
        e, o = side * (self.HW - 0.2), side * (self.HW + self.RIDGE)
        a = s0 if top_square else s0 + self.RIDGE
        return self.poly([(e, s0), (o, a), (o, s1 - self.RIDGE), (e, s1)])

    def outline(self):
        HW = self.HW
        core = self.poly([(-HW, 0), (HW, 0), (HW, 87), (HW - 2.2, self.LEN), (-HW + 2.2, self.LEN), (-HW, 87)])
        g = unary_union([core] + [self.ridge(1, *r) for r in self.RIGHT_RIDGES]
                        + [self.ridge(-1, *r) for r in self.LEFT_RIDGES])
        return g.difference(self.poly([(-HW - 1, 79.5), (-HW + 1.2, 81.5), (-HW - 1, 83.5)]))

    def crown_notches(self):
        tooth = (2 * self.HW - 3 * 1.6) / 4
        return unary_union([self.rect(-self.HW + tooth * (i + 1) + 1.6 * i, -1,
                                      -self.HW + tooth * (i + 1) + 1.6 * (i + 1), 1.6) for i in range(3)])

    def pocket(self):
        W, N = self.HW + 0.3, self.NARROW
        return self.poly([(-N + 1.5, 3.0), (N - 1.5, 3.0), (N, 4.5), (N, 28.5), (W, 28.5),
                          (W, 58.0), (2.6, 58.0 + (W - 2.6)), (2.6, 87.0), (-2.6, 87.0),
                          (-2.6, 74.0), (-W, 74.0), (-W, 39.0), (-N, 39.0), (-N, 4.5)])

    def end_cap_outline(self):
        return self.rect(-6.0, 88.6, 6.0, self.LEN + 1)

    def lanyard(self):
        return self.rect(-1.3, 84.8, 1.3, 87.2)

    def window(self):
        return self.rect(-1.4, 76.5, 1.4, 79.5)

    def through_holes(self):
        return [self.lanyard()]

    def traces(self):
        s1, X0 = 56.0, 60
        along = 52.0 / 1045.0
        L = pattern_lines(0.077 * self.SX, 0.0, lambda X: self.LEN - (s1 - (X - X0) * along))
        bx, by = L["B"][0]
        L["B"] = [(bx, self.LEN - 77.0), (bx, by)] + L["B"]
        return L

    def channels(self, width):
        L = self.traces()
        return lines_shape(L.values(), width, pads=[L["A"][0], L["C"][0]],
                           extra=[self.window().buffer((width - SLOT_W) / 2, join_style=2)])

    def dowels(self):
        return [(x, self.LEN - s) for x, s in self.DOWELS]

    def bridge_spec(self):
        # the long dark-red block on the right side; card lies 15 mm along the stick
        return dict(edge=self.HW * self.SX, y0=self.LEN - 82.4, y1=self.LEN - 63.2, wrap_reach=4.5, card_across="W")

    def decorate(self, p, side, region):
        p -= prism(self.crown_notches(), -1, 1 + Hs(side) - CAV_HALF)     # cosmetic: stops at the drive
        p -= prism(self.end_cap_outline(), -1, 1 + RED_T)
        p -= prism(self.rect(3.25, 66.0, 3.65, 75.0).difference(self.bridge_regions()["wrap_rec"]), -1, 1.4)
        return p

    def end_cap(self, side):
        o = self.end_cap_outline().buffer(-CLR, join_style=2).intersection(self.outline())
        return to_physical(prism(o, 0, RED_T), side)

    def parts(self):
        out = {}
        for side in ("bottom", "top"):
            out[f"half_{side}"] = (to_physical(self.half_local(self.outline(), side), side), "Silver", side)
            out[f"face_{side}"] = (self.face_panel(side), "Red", side)
            out[f"green_{side}"] = (self.green_sheet(side), "Green", side)
            out[f"endcap_{side}"] = (self.end_cap(side), "Red", side)
        out["bridge"] = (self.bridge(), "Dark red", "bridge")
        return out

# ================================================================= v2  (short)
class V2(Design):
    """Drawn from the old-file picture (zoom px). Picture top edge -> model -X side."""
    K = 20.0 / 335.0
    XC, YC = 15.0, 212.5
    LEN = (1180 - 15) * K
    SX = 1.2                  # widened so the 20 mm drive fits (body 24 mm)
    NOTCH_Y, FRONT_T, FRONT_B = 55, 55, 370   # shallower notches/front step (were 80 / 85 / 345)
    side_sign = -1
    DOWEL_PX = [(200, 69), (330, 69), (250, 355), (620, 355)]

    def Z(self, X, Y):
        return ((Y - self.YC) * self.K * self.SX, (X - self.XC) * self.K)

    def zpoly(self, pts):
        return Polygon([self.Z(*p) for p in pts])

    def zbox(self, X0, Y0, X1, Y1):
        (a, b), (c, d) = self.Z(X0, Y0), self.Z(X1, Y1)
        return box(min(a, c), min(b, d), max(a, c), max(b, d))

    def outline(self):
        n, ft, fb = self.NOTCH_Y, self.FRONT_T, self.FRONT_B
        return self.zpoly([(15, 75), (45, 45), (775, 45), (790, n), (830, n), (845, 40), (890, 40),
                           (905, n), (950, n), (965, 40), (1035, 40), (1050, ft), (1180, ft),
                           (1180, fb), (1060, fb), (1040, 380), (45, 380), (15, 350)])

    def tab(self):
        return self.zbox(845, 323, 875, 400)

    def pocket(self):
        p = self.zpoly([(40, 100), (1130, 100), (1130, 330), (1050, 330), (1045, 335), (40, 335)])
        return p.difference(self.tab().buffer(0.5, join_style=2))

    def joint_y(self):
        return (660 - self.XC) * self.K        # joint line between rear body and front frame

    def strip_end_y(self):
        return (845 - self.XC) * self.K        # front end of the rear body's right-hand strip

    def rail_joint(self, cx):
        return self.joint_y() if cx < 0 else self.strip_end_y()

    def slide_channel(self, cx, side):
        (z0, z1), (wb, wt) = slide_z(side), SLIDE_W
        yj = self.rail_joint(cx)
        return prism_y([(cx - wb / 2, z0), (cx + wb / 2, z0), (cx + wt / 2, z1 + 0.01), (cx - wt / 2, z1 + 0.01)],
                       yj - SLIDE_LEN - 0.3, yj + 0.5)

    def slide_rail(self, cx, out_sign, side):
        (z0, z1), (wb, wt) = slide_z(side), SLIDE_W
        c = SLIDE_CLR
        yj = self.rail_joint(cx)
        # dovetail rail, slightly undersized; top stays below the microSD slot floor
        rail = prism_y([(cx - wb / 2 + c, z0 + c), (cx + wb / 2 - c, z0 + c),
                        (cx + wt / 2 - c, z1 - 0.005), (cx - wt / 2 + c, z1 - 0.005)], yj - SLIDE_LEN, yj + 0.6)   # flush with the split face: prints flat
        # click bump on the outer side near the tip; it springs into a notch at the end of the channel.
        # It follows the dovetail's slope so it stays attached whatever the half's height.
        yb = yj - SLIDE_LEN + 1.2
        zs = (z0 + 0.25, z0 + 0.95)
        zr0, zr1 = z0 + c, z1 - 0.005
        def hw(z):
            f = (z - zr0) / (zr1 - zr0)
            return (wb / 2 - c) + f * ((wt / 2 - c) - (wb / 2 - c))
        slabs = []
        for z in zs:
            xi = cx + out_sign * (hw(z) - 0.3)
            xo = cx + out_sign * (hw(z) + c + SLIDE_BUMP)     # past the clearance, into the channel wall
            prof = Polygon([(xi, yb - 0.9), (xo, yb - 0.2), (xo, yb + 0.1), (xi, yb + 0.3)]).buffer(0)
            slabs.append(prism(prof, z - 0.005, 0.01))
        return rail + m.Manifold.batch_hull(slabs)

    def slide_notch(self, cx, out_sign, side):
        (z0, z1), (wb, wt) = slide_z(side), SLIDE_W
        yb = self.rail_joint(cx) - SLIDE_LEN + 1.2
        # notch in the channel wall, following the dovetail slope
        def cw(z):
            f = (z - z0) / (z1 - z0)
            return wb / 2 + f * (wt / 2 - wb / 2)
        slabs = []
        for z in (z0 + 0.15, z0 + 1.1):
            x0, x1 = sorted([cx + out_sign * (cw(z) - 0.2), cx + out_sign * (cw(z) + SLIDE_BUMP + 0.08)])
            slabs.append(prism(box(x0, yb - 1.05, x1, yb + 0.42), z - 0.005, 0.01))
        return m.Manifold.batch_hull(slabs)

    def red_region(self):
        # right-hand strip starts at the drive pocket wall, so no paper-thin silver sliver is left between them
        strip = box(DRIVE_X + DRIVE_W / 2 + FIT_W, 0, 99, self.strip_end_y())
        g = unary_union([self.zbox(0, 0, 660, 500), self.zbox(0, 300, 845, 500), strip])
        # the band around the silver tab goes to the silver frame too (otherwise a 0.4 mm red sliver is left)
        return self.outline().intersection(g).difference(self.tab().buffer(0.6, join_style=2))

    def traces(self):
        return pattern_lines(1.4 * self.K * self.SX, (217.5 - self.YC) * self.K * self.SX, lambda X: (X - self.XC) * self.K)

    def channels(self, width):
        return lines_shape(self.traces().values(), width)

    # snap-pin spots (physical x, y), clear of the microSD slot, the drive and the sliding rail
    PINS_XY = [(-10.0, 3.6), (-9.9, 25.3), (10.3, 5.5), (10.3, 21.0), (10.3, 34.5)]

    def dowels(self):
        return list(self.PINS_XY)

    def bridge_spec(self):
        # the small block at the end of the top rail; card lies 11 mm along, 15 mm across
        yc = BRIDGE_V2_Y                   # moved back so the drive passes in front of it
        L = SD_W + SD_CLR + 2 * RAIL
        return dict(edge=-10.0 * self.SX, y0=yc - L / 2, y1=yc + L / 2, wrap_reach=2.8, card_across="L",
                    wrap_y=(yc - 2.5, yc + 2.5))

    def decorate(self, p, side, region):
        r = self.bridge_regions()
        rail = self.zbox(60, 48, 610, 88).intersection(region).difference(
            r["wrap_rec"].buffer(0.3)).difference(r["plate_rec"].buffer(0.3))
        if rail.is_empty or rail.area < 1e-3:
            return p
        if side == "bottom":                     # bottom face stays flat (it prints face down)
            return p
        return p + prism(rail, -0.5, 0.51)

    def rail_insert(self):
        r = self.bridge_regions()
        rail = self.zbox(60, 48, 610, 88).intersection(self.red_region().buffer(-0.1, join_style=2)).difference(
            r["wrap_rec"].buffer(0.3)).difference(r["plate_rec"].buffer(0.3))
        return prism(rail.buffer(-0.02, join_style=2), -0.5, 0.5 + RAIL_GROOVE - 0.05)

    def parts(self):
        out = {}
        red = self.red_region().buffer(-0.1, join_style=2)
        silver = self.outline().difference(self.red_region()).buffer(-0.1, join_style=2).intersection(self.outline())
        for side in ("bottom", "top"):
            rear = self.half_local(red, side)
            front = self.half_local(silver, side)
            for cx, sgn in zip(SLIDE_X, (-1, 1)):
                rear -= self.slide_channel(cx, side) + self.slide_notch(cx, sgn, side)
                front += self.slide_rail(cx, sgn, side)
            out[f"rear_{side}"] = (to_physical(rear, side), "Red", side)
            out[f"front_{side}"] = (to_physical(front, side), "Silver", side)
            out[f"face_{side}"] = (self.face_panel(side), "Dark red", side)
            out[f"green_{side}"] = (self.green_sheet(side), "Green", side)
        out["bridge"] = (self.bridge(), "Dark red", "bridge")
        return out

# ---------------------------------------------------------------- print poses + export
def lay(man):
    bb = man.bounding_box()
    return man.translate((-(bb[0] + bb[3]) / 2, -(bb[1] + bb[4]) / 2, -bb[2]))

def snap_pin_set(n):
    """n pins lying flat in a row, ready to print (2 spares included by the caller)."""
    out = None
    for i in range(n):
        p = snap_pin_flat().translate((0, i * (SNAP_NW + 2 * SNAP_B + 2.0), 0))
        out = p if out is None else out + p
    return out

def print_pose(D, name, man):
    # bottom halves print outer face down so the built-in pins point up (no rotation needed);
    # top halves print split face down.
    if name == "front_bottom":
        man = man.rotate((0, 180, 0))                      # front frames lie on their split face, rails on the bed
    if name == "face_bottom":
        man = man.rotate((0, 180, 0))                      # face panels: back (with the ties) on the bed
    if name == "bridge":
        man = man.rotate((0, 90 if D.side_sign > 0 else -90, 0))   # side plate on the bed, tray pointing up
    return lay(man)

def export(name, D, parts):
    import trimesh
    d = os.path.join(HERE, "stl", PROFILE, name)
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):
        os.remove(os.path.join(d, f))
    for k, (man, col, _) in parts.items():
        if k == "green_bottom":
            continue
        fname = f"{name}_green_sheet_optional_print_x2.stl" if k == "green_top" else f"{name}_{k}.stl"
        mm = print_pose(D, k, man).to_mesh()
        trimesh.Trimesh(np.array(mm.vert_properties)[:, :3], np.array(mm.tri_verts),
                        process=False).export(os.path.join(d, fname))

def template_pdf(path):
    """1:1 cut template for the green sheets (both faces, both versions)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    W, H = 210, 297
    fig = plt.figure(figsize=(W / 25.4, H / 25.4))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W); ax.set_ylim(0, H); ax.set_aspect("equal"); ax.axis("off")
    ax.text(15, H - 15, "Green sheet cut template  -  print at 100% (turn off 'fit to page')", fontsize=9)
    ax.text(15, H - 22, "Check the scale: this bar must measure 50 mm", fontsize=7)
    ax.plot([100, 150], [H - 21, H - 21], "k-", lw=1.2)
    ax.text(15, H - 28, "Colour the printed side green. That side faces OUT on both the top and the bottom.", fontsize=7)
    x = 18
    for name, D in (("v1", V1()), ("v2", V2())):
        g = D.green_sheet_2d()
        for side in ("top", "bottom"):
            gg = g if side == "top" else affinity.scale(g, -1, 1, origin=(0, 0))
            minx, miny, maxx, maxy = gg.bounds
            gg = affinity.translate(gg, x - minx, 40 - miny)
            for p in ([gg] if gg.geom_type == "Polygon" else gg.geoms):
                ax.fill(*p.exterior.xy, fc="#a6e6a6", ec="k", lw=0.4)
                for r in p.interiors:
                    ax.fill(*r.xy, fc="white", ec="k", lw=0.4)
            ax.text(x, 33, f"{name} {side}", fontsize=7)
            x += (maxx - minx) + 14
    fig.savefig(path)
    plt.close(fig)

if __name__ == "__main__":
    for prof in ("public",):
        set_profile(prof)
        for name, D in (("v1", V1()), ("v2", V2())):
            parts = D.parts()
            print(f"{prof} {name}: body {D.LEN:.1f} mm long, {TOTAL:.1f} mm thick")
            for k, (p, c, _) in parts.items():
                print(f"   {k:14s} {c:9s} {p.volume():7.1f} mm3  pieces={len(p.decompose())}")
            export(name, D, parts)
    template_pdf(os.path.join(HERE, "green_sheet_template.pdf"))
