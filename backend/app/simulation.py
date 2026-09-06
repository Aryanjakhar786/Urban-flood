from __future__ import annotations
from dataclasses import dataclass
from copy import deepcopy
import heapq
from math import ceil, exp, sqrt
from .scientific import horton_infiltration_mmhr, manning_full_flow_capacity, rainfall_depth_m3

DT_MIN = 5
FLOOD_THRESHOLD_CM = 20.0
CRITICAL_DEPTH_CM = 35.0
ROAD_FREE_SPEED_KMPH = 30.0
RISK_ORDER = {"GREEN": 0, "YELLOW": 1, "ORANGE": 2, "RED": 3}

@dataclass
class Cell:
    id: str; road_id: str; area_m2: float; imperviousness: float; elevation_m: float
    depression_storage_m3: float; water_m3: float = 0.0
    infiltration_f0_mmhr: float = 35.0; infiltration_fc_mmhr: float = 6.0; infiltration_decay_hr: float = 1.2
    cumulative_infiltration_m3: float = 0.0; cumulative_rain_m3: float = 0.0
    cumulative_runoff_m3: float = 0.0
    cumulative_inlet_capture_m3: float = 0.0
    surface_overflow_m3: float = 0.0
    ponded_above_depression_m3: float = 0.0

@dataclass
class Node:
    id: str; name: str; lon: float; lat: float; capacity_m3s: float
    inlet_efficiency: float; operational_storage_m3: float; storage_m3: float = 0.0
    surcharge: bool = False; flood_debt_m3: float = 0.0; surcharge_spill_m3: float = 0.0
    roughness: float = 0.03; cumulative_outfall_m3: float = 0.0; cumulative_surcharge_spill_m3: float = 0.0

@dataclass
class Pipe:
    id: str; a: str; b: str; capacity_m3s: float; length_m: float
    diameter_m: float = 0.75; slope: float = 0.004; roughness: float = 0.013

@dataclass
class Inlet:
    id: str; node_id: str; road_id: str; capture_fraction: float = 1.0

@dataclass
class Road:
    id: str; name: str; a: str; b: str; length_m: float; criticality: float
    elevation_m: float; width_m: float; cell_id: str; closed: bool = False
    depth_cm: float = 0.0; max_depth_cm: float = 0.0

NODES0 = {
    'n1': Node('n1','Central Junction',77.2090,28.6139,2.4,.88,300),
    'n2': Node('n2','Market Inlet',77.2140,28.6160,1.3,.82,180),
    'n3': Node('n3','Metro Junction',77.2050,28.6170,1.7,.86,220),
    'n4': Node('n4','Hospital Junction',77.2120,28.6085,1.1,.78,160),
    'n5': Node('n5','Outfall',77.2180,28.6100,3.0,.95,500),
}
ROADS0 = [
    Road('r1','MG Road','n1','n2',620,.90,0.0,7.0,'c1'),
    Road('r2','Market Street','n2','n5',760,.75,-.4,7.0,'c2'),
    Road('r3','Metro Road','n3','n1',580,.85,.2,7.0,'c3'),
    Road('r4','Hospital Road','n4','n1',690,1.0,-.1,7.0,'c4'),
    Road('r5','Ring Connector','n3','n4',820,.65,.5,7.0,'c5'),
    Road('r6','Safe Bypass','n4','n5',980,.55,.8,7.0,'c6'),
]
PIPES0 = [
    Pipe('p1','n3','n1',.25,580,.70,.004,.013), Pipe('p2','n1','n2',.28,620,.75,.003,.013),
    Pipe('p3','n2','n5',.20,760,.60,.0025,.014), Pipe('p4','n4','n1',.18,690,.55,.003,.014),
    Pipe('p5','n3','n4',.22,820,.65,.0035,.013), Pipe('p6','n4','n5',.25,980,.75,.004,.013),
]
CELLS0 = {
    r.cell_id: Cell(r.cell_id, r.id, max(r.length_m*r.width_m, 1000), .78,
                    r.elevation_m, max(15.0, r.length_m*r.width_m*.006))
    for r in ROADS0
}
INLETS0 = [Inlet(f'i{i+1}', r.b, r.id, 1.0) for i,r in enumerate(ROADS0)]

