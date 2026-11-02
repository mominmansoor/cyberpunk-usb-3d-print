"""
Build OrcaSlicer project files (.3mf) with one build plate per filament colour,
set up for a Flashforge Adventurer 5M Pro (0.4 nozzle, 220 x 220 bed).

Orca only creates plates from a 3MF that carries project settings, and it assigns
each part to the plate whose area it sits in. So this writes:
  * 3D/3dmodel.model                 meshes + their positions on each plate's area
  * Metadata/model_settings.config   plate list, plate names, object names
  * Metadata/project_settings.config the stock Orca profiles for the 5M Pro,
                                     "Generic PLA @Flashforge" and 0.20 mm Standard,
                                     flattened from Orca's own profile files
Run:  python3 make_orca_3mf.py <path-to-Orca-profiles/Flashforge>
"""
import json, os, sys, glob, zipfile, uuid
import numpy as np
import cyberpunk_usb as u

PROFILE_DIR = sys.argv[1]
PRINTER  = "Flashforge Adventurer 5M Pro 0.4 Nozzle"
PROCESS  = "0.20mm Standard @Flashforge AD5M Pro 0.4 Nozzle"
FILAMENT = "Generic PLA @Flashforge"
APP      = "OrcaSlicer-2.2.0"      # recognised as an Orca project by old and new releases
GAP      = 0.2                     # Orca's spacing between plates (fraction of bed width)
EDGE     = 8.0                     # keep parts this far from the bed edge
SPACING  = 10.0                    # gap between parts on a plate (room for brims/skirts, no path conflicts)

META = {"type", "name", "inherits", "from", "setting_id", "instantiation", "compatible_printers",
        "compatible_printers_condition", "compatible_prints", "compatible_prints_condition", "renamed_from"}

def load_profiles():
    names = {}
    for f in glob.glob(os.path.join(PROFILE_DIR, "*", "*.json")):
        with open(f) as fh:
            d = json.load(fh)
        names[d["name"]] = d
    return names

def flatten(names, name):
    chain = []
    while name:
        d = names[name]
        chain.append(d)
        name = d.get("inherits")
    out = {}
    for d in reversed(chain):
        for k, v in d.items():
            if k not in META:
                out[k] = v
    return out

def project_config():
    names = load_profiles()
    cfg = {}
    for n in (PRINTER, PROCESS, FILAMENT):
        cfg.update(flatten(names, n))
    fil = flatten(names, FILAMENT)
    cfg["filament_ids"] = [fil.get("filament_id", "")] if isinstance(fil.get("filament_id", ""), str) else fil["filament_id"]
    cfg.pop("filament_id", None)
    cfg.update({
        "name": "project_settings", "from": "project",
        "printer_settings_id": PRINTER, "print_settings_id": PROCESS, "filament_settings_id": [FILAMENT],
        "inherits_group": ["", "", ""], "different_settings_to_system": ["", "", ""],
    })
    if "filament_colour" not in cfg:
        cfg["filament_colour"] = ["#C8201A"]
    return cfg

def bed_size(cfg):
    pts = [tuple(map(float, p.split("x"))) for p in cfg["printable_area"]]
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return max(xs) - min(xs), max(ys) - min(ys), min(xs), min(ys)

def plate_origin(i, n, W, D):
    import math
    v = math.sqrt(n); r = round(v)
    cols = r + 1 if v > r else r
    row, col = divmod(i, cols)
    return col * W * (1 + GAP), -row * D * (1 + GAP)

def mesh_of(man):
    mm = man.to_mesh()
    V = np.array(mm.vert_properties)[:, :3].astype(float)
    F = np.array(mm.tri_verts).astype(int)
    V[:, 0] -= (V[:, 0].min() + V[:, 0].max()) / 2
    V[:, 1] -= (V[:, 1].min() + V[:, 1].max()) / 2
    V[:, 2] -= V[:, 2].min()
    return V, F

def layout(meshes, W, D):
    """Place parts in rows, left to right, the whole group centred on the bed."""
    sizes = [(np.ptp(V[:, 0]), np.ptp(V[:, 1])) for V, F in meshes]
    rows, cur, cur_w = [], [], 0.0
    for i, (w, d) in enumerate(sizes):
        if cur and cur_w + SPACING + w > W - 2 * EDGE:
            rows.append(cur); cur, cur_w = [], 0.0
        cur_w += (SPACING if cur else 0) + w
        cur.append(i)
    rows.append(cur)
    heights = [max(sizes[i][1] for i in r) for r in rows]
    total_h = sum(heights) + SPACING * (len(rows) - 1)
    pos = [None] * len(meshes)
    y = D / 2 + total_h / 2
    for r, h in zip(rows, heights):
        row_w = sum(sizes[i][0] for i in r) + SPACING * (len(r) - 1)
        x = W / 2 - row_w / 2
        for i in r:
            pos[i] = (x + sizes[i][0] / 2, y - h / 2)
            x += sizes[i][0] + SPACING
        y -= h + SPACING
    return pos

