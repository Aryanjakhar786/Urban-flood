from __future__ import annotations
import os, time
from typing import Any
import httpx

class RainfallProvider:
    """Safe provider boundary. Live values are never assumed to be mm/hr without
    explicit unit/accumulation metadata supplied by the deployment configuration."""
    def __init__(self):
        self.mode=os.getenv('RAINFALL_MODE','demo').lower()
        self.imd_url=os.getenv('IMD_RAINFALL_URL','https://mausam.imd.gov.in/api/districtwise_rainfall_api.php')
        self.city_url=os.getenv('IMD_CITY_WEATHER_URL','https://mausam.imd.gov.in/api/current_wx_api.php')
        self.station_id=os.getenv('IMD_STATION_ID','')
        self.timeout=float(os.getenv('RAIN_TIMEOUT_SECONDS','10'))
        self._cache=None; self._cache_ts=0.0
        self.cache_seconds=int(os.getenv('RAIN_CACHE_SECONDS','300'))

    def _extract_candidate(self,obj):
        keys={'rainfall','rain','rainfall_mm','rain_mm','actual_rainfall','current_rainfall'}
        if isinstance(obj,dict):
            for k,v in obj.items():
                if str(k).lower() in keys:
                    try:return float(v),str(k)
                    except (TypeError,ValueError): pass
            for v in obj.values():
                x=self._extract_candidate(v)
                if x:return x
        elif isinstance(obj,list):
            for v in obj:
                x=self._extract_candidate(v)
                if x:return x
        return None

    def _normalize(self,value, source_key):
        unit=os.getenv('IMD_RAINFALL_UNIT','').lower().strip()
        accumulation=float(os.getenv('IMD_RAINFALL_ACCUMULATION_MINUTES','0'))
        if unit in ('mm/hr','mmh','mmhr'):
            return value, {'input_unit':'mm/hr','accumulation_minutes':None}
        if unit=='mm':
            if accumulation <= 0:
                raise ValueError('IMD_RAINFALL_ACCUMULATION_MINUTES is required when rainfall is accumulated in mm')
            return value*(60.0/accumulation), {'input_unit':'mm','accumulation_minutes':accumulation}
        raise ValueError('Rainfall units are not configured; set IMD_RAINFALL_UNIT to mm/hr or mm')

    async def live(self)->dict[str,Any]:
        if self.mode!='imd':
            return {'mode':'DEMO','source':'simulation','rainfall_mmhr':None,'stale':False,'quality':'SIMULATED'}
        now=time.time()
        if self._cache and now-self._cache_ts < self.cache_seconds:
            return {**self._cache,'cached':True}
        urls=[]
        if self.station_id: urls.append((f'{self.city_url}?id={self.station_id}','IMD Current Weather API'))
        urls.append((self.imd_url,'IMD Districtwise Rainfall API'))
        last_error=None
        async with httpx.AsyncClient(timeout=self.timeout,follow_redirects=True) as client:
            for url,label in urls:
                try:
                    resp=await client.get(url,headers={'User-Agent':'UrbanFloodDigitalTwin/8.0'})
                    resp.raise_for_status(); data=resp.json()
                    candidate=self._extract_candidate(data)
                    if not candidate: raise ValueError('Provider response has no recognizable rainfall field')
                    value,key=candidate
                    normalized,meta=self._normalize(value,key)
                    result={'mode':'LIVE','source':label,'source_url':url,'rainfall_mmhr':normalized,
                            'raw_value':value,'raw_field':key,'unit_metadata':meta,
                            'observed_at':time.time(),'retrieved_at':time.time(),'stale':False,
                            'cached':False,'quality':'UNVERIFIED_PROVIDER_FIELD'}
                    self._cache=result; self._cache_ts=now; return result
                except Exception as e: last_error=str(e)
        if self._cache: return {**self._cache,'stale':True,'cached':True,'error':last_error}
        return {'mode':'LIVE','source':'IMD','rainfall_mmhr':None,'stale':True,'quality':'UNAVAILABLE','error':last_error}
