from .simulation import FloodTwin

def build_swmm_input(twin: FloodTwin) -> str:
    """Generate a complete, inspectable SWMM input skeleton for the demo network.
    It includes rainfall timeseries and network/subcatchment sections. Execution still
    requires an approved SWMM runtime and calibrated municipal data.
    """
    lines=[
        "[TITLE]","; Street-Level Urban Flood Digital Twin - SWMM reference input",
        "; Generated from the configured prototype network. Calibrate before operational use.","",
        "[OPTIONS]","FLOW_UNITS CMS","INFILTRATION HORTON","FLOW_ROUTING DYNWAVE",
        "START_DATE 01/01/2026","START_TIME 00:00:00",
        "REPORT_START_DATE 01/01/2026","REPORT_START_TIME 00:00:00","WET_STEP 00:05:00",
        "DRY_STEP 01:00:00","ROUTING_STEP 00:00:30","","[JUNCTIONS]",
        ";Name Elevation MaxDepth InitDepth SurDepth Aponded",
    ]
    for n in twin.nodes.values():
        if n.id == "n5": continue
        lines.append(f"{n.id} 0.000 2.000 0.000 0.000 0")
    lines += ["","[OUTFALLS]",";Name Elevation Type Stage Data Gated","n5 0.000 FREE * NO","",
              "[CONDUITS]",";Name FromNode ToNode Length Roughness InOffset OutOffset InitFlow MaxFlow"]
    for p in twin.pipes:
        lines.append(f"{p.id} {p.a} {p.b} {p.length_m:.1f} {p.roughness:.4f} 0 0 0 {p.capacity_m3s:.4f}")
    lines += ["","[XSECTIONS]",";Link Shape Geom1 Geom2 Geom3 Geom4 Barrels"]
    for p in twin.pipes:
        lines.append(f"{p.id} CIRCULAR {p.diameter_m:.3f} 0 0 0 1")
    lines += ["","[RAINGAGES]",";Name Format Interval SCF Source",
              "RG1 INTENSITY 00:05 1.0 RAIN_TS","",
              "[SUBCATCHMENTS]",";Name RainGage Outlet Area Imperv Width Slope CurbLen SnowPack"]
    for c in twin.cells.values():
        r=twin.roads[c.road_id]
        outlet=r.b
        area_ha=c.area_m2/10000
        lines.append(f"{c.id} RG1 {outlet} {area_ha:.5f} {c.imperviousness*100:.1f} 50 0.005 0")
    lines += ["","[SUBAREAS]",";Subcatch N-Imperv N-Perv S-Imperv S-Perv PctZero RouteTo PctRouted"]
    for c in twin.cells.values():
        lines.append(f"{c.id} 0.013 0.35 0.10 0.20 0.0 OUTLET 100")
    lines += ["","[INFILTRATION]",";Subcatch MaxRate MinRate Decay DryTime MaxInfil"]
    for c in twin.cells.values():
        lines.append(f"{c.id} {c.infiltration_f0_mmhr:.3f} {c.infiltration_fc_mmhr:.3f} {c.infiltration_decay_hr:.3f} 7 0")
    lines += ["","[TIMESERIES]",";Name Date Time Value"]
    for minute in range(0,twin.horizon+5,5):
        # SWMM INTENSITY expects rainfall intensity for the interval.
        lines.append(f"RAIN_TS 01/01/2026 {minute//60:02d}:{minute%60:02d} {twin.rain_at(minute):.3f}")
    lines += ["","[COORDINATES]",";Node X-Coord Y-Coord"]
    for n in twin.nodes.values():
        lines.append(f"{n.id} {n.lon:.6f} {n.lat:.6f}")
    lines += ["","[REPORT]","INPUT NO","CONTINUITY YES","FLOWSTATS YES","NODES ALL","LINKS ALL",""]
    return "\n".join(lines)
