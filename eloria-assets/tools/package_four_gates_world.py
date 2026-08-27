#!/usr/bin/env python3
"""Build the playable portable-world Four Gates package from the authored GLB."""
import argparse, json, math, struct
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; SOURCE_DIR=ROOT/"maps/four-gates-city"; SOURCE=SOURCE_DIR/"four-gates-city.glb"; METADATA=SOURCE_DIR/"four-gates-city.json"
SOURCE_OUTPUT=ROOT/"nymara-packs/nymara-client-assets/runtime/maps/four_gates"
OUTPUT=SOURCE_OUTPUT; SIZE=1536; UNITS_PER_METER=2.15; ORIGIN=(384.0,384.0,0.0)
BUILDING_MARKERS=[(r*math.sin(math.radians(a)),r*math.cos(math.radians(a))) for r in (125,195,265) for a in range(15,360,30)]

def correct_winding_indices(raw):
 data=bytearray(raw);offset=12;document=None;binary_offset=None
 while offset<len(data):
  length,kind=struct.unpack_from('<II',data,offset);offset+=8
  if kind==0x4E4F534A:document=json.loads(data[offset:offset+length])
  elif kind==0x004E4942:binary_offset=offset
  offset+=length
 if document is None or binary_offset is None:raise RuntimeError('source GLB lacks JSON or BIN chunk')
 formats={5121:'B',5123:'H',5125:'I'};decisions={}
 def accessor(index):
  item=document['accessors'][index];view=document['bufferViews'][item['bufferView']]
  component=item['componentType'];width={5121:1,5123:2,5125:4,5126:4}.get(component)
  components={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4}.get(item['type'])
  if width is None or components is None:raise RuntimeError('unsupported Four Gates accessor')
  stride=view.get('byteStride',width*components)
  start=binary_offset+view.get('byteOffset',0)+item.get('byteOffset',0)
  return item,start,stride,width,components
 def vec3(index,element):
  item,start,stride,_,components=accessor(index)
  if item['componentType']!=5126 or components!=3:raise RuntimeError('Four Gates vectors must be float VEC3')
  return struct.unpack_from('<3f',data,start+element*stride)
 def index_value(index,element):
  item,start,stride,width,components=accessor(index);fmt=formats.get(item['componentType'])
  if fmt is None or components!=1:raise RuntimeError('unsupported Four Gates triangle indices')
  return struct.unpack_from('<'+fmt,data,start+element*stride)[0]
 for mesh in document.get('meshes',[]):
  for primitive in mesh.get('primitives',[]):
   if primitive.get('mode',4)!=4 or 'indices' not in primitive:continue
   accessor_index=primitive['indices'];indices=document['accessors'][accessor_index];count=indices['count']
   if count%3:raise RuntimeError('Four Gates triangle index count is not divisible by three')
   normal_index=primitive.get('attributes',{}).get('NORMAL');position_index=primitive.get('attributes',{}).get('POSITION')
   reverse=False
   if normal_index is not None and position_index is not None:
    score=0
    # The source contains both CCW and CW helper meshes.  Compare geometric
    # faces with authored normals instead of reversing the complete package.
    step=max(3,(count//(512*3))*3)
    for triangle in range(0,count,step):
     if triangle+2>=count:break
     ia,ib,ic=(index_value(accessor_index,triangle+i) for i in range(3))
     a,b,c=(vec3(position_index,index) for index in (ia,ib,ic));normal=vec3(normal_index,ia)
     ux,uy,uz=(b[i]-a[i] for i in range(3));vx,vy,vz=(c[i]-a[i] for i in range(3))
     dot=(uy*vz-uz*vy)*normal[0]+(uz*vx-ux*vz)*normal[1]+(ux*vy-uy*vx)*normal[2]
     if dot>1e-8:score+=1
     elif dot< -1e-8:score-=1
    reverse=score<0
   previous=decisions.get(accessor_index)
   if previous is not None and previous!=reverse:raise RuntimeError('shared Four Gates indices require conflicting winding')
   decisions[accessor_index]=reverse
   if not reverse:continue
   item,start,stride,width,_=accessor(accessor_index)
   for triangle in range(0,count,3):
    second=start+(triangle+1)*stride;third=start+(triangle+2)*stride
    data[second:second+width],data[third:third+width]=data[third:third+width],data[second:second+width]
 return bytes(data)

def source_xz(cx,cy):
 world_x=(cx+.5)*.5;world_y=(cy+.5)*.5;return ((world_x-ORIGIN[0])*UNITS_PER_METER,(ORIGIN[1]-world_y)*UNITS_PER_METER)
def terrain_height(r):
 if r<=175:return 36.
 if r<=285:return 36-(r-175)/110*5
 if r<=365:return 31-(r-285)/80*7
 return 24.
def on_causeway(x,z):return (abs(x)<=22 and 340<=abs(z)<=735) or (abs(z)<=22 and 340<=abs(x)<=735)
def blocked(x,z,obstacles):
 return any(abs(x-o['center'][0])<max(.75,o['halfExtents'][0]-.6) and abs(z-o['center'][2])<max(.75,o['halfExtents'][2]-.6) for o in obstacles)
def walkable_height(x,z,obstacles):
 r=math.hypot(x,z)
 if r<=350:
  if r<20 or blocked(x,z,obstacles):return None
  angle=(math.degrees(math.atan2(x,z))-25)%45
  if r>300 and min(angle,45-angle)<1.25:return None
  return terrain_height(r)
 if on_causeway(x,z):return 31.
 return None
def encode_height(y):
 if y is None:return 0
 return max(1,min(255,int(round((y/UNITS_PER_METER+2.2)/.2))))

def build_portable_glb():
 raw=correct_winding_indices(SOURCE.read_bytes());jlen=struct.unpack_from('<I',raw,12)[0];doc=json.loads(raw[20:20+jlen]);bo=20+jlen;blen=struct.unpack_from('<I',raw,bo)[0];binary=bytearray(raw[bo+8:bo+8+blen]);textures=OUTPUT/'textures';textures.mkdir(exist_ok=True)
 for index,image in enumerate(doc.get('images',[])):
  view=doc['bufferViews'][image['bufferView']];start=view.get('byteOffset',0);data=bytes(binary[start:start+view['byteLength']]);name=''.join(c if c.isalnum() or c in '-_' else '-' for c in image.get('name',f'image-{index}'))+'.png';(textures/name).write_bytes(data);image.pop('bufferView',None);image.pop('mimeType',None);image['uri']=f'textures/{name}'
 def transformed_uv(accessor_index,transform):
  accessor=doc['accessors'][accessor_index];view=doc['bufferViews'][accessor['bufferView']];stride=view.get('byteStride',8);start=view.get('byteOffset',0)+accessor.get('byteOffset',0);scale=transform.get('scale',[1,1]);offset=transform.get('offset',[0,0]);values=[]
  for i in range(accessor['count']):
   u,v=struct.unpack_from('<2f',binary,start+i*stride);values.extend((u*scale[0]+offset[0],v*scale[1]+offset[1]))
  while len(binary)%4:binary.append(0)
  packed=struct.pack(f'<{len(values)}f',*values);view_index=len(doc['bufferViews']);doc['bufferViews'].append({'buffer':0,'byteOffset':len(binary),'byteLength':len(packed),'target':34962});binary.extend(packed);pairs=list(zip(values[0::2],values[1::2]));new=dict(accessor);new.update({'bufferView':view_index,'byteOffset':0,'min':[min(x for x,_ in pairs),min(y for _,y in pairs)],'max':[max(x for x,_ in pairs),max(y for _,y in pairs)]});doc['accessors'].append(new);return len(doc['accessors'])-1
 for mesh in doc.get('meshes',[]):
  for primitive in mesh.get('primitives',[]):
   material=doc['materials'][primitive.get('material',0)];info=material.get('pbrMetallicRoughness',{}).get('baseColorTexture',{});transform=info.get('extensions',{}).get('KHR_texture_transform')
   if transform and 'TEXCOORD_0' in primitive.get('attributes',{}):primitive['attributes']['TEXCOORD_0']=transformed_uv(primitive['attributes']['TEXCOORD_0'],transform)
 for material in doc.get('materials',[]):
  stack=[material]
  while stack:
   value=stack.pop()
   if isinstance(value,dict):
    extensions=value.get('extensions')
    if isinstance(extensions,dict):
     extensions.pop('KHR_texture_transform',None)
     if not extensions:value.pop('extensions')
    stack.extend(value.values())
   elif isinstance(value,list):stack.extend(value)
 used=[x for x in doc.get('extensionsUsed',[]) if x!='KHR_texture_transform']
 if used:doc['extensionsUsed']=used
 else:doc.pop('extensionsUsed',None)
 while len(binary)%4:binary.append(0)
 doc['buffers'][0]['byteLength']=len(binary);jb=json.dumps(doc,separators=(',',':')).encode();jb+=b' '*((-len(jb))%4);(OUTPUT/'world.glb').write_bytes(struct.pack('<4sII',b'glTF',2,12+8+len(jb)+8+len(binary))+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(binary),b'BIN\0')+binary)

def dds_mipped(path,width,height,pixel,levels=4):
 header=[124,0x0002100F,height,width,width*4,0,levels]+[0]*11+[32,0x41,0,32,0x00FF0000,0x0000FF00,0x000000FF,0xFF000000]+[0x401008,0,0,0,0];payload=bytearray()
 for level in range(levels):
  w,h,scale=max(1,width>>level),max(1,height>>level),1<<level
  for y in range(h):
   for x in range(w):
    r,g,b,a=pixel(min(width-1,x*scale),min(height-1,y*scale));payload.extend((b,g,r,a))
 path.write_bytes(b'DDS '+struct.pack('<31I',*header)+payload)
def cartography_pixel(px,py):
 x=(px/511-.5)*1500;z=(py/511-.5)*1570-35;r=math.hypot(x,z);color=(43,113,139,255)
 if r<=454:color=(82,91,82,255) if r>365 else (112,139,91,255)
 if r<=350 and (abs(x)<15 or abs(z)<15):color=(211,184,118,255)
 elif 95<r<330 and min(abs((math.degrees(math.atan2(x,z))-a+180)%360-180) for a in range(0,360,45))<2:color=(177,160,121,255)
 if 342<=r<=358:color=(188,191,184,255)
 if on_causeway(x,z):color=(174,179,174,255)
 if 105<r<315:
  angle=(math.degrees(math.atan2(x,z))+360)%360
  if 180<angle<285:color=tuple(int((c+d)/2) for c,d in zip(color[:3],(151,135,107)))+(255,)
  elif 285<=angle or angle<30:color=tuple(int((c+d)/2) for c,d in zip(color[:3],(122,151,102)))+(255,)
 for bx,bz in BUILDING_MARKERS:
  if abs(x-bx)<10 and abs(z-bz)<7:color=(203,198,181,255);break
 for a in range(25,360,45):
  wx,wz=405*math.sin(math.radians(a)),405*math.cos(math.radians(a))
  if (x-wx)**2+(z-wz)**2<13**2:color=(87,190,217,255);break
 if 285<r<342 and int(abs(math.sin(x*.071)+math.cos(z*.083))*19)%11==0:color=(48,91,61,255)
 if 336<r<365 and (abs(x)<28 or abs(z)<28):color=(174,128,62,255)
 if r<78:color=(203,191,149,255)
 if r<22:color=(62,187,219,255)
 return color

def gameplay_manifest():
 harvest=[('resonant-crystal-east','resonant_crystal',(238.,33.,120.)),('stormglass-west','stormglass_shard',(-242.,32.,116.)),('mirror-reed-south','mirror_reed',(-82.,31.,258.)),('sunmane-seed-north','sunmane_seed',(92.,31.,-252.))]
 npcs=[('toran-civic-official',307,'official',(-28.,32.,42.),200.),('nima-vey-merchant',309,'merchant',(-142.,31.,-92.),45.),('south-gate-guard',301,'guard',(18.,31.,325.),180.),('north-gate-guard',308,'guard',(-18.,31.,-325.),0.),('civic-scholar',304,'scholar',(-112.,32.,70.),110.),('ferry-lantern-bearer',303,'ferryman',(15.,31.,405.),180.)]
 spawns=[('garden-glasswings','glasswing_moth',(225.,31.,-185.),22.,4),('shore-reefbacks','reefback_crab',(-270.,24.,185.),24.,3),('outer-lumen-stags','lumen_stag',(248.,27.,210.),30.,2)]
 return {'harvestables':[{'id':i,'resource':r,'position':list(p),'interaction_radius':2.5,'respawn_seconds':90} for i,r,p in harvest],
  'npc_markers':[{'id':i,'actor_type':a,'role':r,'position':list(p),'rotation_degrees':d} for i,a,r,p,d in npcs],
  'spawn_markers':[{'id':i,'creature':c,'position':list(p),'radius':r,'maximum_alive':n} for i,c,p,r,n in spawns],
  'regions':[{'id':'central-plaza','position':[0.,32.,0.],'radius':82.,'tags':['safe','civic']},{'id':'civic-quarter','position':[-145.,31.,-45.],'radius':125.,'tags':['safe','market']},{'id':'residential-quarter','position':[190.,31.,20.],'radius':145.,'tags':['safe','residential']},{'id':'agricultural-quarter','position':[0.,30.,245.],'radius':125.,'tags':['safe','harvest']},{'id':'sanctuary-approach','position':[0.,42.,-505.],'radius':165.,'tags':['ceremonial','portal']}]}

def main():
 global OUTPUT
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument("output",nargs="?",help="runtime data root; omit to refresh the checked-in handoff pack")
 args=parser.parse_args()
 if args.output: OUTPUT=Path(args.output)/"maps/four_gates"
 OUTPUT.mkdir(parents=True,exist_ok=True);meta=json.loads(METADATA.read_text())
 if meta.get('assetVersion')!='0.6.1':raise RuntimeError('Four Gates portable package requires authored asset version 0.6.1')
 build_portable_glb();obstacles=[o for o in meta['navigation']['navmesh'].get('obstacles',[]) if 'Window' not in o['node']];gameplay=gameplay_manifest();water=[]
 for i in range(8):
  a=math.radians(25+i*45);water.append({'id':f'waterfall-{i:02}','channel_node':f'Water_Channel_{i:02}','pool_node':f'Waterfall_Pool_{i:02}','foam_node':f'Waterfall_Foam_{i:02}','mist_node':f'FX_Waterfall_Mist_{i:02}','position':[405*math.sin(a),0.,405*math.cos(a)],'uv_scroll':[0.,-.32],'foam_scroll':[.08,-.18],'mist_particle':'waterfall_mist','fallback':'static-geometry'})
 manifest={'format':'eloria-world','version':1,'id':'four_gates','display_name':'Four Gates','scene':'world.glb','collision':'collision.bin','collision_width':SIZE,'collision_height':SIZE,'minimap':'four_gates.dds',
  'coordinates':{'units_per_meter':UNITS_PER_METER,'up_axis':'Y','forward_axis':'-Z','origin':list(ORIGIN)},'bounds':{'minimum':[-750.,-40.,-820.],'maximum':[750.,195.,750.]},
  'environment':{'ambient_color':[.72,.76,.78],'ambient_intensity':1.15,'sun_direction':[-.4,-.8,-.3],'sun_color':[1.,.95,.85],'sun_intensity':1.,'fog_enabled':False},
  # Use the authored central-plaza marker for the default test/login spawn.
  # The former south marker maps to server [768,480] and places the camera
  # among the dense inner-gate roofs, obscuring almost the entire city.
  'player_starts':[{'id':'default','position':[0.,32.,55.],'rotation_degrees':180.}],
  'portals':[{'id':'south','position':[0.,31.,722.2],'target_hook':'nymara.south'},{'id':'east','position':[722.2,31.,0.],'target_hook':'nymara.east'},{'id':'west','position':[-722.2,31.,0.],'target_hook':'nymara.west'},{'id':'north','position':[0.,31.,-722.2],'target_hook':'nymara.sanctuary'}],
  'navigation':{'format':meta['navigation']['navmesh']['format'],'polygons':meta['navigation']['navmesh']['polygons'],'off_mesh_links':meta['navigation']['navmesh'].get('offMeshLinks',[]),'obstacle_count':len(obstacles)},
  'effects':{'waterfalls':water,'materials':{'water':{'uv_scroll':[.02,-.04],'blend':'alpha'},'waterfall':{'uv_scroll':[0.,-.32],'blend':'alpha'},'landmark-energy':{'pulse_hz':.75,'blend':'additive'}}},**gameplay}
 (OUTPUT/'world.json').write_text(json.dumps(manifest,indent=2)+'\n');payload=bytearray(SIZE*SIZE)
 for cy in range(SIZE):
  row=cy*SIZE
  for cx in range(SIZE):
   x,z=source_xz(cx,cy);payload[row+cx]=encode_height(walkable_height(x,z,obstacles))
 (OUTPUT/'collision.bin').write_bytes(struct.pack('<4sHHII',b'EWCG',1,0,SIZE,SIZE)+payload);dds_mipped(OUTPUT/'four_gates.dds',512,512,cartography_pixel)
 count=sum(bool(v) for v in payload);print(json.dumps({'walkableCells':count,'blockedCells':len(payload)-count,'collisionCoveragePercent':round(count/len(payload)*100,2),'npcs':len(gameplay['npc_markers']),'spawns':len(gameplay['spawn_markers']),'harvestables':len(gameplay['harvestables']),'waterfalls':len(water)},indent=2))
if __name__=='__main__':main()
