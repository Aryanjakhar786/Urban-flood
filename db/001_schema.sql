CREATE EXTENSION IF NOT EXISTS postgis;
CREATE TABLE IF NOT EXISTS roads (id text PRIMARY KEY, name text NOT NULL, criticality double precision, closed boolean DEFAULT false, geom geometry(LineString,4326));
CREATE TABLE IF NOT EXISTS drain_nodes (id text PRIMARY KEY, name text NOT NULL, capacity_m3s double precision, inlet_efficiency double precision, roughness double precision, geom geometry(Point,4326));
CREATE TABLE IF NOT EXISTS drain_links (id text PRIMARY KEY, a text NOT NULL, b text NOT NULL, capacity_m3s double precision, length_m double precision, geom geometry(LineString,4326));
CREATE TABLE IF NOT EXISTS rainfall_observations (id bigserial PRIMARY KEY, observed_at timestamptz NOT NULL DEFAULT now(), source text NOT NULL, rainfall_mmhr double precision, raw jsonb);
CREATE TABLE IF NOT EXISTS water_observations (id bigserial PRIMARY KEY, observed_at timestamptz NOT NULL DEFAULT now(), road_id text, water_level_cm double precision, source text);
CREATE INDEX IF NOT EXISTS roads_geom_idx ON roads USING gist(geom);
CREATE INDEX IF NOT EXISTS drain_nodes_geom_idx ON drain_nodes USING gist(geom);
CREATE INDEX IF NOT EXISTS drain_links_geom_idx ON drain_links USING gist(geom);
