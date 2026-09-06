# Municipal pilot deployment checklist

## Before go-live
- Obtain municipality-approved road/drain GIS and DEM.
- Confirm IMD data access/whitelisting and attribution requirements.
- Configure `RAINFALL_MODE=imd` and the approved endpoint/ID.
- Replace demo credentials and set secrets outside source control.
- Put NGINX/load balancer and TLS in front of the API.
- Restrict CORS to the municipal dashboard origin.
- Enable backups for PostGIS and audit logs.
- Add operator authentication/role-based access before production use.
- Calibrate against verified water-level observations.
- Validate outputs against an approved hydraulic model before life-safety use.
- Define incident escalation and manual override procedures.

## Data flow
IMD / approved rainfall feed -> adapter -> validation/cache -> digital twin -> PostGIS/API -> municipal dashboard
Municipal GIS/DEM -> ETL -> PostGIS -> simulation
Water sensors / verified reports -> observation API -> calibration -> next forecast cycle
