"""Build the bundled, attributed OpenStreetMap vector extract from an OSM XML file.
Usage: python tools/build_offline_map.py /path/to/baku.osm
Source: https://api.openstreetmap.org/api/0.6/map?bbox=49.825,40.359,49.867,40.385
No raster tiles are downloaded or bundled.
"""
import json,sys,xml.etree.ElementTree as ET
from pathlib import Path
root=ET.parse(sys.argv[1]).getroot()
nodes={n.attrib['id']:[round(float(n.attrib['lon']),6),round(float(n.attrib['lat']),6)] for n in root.findall('node')}
features=[];coasts=[]
for way in root.findall('way'):
 tags={t.attrib['k']:t.attrib['v'] for t in way.findall('tag')}
 points=[nodes[n.attrib['ref']] for n in way.findall('nd') if n.attrib['ref'] in nodes]
 if len(points)<2:continue
 if tags.get('natural')=='coastline':coasts.append(points);continue
 kind='road' if tags.get('highway') else 'building' if tags.get('building') else 'park' if tags.get('leisure') in ('park','garden') or tags.get('landuse') in ('grass','forest') else 'water' if tags.get('natural')=='water' else None
 if not kind:continue
 closed=points[0]==points[-1] and kind!='road'
 features.append({'type':'Feature','properties':{'kind':kind,**({'highway':tags['highway']} if 'highway'in tags else {}),**({'name':tags['name']} if tags.get('name') else {})},'geometry':{'type':'Polygon' if closed else 'LineString','coordinates':[points] if closed else points}})
# Join the actual coastline; close the water polygon beyond the extract boundary.
while len(coasts)>1:
 merged=False
 for i in range(len(coasts)):
  for j in range(len(coasts)):
   if i!=j and coasts[i][-1]==coasts[j][0]:
    chain=coasts[i]+coasts[j][1:];coasts=[v for k,v in enumerate(coasts) if k not in (i,j)]+[chain];merged=True;break
  if merged:break
 if not merged:break
for chain in coasts:
 if len(chain)>100:
  polygon=chain+[[50.02,40.28],[49.80,40.28],chain[0]]
  features.insert(0,{'type':'Feature','properties':{'kind':'water','name':'Xəzər dənizi'},'geometry':{'type':'Polygon','coordinates':[polygon]}})
features.sort(key=lambda f:{'water':0,'park':1,'building':2,'road':3}[f['properties']['kind']])
data={'type':'FeatureCollection','name':'Baku central OpenStreetMap extract','attribution':'© OpenStreetMap contributors','license':'ODbL 1.0','source':'https://api.openstreetmap.org/api/0.6/map?bbox=49.825,40.359,49.867,40.385','bounds':[49.825,40.359,49.867,40.385],'features':features}
out=Path(__file__).resolve().parents[1]/'frontend/baku.geojson';out.write_text(json.dumps(data,ensure_ascii=False,separators=(',',':')))
print(len(features),'real geographic features;',out.stat().st_size,'bytes')