def build(name, D, plates, out_path):
    cfg = project_config()
    W, Dp, x0, y0 = bed_size(cfg)
    parts = D.parts()
    objects, items, plate_xml, obj_xml = [], [], [], []
    oid = 0
    for pi, (pname, keys) in enumerate(plates):
        meshes = []
        for k in keys:
            man = parts[k][0]
            meshes.append(mesh_of(u.print_pose(D, k, man)))
        ox, oy = plate_origin(pi, len(plates), W, Dp)
        inst = []
        for k, (V, F), (px, py) in zip(keys, meshes, layout(meshes, W, Dp)):
            oid += 1
            label = f"{name.replace(' ', '_')}_{k}"
            objects.append((oid, V, F))
            items.append((oid, ox + x0 + px, oy + y0 + py))
            obj_xml.append(
                f'  <object id="{oid}">\n    <metadata key="name" value="{label}"/>\n'
                f'    <metadata key="extruder" value="1"/>\n'
                + ('    <metadata key="enable_support" value="1"/>\n    <metadata key="support_type" value="normal(auto)"/>\n'
                   '    <metadata key="support_on_build_plate_only" value="1"/>\n    <metadata key="support_threshold_angle" value="30"/>\n'
                   '    <metadata key="support_top_z_distance" value="0.2"/>\n    <metadata key="support_interface_top_layers" value="2"/>\n'
                   '    <metadata key="support_interface_pattern" value="rectilinear"/>\n'
                   if k in ("half_bottom", "rear_bottom") else '')
                + f'    <part id="{oid}" subtype="normal_part">\n      <metadata key="name" value="{label}"/>\n'
                f'      <metadata key="matrix" value="1 0 0 0 0 1 0 0 0 0 1 0 0 0 0 1"/>\n    </part>\n  </object>\n')
            inst.append(f'    <model_instance>\n      <metadata key="object_id" value="{oid}"/>\n'
                        f'      <metadata key="instance_id" value="0"/>\n      <metadata key="identify_id" value="{100 + oid}"/>\n    </model_instance>\n')
        plate_xml.append(f'  <plate>\n    <metadata key="plater_id" value="{pi + 1}"/>\n'
                         f'    <metadata key="plater_name" value="{pname}"/>\n    <metadata key="locked" value="false"/>\n'
                         + "".join(inst) + '  </plate>\n')

    # ---- 3dmodel.model
    res = []
    for oid_, V, F in objects:
        vs = "".join(f'<vertex x="{a:.4f}" y="{b:.4f}" z="{c:.4f}"/>' for a, b, c in V)
        ts = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in F)
        res.append(f'  <object id="{oid_}" type="model" p:UUID="{uuid.uuid4()}">\n   <mesh><vertices>{vs}</vertices>'
                   f'<triangles>{ts}</triangles></mesh>\n  </object>\n')
    build_items = "".join(f'  <item objectid="{i}" p:UUID="{uuid.uuid4()}" transform="1 0 0 0 1 0 0 0 1 {x:.3f} {y:.3f} 0" printable="1"/>\n'
                          for i, x, y in items)
    model = ('<?xml version="1.0" encoding="UTF-8"?>\n'
             '<model unit="millimeter" xml:lang="en-US" xmlns="http://schemas.microsoft.com/3dmanufacturing/core/2015/02" '
             'xmlns:BambuStudio="http://schemas.bambulab.com/package/2021" '
             'xmlns:p="http://schemas.microsoft.com/3dmanufacturing/production/2015/06" requiredextensions="p">\n'
             f' <metadata name="Application">{APP}</metadata>\n'
             ' <metadata name="BambuStudio:3mfVersion">1</metadata>\n'
             f' <metadata name="Title">Cyberpunk USB 3D print {name.split()[-1]}</metadata>\n'
             ' <metadata name="Designer">mominmansoor</metadata>\n'
             ' <resources>\n' + "".join(res) + ' </resources>\n'
             f' <build p:UUID="{uuid.uuid4()}">\n' + build_items + ' </build>\n</model>\n')
    settings = '<?xml version="1.0" encoding="UTF-8"?>\n<config>\n' + "".join(obj_xml) + "".join(plate_xml) + '</config>\n'
    ctypes = ('<?xml version="1.0" encoding="UTF-8"?>\n<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">\n'
              ' <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>\n'
              ' <Default Extension="model" ContentType="application/vnd.ms-package.3dmanufacturing-3dmodel+xml"/>\n'
              ' <Default Extension="png" ContentType="image/png"/>\n</Types>\n')
    rels = ('<?xml version="1.0" encoding="UTF-8"?>\n<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">\n'
            ' <Relationship Target="/3D/3dmodel.model" Id="rel-1" Type="http://schemas.microsoft.com/3dmanufacturing/2013/01/3dmodel"/>\n'
            '</Relationships>\n')
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", ctypes)
        z.writestr("_rels/.rels", rels)
        z.writestr("3D/3dmodel.model", model)
        z.writestr("Metadata/model_settings.config", settings)
        z.writestr("Metadata/project_settings.config", json.dumps(cfg, indent=4))
    return items, W, Dp, objects

PLATES = {
    "v1": [("Silver - body halves", ["half_top", "half_bottom"]),
           ("Red - face panels and end caps", ["face_top", "face_bottom", "endcap_top", "endcap_bottom"]),
           ("Dark red - microSD bridge", ["bridge"]),
           ("Green - optional (or use paper)", ["green_top", "green_bottom"])],
    "v2": [("Silver - front frames", ["front_top", "front_bottom"]),
           ("Red - rear bodies", ["rear_top", "rear_bottom"]),
           ("Dark red - face panels and bridge", ["face_top", "face_bottom", "bridge"]),
           ("Green - optional (or use paper)", ["green_top", "green_bottom"])],
}

if __name__ == "__main__":
    here = os.path.dirname(os.path.abspath(__file__))
    for f in os.listdir(here):
        if f.startswith("cyberpunk-usb-3d-print_") and f.endswith(".3mf"):
            os.remove(os.path.join(here, f))
    for prof in ("public",):
        u.set_profile(prof)
        for name in ("v1", "v2"):
            D = u.V1() if name == "v1" else u.V2()
            out = os.path.join(here, f"cyberpunk-usb-3d-print_{name}_orca-flashforge-5m-pro.3mf")
            items, W, Dp, objs = build(f"cyberpunk_usb {name}", D, PLATES[name], out)
            print(out, "bed", W, Dp)
