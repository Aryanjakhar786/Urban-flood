from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from pydantic import BaseModel, Field
from .simulation import FloodTwin
from .gis import validate_geojson
from .rainfall import RainfallProvider
from .provenance import CATALOG, source_status
from .swmm import build_swmm_input

app=FastAPI(title='Street-Level Urban Flood Digital Twin',version='10.0.0',description='SIH PS 26085 scientific demonstrator')
app.add_middleware(CORSMiddleware,allow_origins=['*'],allow_methods=['*'],allow_headers=['*'])
twin=FloodTwin(); rainfall_provider=RainfallProvider(); FRONTEND=Path(__file__).resolve().parents[2]/'frontend'
class SimConfig(BaseModel): rainfall_mmhr:float=Field(70,ge=0,le=250); horizon:int=Field(180,ge=15,le=180)
class Observation(BaseModel): water_level_cm:float=Field(...,ge=0,le=200); road_id:str|None=None
class Closure(BaseModel): road_id:str; closed:bool=True
@app.get('/api/health')
def health(): return {'status':'ok','mode':rainfall_provider.mode.upper(),'version':'10.0.0'}
@app.get('/api/data-provenance')
def data_provenance(): return {'catalog':CATALOG,'current':source_status('IMD_CONFIGURED' if rainfall_provider.mode=='imd' else 'DEMO_SIMULATION')}
@app.get('/api/rainfall/live')
async def live_rainfall(): return await rainfall_provider.live()
@app.post('/api/rainfall/apply-live')
async def apply_live_rainfall():
    data=await rainfall_provider.live()
    if data.get('rainfall_mmhr') is None: raise HTTPException(503,'Live rainfall unavailable; use DEMO mode or configure authorized IMD access.')
    twin.rainfall_mmhr=float(data['rainfall_mmhr']); return {'applied':True,'rainfall':data,'state':twin.state()}
@app.get('/api/validation')
def validation(): return twin.validation_summary()
@app.post('/api/calibration')
def calibration(): return twin.calibrate()

@app.get('/api/model-card')
def model_card():
    return {
        'version':'10.0.0',
        'status':'SCIENTIFIC_MVP',
        'claims':{
            'hydrology':'Horton infiltration on pervious area',
            'surface':'Lumped road cells with explicit depression-storage parameter',
            'hydraulics':'Manning-based pipe capacity with transparent lumped routing',
            'swmm':'Complete reference-input export; execution requires an approved SWMM runtime',
            'validation':'Accuracy metrics are disabled until observed validation data are supplied'
        },
        'required_for_pilot':['authorized rainfall time series','DEM','road/drain/inlet GIS','observed water levels','calibration/validation dataset']
    }

@app.get('/api/swmm/starter',response_class=PlainTextResponse)
def swmm_starter(): return build_swmm_input(twin)
@app.get('/api/state')
def state(): return twin.state()
@app.get('/api/forecast')
def forecast(): return twin.forecast()
@app.post('/api/simulation/reset')
def reset(config:SimConfig): twin.reset(config.rainfall_mmhr,config.horizon); return twin.state()
@app.post('/api/simulation/step')
def step(minutes:int=5):
    try:return twin.step(minutes)
    except ValueError as e: raise HTTPException(400,str(e))
@app.get('/api/roads')
def roads(): return twin.state()['roads']
@app.get('/api/drains')
def drains(): return twin.state()['nodes']
@app.get('/api/bottlenecks')
def bottlenecks(): return sorted(twin.state()['nodes'],key=lambda x:x['flood_debt_m3'],reverse=True)
@app.post('/api/observation')
def observation(o:Observation):
    if o.road_id and o.road_id not in twin.roads: raise HTTPException(404,'Unknown road')
    return twin.observe(o.water_level_cm,o.road_id)
@app.post('/api/road-closure')
def closure(c:Closure):
    try:twin.set_closure(c.road_id,c.closed)
    except KeyError:raise HTTPException(404,'Unknown road')
    return twin.state()
@app.post('/api/gis/validate')
def validate_gis(payload:dict):
    try:return validate_geojson(payload)
    except ValueError as e:raise HTTPException(400,str(e))
@app.get('/api/route')
def route(start:str='n3',destination:str='n5'):
    if start not in twin.nodes or destination not in twin.nodes:raise HTTPException(400,'Unknown node')
    return twin.route(start,destination)
@app.get('/api/alerts')
def alerts():
    s=twin.state(); out=[]
    for r in s['roads']:
        if r['risk'] in ('ORANGE','RED'):
            out.append({'road':r['name'],'risk':r['risk'],'depth_cm':r['depth_cm'],'eta_min':r['eta_to_flood_min'],'confidence':r['confidence'],'action':'AVOID / DEPLOY BARRICADE' if r['risk']=='RED' else 'MONITOR / PREPARE CLOSURE'})
    return out
@app.get('/')
def index():return FileResponse(FRONTEND/'index.html')
@app.get('/{path:path}')
def static(path:str):
    p=FRONTEND/path; return FileResponse(p if p.exists() and p.is_file() else FRONTEND/'index.html')
