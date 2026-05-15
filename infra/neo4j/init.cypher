CREATE CONSTRAINT service_identity_id IF NOT EXISTS
FOR (s:ServiceIdentity)
REQUIRE s.id IS UNIQUE;

CREATE CONSTRAINT incident_id IF NOT EXISTS
FOR (i:Incident)
REQUIRE i.id IS UNIQUE;

CREATE CONSTRAINT incident_family_id IF NOT EXISTS
FOR (f:IncidentFamily)
REQUIRE f.id IS UNIQUE;

CREATE INDEX service_alias_name IF NOT EXISTS
FOR (a:ServiceAlias)
ON (a.name);
