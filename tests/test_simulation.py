from backend.app.simulation import FloodTwin, RISK_ORDER
from backend.app.scientific import horton_infiltration_mmhr, manning_full_flow_capacity

def run(t, rain=180):
    t.reset(rain,180)
    for _ in range(18): t.step(5)
    return t.state()

def test_zero_state_has_no_water():
    t=FloodTwin(); t.reset(0,180); s=t.state()
    assert s['surface_water_m3']==0 and s['flood_debt_m3']==0

def test_flood_debt_is_drainage_debt_not_surface_ponding():
    s=run(FloodTwin())
    assert s['flood_debt_m3'] == s['drainage_debt_m3'] == s['network_excess_m3']
    assert s['total_unresolved_water_m3'] >= s['surface_water_m3']

def test_surface_depth_matches_water_volume():
    t=FloodTwin(); s=run(t)
    for r in s['roads']:
        c=t.cells[r['id'].replace('r','c')]
        assert abs(r['depth_cm'] - c.water_m3/c.area_m2*100) < 0.11

def test_hydrology_uses_pervious_area_only():
    t=FloodTwin(); t.reset(100,180)
    before=sum(c.cumulative_infiltration_m3 for c in t.cells.values())
    t.step(5); after=sum(c.cumulative_infiltration_m3 for c in t.cells.values())
    assert after > before
    expected_upper=sum(c.area_m2*(1-c.imperviousness)*35/1000/3600*300 for c in t.cells.values())
    assert after <= expected_upper + 1e-6

def test_surcharge_spill_is_separately_accounted():
    t=FloodTwin(); s=run(t)
    spill=sum(n['cumulative_surcharge_spill_m3'] for n in s['nodes'])
    assert spill >= 0
    # Current network may relieve surcharge every step; if it spills, it is never counted as debt.
    for n in s['nodes']:
        assert not (n['surcharge_spill_m3'] > 0 and n['flood_debt_m3'] > 0)

def test_continuity_is_conserved():
    s=run(FloodTwin())
    assert abs(s['scientific']['continuity_error_pct']) < 1e-8

def test_forecast_does_not_mutate_live_state():
    t=FloodTwin(); t.reset(160,180); t.step(5)
    before=(t.minute,t.state()['flood_debt_m3'],t.state()['max_depth_cm'])
    t.forecast(); t.future_depth('r1',30)
    after=(t.minute,t.state()['flood_debt_m3'],t.state()['max_depth_cm'])
    assert before==after

def test_route_arrivals_positive_and_monotonic():
    t=FloodTwin(); t.reset(140,180); r=t.route('n3','n5')
    a=[x['arrival_min'] for x in r['arrival_profile']]
    assert a and all(x>0 for x in a) and a==sorted(a)

def test_route_uses_future_depth_and_baseline():
    t=FloodTwin(); t.reset(180,180); r=t.route('n3','n5')
    assert 'baseline_route' in r and 'baseline_arrival_profile' in r
    assert all('predicted_depth_cm' in x for x in r['arrival_profile'])

def test_calibration_updates_parameters_not_depth():
    t=FloodTwin(); t.reset(100,180); old_eff=sum(n.inlet_efficiency for n in t.nodes.values())
    old_depth=t.roads['r1'].depth_cm
    out=t.observe(40,'r1')
    assert out['accepted']
    assert sum(n.inlet_efficiency for n in t.nodes.values()) != old_eff
    assert t.roads['r1'].depth_cm == old_depth

def test_risk_order_is_explicit():
    assert RISK_ORDER['GREEN']<RISK_ORDER['YELLOW']<RISK_ORDER['ORANGE']<RISK_ORDER['RED']

def test_closure_changes_network_availability():
    t=FloodTwin(); t.reset(140,180); before=t.route('n3','n5')['road_ids']
    t.set_closure('r5',True); after=t.route('n3','n5')['road_ids']
    assert before != after or not before

def test_scientific_equations_are_explicit():
    assert horton_infiltration_mmhr(35,6,1.2,0) == 35
    assert horton_infiltration_mmhr(35,6,1.2,100) >= 6
    assert manning_full_flow_capacity(.75,.003,.013) > 0

def test_model_card_and_swmm_export():
    from backend.app.swmm import build_swmm_input
    t=FloodTwin()
    inp=build_swmm_input(t)
    for section in ('[OPTIONS]','[JUNCTIONS]','[OUTFALLS]','[CONDUITS]','[XSECTIONS]','[RAINGAGES]','[SUBCATCHMENTS]','[SUBAREAS]','[INFILTRATION]','[TIMESERIES]','[COORDINATES]'):
        assert section in inp
    assert 'FLOW_ROUTING DYNWAVE' in inp and 'RAIN_TS' in inp

def test_live_data_never_claims_live_in_demo():
    import asyncio
    from backend.app.rainfall import RainfallProvider
    p=RainfallProvider()
    assert asyncio.run(p.live())['mode']=='DEMO'

def test_rainfall_continues_during_road_closure():
    t=FloodTwin(); t.reset(100,180); t.set_closure('r1',True); before=t.cells['c1'].cumulative_rain_m3; t.step(5)
    assert t.cells['c1'].cumulative_rain_m3 > before

def test_validation_is_honest_without_observations():
    t=FloodTwin(); assert t.validation_summary()['status']=='NO_OBSERVATIONS'

def test_validation_metrics_from_observation():
    t=FloodTwin(); t.reset(100,180); t.observe(20,'r1'); v=t.validation_summary()
    assert v['n']==1 and set(v['metrics'])=={'mae_cm','rmse_cm','bias_cm'}

def test_horton_rejects_invalid_order():
    import pytest
    with pytest.raises(ValueError): horton_infiltration_mmhr(5,10,1,0)


def test_calibration_requires_observations():
    t=FloodTwin(); assert t.calibrate()['status']=='INSUFFICIENT_OBSERVATIONS'

def test_calibration_produces_holdout_metrics():
    t=FloodTwin(); t.reset(120,180)
    for _ in range(6):
        t.step(5)
        t.observe(12.0,'r1')
    out=t.calibrate()
    assert out['status']=='CALIBRATED' and out['holdout'] is not None
    assert out['holdout']['n'] >= 1

def test_empirical_uncertainty_uses_observations():
    t=FloodTwin(); t.reset(100,180)
    for _ in range(5):
        t.step(5); t.observe(10.0,'r1')
    assert t.uncertainty(t.rain_at(t.minute)) >= 2.0