class FloodTwin:
    """Fast, transparent MVP digital twin. It is a lumped surface model, not a 2-D solver."""

    def __init__(self): self.reset()

    def reset(self, rainfall_mmhr=70, horizon=180):
        self.minute=0; self.rainfall_mmhr=float(rainfall_mmhr); self.horizon=int(horizon)
        self.nodes=deepcopy(NODES0); self.roads={r.id:deepcopy(r) for r in ROADS0}
        self.pipes=deepcopy(PIPES0); self.cells=deepcopy(CELLS0); self.inlets=deepcopy(INLETS0)
        self.observed_level=None; self.calibration_count=0; self.observations=[]
        self.history=[]; self._record()

    def rain_at(self,t):
        peak=self.rainfall_mmhr
        if t < 30: return peak*(.55+.45*t/30)
        if t < 90: return peak*(1+.22*(t-30)/60)
        if t < 135: return peak*(1.22-.32*(t-90)/45)
        return peak*max(.18,.90-.62*(t-135)/45)

    def rainfall_for_cell(self, cell_id, t):
        """Deterministic moving storm cell for spatially varying demo rainfall."""
        base=self.rain_at(t)
        idx=max(0,int(cell_id[1:])-1) if cell_id.startswith('c') else 0
        center=(t/45.0)%6.0
        distance=abs(idx-center)
        multiplier=0.72 + 0.48*exp(-(distance**2)/2.0)
        return base*multiplier

    def _road_for_pipe(self,pid):
        p=next(x for x in self.pipes if x.id==pid)
        for r in self.roads.values():
            if {r.a,r.b}=={p.a,p.b}: return r.id
        return next(iter(self.roads))

    def _pipe_open_for(self,p,roads):
        return not roads[self._road_for_pipe(p.id)].closed

    def _node_outflow(self,nid,nodes,roads):
        n=nodes[nid]; outs=[p for p in self.pipes if p.a==nid and self._pipe_open_for(p,roads)]
        if not outs: return 0.0
        caps=[]
        for p in outs:
            q=manning_full_flow_capacity(p.diameter_m,p.slope,max(n.roughness,p.roughness))
            caps.append(min(p.capacity_m3s,q))
        return min(n.storage_m3/(DT_MIN*60), min(n.capacity_m3s,sum(caps)))

    def _step_state(self,nodes,roads,cells,rainfall_unused):
        dt=DT_MIN*60
        incoming={k:0.0 for k in nodes}
        dt=DT_MIN*60
        # Rain falls even on a closed road. Closure affects traffic/routing and inlet
        # accessibility, not meteorology. Infiltration is limited to pervious area.
        for r in roads.values():
            c=cells[r.cell_id]
            rain=self.rainfall_for_cell(c.id,self.minute+DT_MIN)
            rain_m3=rainfall_depth_m3(rain,c.area_m2,DT_MIN)
            c.cumulative_rain_m3 += rain_m3
            pervious_area=c.area_m2*(1.0-c.imperviousness)
            infil_cap=horton_infiltration_mmhr(c.infiltration_f0_mmhr,c.infiltration_fc_mmhr,c.infiltration_decay_hr,self.minute/60.0)
            infil_m3=min(rain_m3*(1.0-c.imperviousness), rainfall_depth_m3(infil_cap,pervious_area,DT_MIN))
            c.cumulative_infiltration_m3 += infil_m3
            runoff=rain_m3-infil_m3
            c.cumulative_runoff_m3 += runoff
            c.water_m3 += runoff
            c.ponded_above_depression_m3=max(0.0,c.water_m3-c.depression_storage_m3)

        # Inlet capture draws from water above depression storage first. This keeps
        # the storage parameter physically meaningful without pretending the lumped
        # cell has 2-D surface routing.
        #  is capped by both hydraulic capacity and available ponded water.
        for inlet in self.inlets:
            if roads[inlet.road_id].closed: continue
            n=nodes[inlet.node_id]; c=cells[roads[inlet.road_id].cell_id]
            pipe_caps=[min(p.capacity_m3s,manning_full_flow_capacity(p.diameter_m,p.slope,max(n.roughness,p.roughness)))
                        for p in self.pipes if p.a==n.id and self._pipe_open_for(p,roads)]
            hydraulic_capacity=min(n.capacity_m3s, sum(pipe_caps)) if pipe_caps else 0.0
            capture=hydraulic_capacity*n.inlet_efficiency*inlet.capture_fraction*dt
            available=max(0.0,c.water_m3-c.depression_storage_m3)
            captured=min(available,max(0.0,capture))
            c.water_m3-=captured
            c.ponded_above_depression_m3=max(0.0,c.water_m3-c.depression_storage_m3)
            c.cumulative_inlet_capture_m3 += captured
            incoming[n.id]+=captured

        # Directed network routing. This is a transparent lumped approximation.
        order=['n3','n4','n1','n2','n5']
        for nid in order:
            n=nodes[nid]; n.storage_m3 += incoming[nid]
            out=self._node_outflow(nid,nodes,roads)
            moved=out*dt
            n.storage_m3-=moved
            outs=[p for p in self.pipes if p.a==nid and self._pipe_open_for(p,roads)]
            if outs and moved>0:
                capsum=sum(min(p.capacity_m3s,manning_full_flow_capacity(p.diameter_m,p.slope,max(n.roughness,p.roughness))) for p in outs)
                if capsum>0:
                    for p in outs:
                        pc=min(p.capacity_m3s,manning_full_flow_capacity(p.diameter_m,p.slope,max(n.roughness,p.roughness)))
                        nodes[p.b].storage_m3 += moved*pc/capsum

        # Explicit receiving-water boundary.
        out=nodes['n5']
        discharged=min(out.storage_m3,max(0.0,out.capacity_m3s*dt))
        out.storage_m3-=discharged; out.cumulative_outfall_m3+=discharged

        # Surcharge is drainage storage above operational storage. If connected surface exists,
        # the excess spills back and becomes surface ponding; otherwise it remains drainage debt.
        for nid,n in nodes.items():
            n.surcharge_spill_m3=0.0
            excess=max(0.0,n.storage_m3-n.operational_storage_m3)
            connected=[x for x in self.inlets if x.node_id==nid and not roads[x.road_id].closed]
            if excess and connected:
                share=excess/len(connected)
                for inlet in connected:
                    cc=cells[roads[inlet.road_id].cell_id]
                    cc.water_m3 += share
                    cc.ponded_above_depression_m3=max(0.0,cc.water_m3-cc.depression_storage_m3)
                n.storage_m3-=excess; n.surcharge_spill_m3=excess; n.cumulative_surcharge_spill_m3 += excess
            n.flood_debt_m3=max(0.0,n.storage_m3-n.operational_storage_m3)
            n.surcharge=n.flood_debt_m3>0

        for r in roads.values():
            c=cells[r.cell_id]
            c.ponded_above_depression_m3=max(0.0,c.water_m3-c.depression_storage_m3)
            r.depth_cm=max(0.0,c.water_m3/c.area_m2*100)
            r.max_depth_cm=max(r.max_depth_cm,r.depth_cm)
        return nodes,roads,cells

    def _simulate_from(self,steps,base_nodes=None,base_roads=None,base_cells=None,start_minute=None):
        nodes=deepcopy(self.nodes if base_nodes is None else base_nodes)
        roads=deepcopy(self.roads if base_roads is None else base_roads)
        cells=deepcopy(self.cells if base_cells is None else base_cells)
        t=self.minute if start_minute is None else start_minute
        original_minute=self.minute
        try:
            self.minute=t
            for _ in range(steps):
                t += DT_MIN
                self._step_state(nodes,roads,cells,self.rain_at(t))
                self.minute=t
        finally:
            self.minute=original_minute
        return nodes,roads,cells

    def step(self,minutes=5):
        if minutes not in (5,10,15): raise ValueError('minutes must be 5, 10 or 15')
        nodes,roads,cells=self._simulate_from(minutes//DT_MIN)
        self.nodes,self.roads,self.cells=nodes,roads,cells
        self.minute=min(self.horizon,self.minute+minutes); self._record(); return self.state()

    def future_depth(self,rid,arrival_min):
        target=min(self.horizon,self.minute+max(DT_MIN,int(ceil(arrival_min/DT_MIN))*DT_MIN))
        steps=max(0,(target-self.minute)//DT_MIN)
        _,roads,_=self._simulate_from(steps)
        return roads[rid].depth_cm

    def eta(self,r):
        for k in range(1,(self.horizon-self.minute)//DT_MIN+1):
            _,roads,_=self._simulate_from(k)
            if roads[r.id].depth_cm>=FLOOD_THRESHOLD_CM: return k*DT_MIN
        return None

    def uncertainty(self,rain):
        # Empirical residual scale when observations exist; otherwise a clearly labelled
        # conservative proxy. This is not a probabilistic confidence interval.
        if len(self.observations) >= 5:
            residuals=[o['predicted_cm']-o['observed_cm'] for o in self.observations]
            mean=sum(residuals)/len(residuals)
            rmse=sqrt(sum((e-mean)**2 for e in residuals)/max(1,len(residuals)-1))
            return round(max(2.0,1.96*rmse),1)
        rain_component=.015*rain
        data_component=1.0
        calibration_component=max(.5,2.5-self.calibration_count*.25)
        return round(1.5+rain_component+data_component+calibration_component,1)

    def risk(self,depth,criticality):
        if depth>=CRITICAL_DEPTH_CM: return 'RED'
        if depth>=FLOOD_THRESHOLD_CM: return 'ORANGE'
        if depth>=10 or depth+criticality*5>=16: return 'YELLOW'
        return 'GREEN'

    def _surface_water_m3(self): return sum(max(0,c.water_m3) for c in self.cells.values())
    def _network_debt_m3(self): return sum(max(0,n.flood_debt_m3) for n in self.nodes.values())
    def _network_storage_m3(self): return sum(max(0,n.storage_m3) for n in self.nodes.values())

    def state(self):
        rain=self.rain_at(self.minute); unc=self.uncertainty(rain)
        roads=[]
        for r in self.roads.values():
            eta=self.eta(r)
            roads.append({'id':r.id,'name':r.name,'a':r.a,'b':r.b,'length_m':r.length_m,'criticality':r.criticality,
              'depth_cm':round(r.depth_cm,1),'max_depth_cm':round(r.max_depth_cm,1),'risk':self.risk(r.depth_cm,r.criticality),
              'eta_to_flood_min':eta,'confidence':'HIGH' if unc<6 else 'MEDIUM' if unc<9 else 'LOW',
              'uncertainty_cm':unc,'closed':r.closed,'elevation_m':r.elevation_m,'width_m':r.width_m,'depression_storage_m3':round(self.cells[r.cell_id].depression_storage_m3,1),'surface_storage_fraction':round(min(1.0,self.cells[r.cell_id].water_m3/max(self.cells[r.cell_id].depression_storage_m3,1e-9)),3),'ponded_above_depression_m3':round(self.cells[r.cell_id].ponded_above_depression_m3,1)})
        nodes=[{'id':n.id,'name':n.name,'lat':n.lat,'lon':n.lon,'capacity_m3s':n.capacity_m3s,
          'inlet_efficiency':round(n.inlet_efficiency,3),'surcharge':n.surcharge,
          'surcharge_spill_m3':round(n.surcharge_spill_m3,1),'flood_debt_m3':round(n.flood_debt_m3,1),
          'storage_m3':round(n.storage_m3,1),'roughness':round(n.roughness,4),
          'cumulative_outfall_m3':round(n.cumulative_outfall_m3,1),'cumulative_surcharge_spill_m3':round(n.cumulative_surcharge_spill_m3,1)} for n in self.nodes.values()]
        surface=self._surface_water_m3(); network_debt=self._network_debt_m3()
        network_storage=self._network_storage_m3(); total_unresolved=surface+network_storage
        rain_total=sum(c.cumulative_rain_m3 for c in self.cells.values())
        infil_total=sum(c.cumulative_infiltration_m3 for c in self.cells.values())
        outfall_total=sum(n.cumulative_outfall_m3 for n in self.nodes.values())
        balance_error=rain_total-infil_total-outfall_total-total_unresolved
        balance_pct=(abs(balance_error)/rain_total*100) if rain_total else 0.0
        return {'minute':self.minute,'horizon':self.horizon,'rainfall_mmhr':round(rain,1),
          'max_depth_cm':round(max((r.depth_cm for r in self.roads.values()),default=0),1),
          'surface_water_m3':round(surface,3),'drainage_debt_m3':round(network_debt,3),'network_excess_m3':round(network_debt,3),
          'network_storage_m3':round(network_storage,3),'flood_debt_m3':round(network_debt,3),
          'total_unresolved_water_m3':round(total_unresolved,3),
          'confidence':'HIGH' if unc<6 else 'MEDIUM' if unc<9 else 'LOW','uncertainty_cm':unc,
          'roads':roads,'nodes':nodes,'history':self.history[-36:],
          'scientific':{'hydrology':'Horton infiltration on pervious area + explicit volume balance',
            'hydraulics':'Manning full-flow capacity; lumped network routing (not a 1-D/2-D solver)',
            'surface_model':'Lumped road surface cells with explicit depression-storage parameter',
            'rainfall_model':'Deterministic moving spatial storm for demo; replace with authorized gridded observations/nowcast',
            'cumulative_rain_m3':round(rain_total,3),'cumulative_infiltration_m3':round(infil_total,3),
            'cumulative_outfall_m3':round(outfall_total,3),'unresolved_storage_m3':round(total_unresolved,3),
            'cumulative_inlet_capture_m3':round(sum(c.cumulative_inlet_capture_m3 for c in self.cells.values()),3),
            'cumulative_surcharge_spill_m3':round(sum(n.cumulative_surcharge_spill_m3 for n in self.nodes.values()),3),
            'continuity_error_m3':round(balance_error,6),'continuity_error_pct':round(balance_pct,6),
            'flood_debt_definition':'Drainage storage above operational capacity after surcharge spill is Flood Debt.'}}

    def _record(self):
        sdepth=max((r.depth_cm for r in self.roads.values()),default=0)
        self.history.append({'minute':self.minute,'rainfall_mmhr':round(self.rain_at(self.minute),1),
          'max_depth_cm':round(sdepth,1),'flood_debt_m3':round(self._network_debt_m3(),1),
          'surface_water_m3':round(self._surface_water_m3(),1),'total_unresolved_water_m3':round(self._surface_water_m3()+self._network_storage_m3(),1)})

    def forecast(self):
        sim=deepcopy(self); out=[]
        while sim.minute<sim.horizon:
            sim.step(DT_MIN); s=sim.state()
            out.append({'minute':sim.minute,'rainfall_mmhr':s['rainfall_mmhr'],'max_depth_cm':s['max_depth_cm'],
                        'flood_debt_m3':s['flood_debt_m3'],'surface_water_m3':s['surface_water_m3'],
                        'total_unresolved_water_m3':s['total_unresolved_water_m3']})
        return out

    def _travel_min(self,r): return r.length_m/1000/ROAD_FREE_SPEED_KMPH*60

    def _profile(self,road_ids):
        details=[]; cumulative=0.0
        for rid in road_ids:
            cumulative += self._travel_min(self.roads[rid])
            arrival=max(DT_MIN,ceil(cumulative/DT_MIN)*DT_MIN)
            depth=self.future_depth(rid,arrival)
            details.append({'road_id':rid,'name':self.roads[rid].name,'arrival_min':arrival,
                            'predicted_depth_cm':round(depth,1),'risk':self.risk(depth,self.roads[rid].criticality)})
        return details

    def shortest_route(self,start='n3',destination='n5'):
        adj={}
        for r in self.roads.values():
            if r.closed: continue
            adj.setdefault(r.a,[]).append((r.b,r.id)); adj.setdefault(r.b,[]).append((r.a,r.id))
        pq=[(0.0,start,[])]; seen=set()
        while pq:
            dist,node,path=heapq.heappop(pq)
            if node==destination:
                return {'road_ids':path,'roads':[self.roads[x].name for x in path],
                        'distance_km':round(sum(self.roads[x].length_m for x in path)/1000,2),
                        'travel_min':round(sum(self._travel_min(self.roads[x]) for x in path),1)}
            if node in seen: continue
            seen.add(node)
            for nxt,rid in adj.get(node,[]): heapq.heappush(pq,(dist+self.roads[rid].length_m,nxt,path+[rid]))
        return {'road_ids':[],'roads':[],'distance_km':None,'travel_min':None}

    def route(self,start='n3',destination='n5'):
        adj={}
        for r in self.roads.values():
            if r.closed: continue
            adj.setdefault(r.a,[]).append((r.b,r.id)); adj.setdefault(r.b,[]).append((r.a,r.id))
        pq=[(0.0,start,[],0.0)]; best={}
        while pq:
            cost,node,path,travel=heapq.heappop(pq)
            if node==destination:
                profile=self._profile(path); baseline=self.shortest_route(start,destination)
                bp=self._profile(baseline['road_ids']) if baseline['road_ids'] else []
                safe=max((x['risk'] for x in profile),key=lambda z:RISK_ORDER[z],default='GREEN')
                br=max((x['risk'] for x in bp),key=lambda z:RISK_ORDER[z],default='GREEN')
                return {'road_ids':path,'roads':[self.roads[x].name for x in path],'cost':round(cost,2),
                        'distance_km':round(sum(self.roads[x].length_m for x in path)/1000,2),'travel_min':round(travel,1),
                        'risk':safe,'arrival_profile':profile,'baseline_route':baseline,'baseline_arrival_profile':bp,
                        'baseline_risk':br,'route_reason':'Road risk is evaluated from predicted depth at vehicle arrival time.'}
            if node in best and best[node] <= cost: continue
            best[node]=cost
            for nxt,rid in adj.get(node,[]):
                r=self.roads[rid]; arrival=max(DT_MIN,ceil((travel+self._travel_min(r))/DT_MIN)*DT_MIN)
                depth=self.future_depth(rid,arrival)
                if depth>=CRITICAL_DEPTH_CM: continue
                severity=RISK_ORDER[self.risk(depth,r.criticality)]
                penalty=1+r.criticality*1.2+(depth/8)**2+severity*8+(15 if depth>=FLOOD_THRESHOLD_CM else 0)
                heapq.heappush(pq,(cost+r.length_m/100*penalty,nxt,path+[rid],travel+self._travel_min(r)))
        return {'road_ids':[],'roads':[],'cost':None,'distance_km':None,'travel_min':None,'risk':'NO_SAFE_ROUTE',
                'arrival_profile':[],'baseline_route':self.shortest_route(start,destination),'baseline_arrival_profile':[],
                'baseline_risk':'NO_SAFE_ROUTE'}

    def observe(self,water_level_cm,road_id=None):
        predicted=self.roads[road_id].depth_cm if road_id else max((r.depth_cm for r in self.roads.values()),default=0)
        residual=water_level_cm-predicted
        adjustment=max(-.04,min(.04,residual/150))
        targets=[self.nodes[self.roads[road_id].b]] if road_id else list(self.nodes.values())
        for n in targets:
            n.inlet_efficiency=max(.55,min(.98,n.inlet_efficiency-adjustment*.5))
            n.roughness=max(.02,min(.08,n.roughness+adjustment*.02))
        self.observed_level=water_level_cm; self.calibration_count+=1
        self.observations.append({'minute':self.minute,'road_id':road_id,'observed_cm':water_level_cm,'predicted_cm':predicted,'residual_cm':round(residual,2)})
        return {'accepted':True,'residual_cm':round(residual,1),'method':'parameter_update_only; no direct depth override',
                'updated_inlet_efficiency':round(sum(n.inlet_efficiency for n in targets)/len(targets),3),
                'updated_roughness':round(sum(n.roughness for n in targets)/len(targets),4),'state':self.state()}

    def _replay_observations(self, observations, inlet_scale=1.0, roughness_scale=1.0):
        sim=FloodTwin()
        sim.reset(self.rainfall_mmhr, max(self.horizon, max((int(o['minute']) for o in observations), default=0)))
        for n in sim.nodes.values():
            n.inlet_efficiency=max(.55,min(.98,n.inlet_efficiency*inlet_scale))
            n.roughness=max(.02,min(.08,n.roughness*roughness_scale))
        by_minute=sorted(observations, key=lambda o:int(o['minute']))
        predictions=[]
        for obs in by_minute:
            target=int(obs['minute'])
            while sim.minute < target:
                sim.step(min(DT_MIN, target-sim.minute))
            rid=obs.get('road_id')
            pred=sim.roads[rid].depth_cm if rid else max((r.depth_cm for r in sim.roads.values()),default=0.0)
            predictions.append(pred)
        return predictions

    def calibrate(self, holdout_fraction=0.25):
        if len(self.observations) < 3:
            return {'status':'INSUFFICIENT_OBSERVATIONS','required':3,'n':len(self.observations)}
        obs=sorted(self.observations, key=lambda o:int(o['minute']))
        split=max(2,int(len(obs)*(1-holdout_fraction)))
        train=obs[:split]; test=obs[split:]
        base_eff=sum(n.inlet_efficiency for n in self.nodes.values())/len(self.nodes)
        base_rough=sum(n.roughness for n in self.nodes.values())/len(self.nodes)
        # Small, bounded grid search keeps calibration transparent and avoids overfitting.
        candidates=[0.90,0.95,1.00,1.05,1.10]
        best=None
        for es in candidates:
            for rs in candidates:
                preds=self._replay_observations(train,es,rs)
                errs=[p-o['observed_cm'] for p,o in zip(preds,train)]
                rmse=sqrt(sum(e*e for e in errs)/len(errs))
                penalty=((es-1)**2+(rs-1)**2)*0.25
                score=rmse+penalty
                if best is None or score<best['score']:
                    best={'score':score,'inlet_scale':es,'roughness_scale':rs,'train_rmse_cm':rmse}
        for n in self.nodes.values():
            n.inlet_efficiency=max(.55,min(.98,n.inlet_efficiency*best['inlet_scale']))
            n.roughness=max(.02,min(.08,n.roughness*best['roughness_scale']))
        self.calibration_count += 1
        test_metrics=None
        if test:
            preds=self._replay_observations(test,best['inlet_scale'],best['roughness_scale'])
            errs=[p-o['observed_cm'] for p,o in zip(preds,test)]
            test_metrics={'n':len(test),'mae_cm':round(sum(abs(e) for e in errs)/len(errs),3),
                          'rmse_cm':round(sqrt(sum(e*e for e in errs)/len(errs)),3),
                          'bias_cm':round(sum(errs)/len(errs),3)}
        return {'status':'CALIBRATED','n':len(obs),'train_n':len(train),'holdout_n':len(test),
                'method':'bounded grid search over inlet-efficiency and roughness scales; chronological holdout',
                'inlet_scale':best['inlet_scale'],'roughness_scale':best['roughness_scale'],
                'train_rmse_cm':round(best['train_rmse_cm'],3),'holdout':test_metrics,
                'mean_inlet_efficiency':round(sum(n.inlet_efficiency for n in self.nodes.values())/len(self.nodes),4),
                'mean_roughness':round(sum(n.roughness for n in self.nodes.values())/len(self.nodes),5)}

    def validation_summary(self):
        if not self.observations:
            return {'status':'NO_OBSERVATIONS','n':0,'metrics':None}
        errors=[o['predicted_cm']-o['observed_cm'] for o in self.observations]
        abs_err=[abs(e) for e in errors]
        rmse=(sum(e*e for e in errors)/len(errors))**0.5
        mae=sum(abs_err)/len(abs_err)
        bias=sum(errors)/len(errors)
        return {'status':'OBSERVATIONS_AVAILABLE','n':len(errors),'metrics':{'mae_cm':round(mae,3),'rmse_cm':round(rmse,3),'bias_cm':round(bias,3)}}

    def set_closure(self,rid,closed):
        if rid not in self.roads: raise KeyError(rid)
        self.roads[rid].closed=closed
