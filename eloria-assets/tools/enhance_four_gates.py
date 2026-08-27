import json, math, struct
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

PKG=Path('four-gates-city-package'); GLB=PKG/'four-gates-city.glb'; TEX=PKG/'textures'; TEX.mkdir(exist_ok=True)
raw=GLB.read_bytes(); jlen,jtype=struct.unpack_from('<I4s',raw,12); g=json.loads(raw[20:20+jlen]); boff=20+jlen; blen,btype=struct.unpack_from('<I4s',raw,boff); buf=bytearray(raw[boff+8:boff+8+blen])
# Normalize legacy authoring shorthand into strict glTF 2.0 properties.
for material in g.get('materials',[]):
 if isinstance(material.get('alphaMode'),list):
  modes=material['alphaMode'];material['alphaMode']=modes[0]
  if 'doubleSided' in modes:material['doubleSided']=True
for node in g.get('nodes',[]):
 if node.get('children')==[]:node.pop('children')
def align4():
 while len(buf)%4: buf.append(0)
def add_view(data,target=None):
 align4(); off=len(buf); buf.extend(data); d={'buffer':0,'byteOffset':off,'byteLength':len(data)}
 if target:d['target']=target
 g['bufferViews'].append(d); return len(g['bufferViews'])-1
def add_acc(arr,typ,component=5126,target=34962):
 a=np.asarray(arr,np.float32 if component==5126 else np.uint32); vi=add_view(a.tobytes(),target); d={'bufferView':vi,'componentType':component,'count':len(a),'type':typ,'min':a.min(0).tolist() if a.ndim>1 else [int(a.min())],'max':a.max(0).tolist() if a.ndim>1 else [int(a.max())]}; g['accessors'].append(d); return len(g['accessors'])-1
def read_pos(ai):
 a=g['accessors'][ai]; v=g['bufferViews'][a['bufferView']]; off=v.get('byteOffset',0)+a.get('byteOffset',0); return np.frombuffer(buf,dtype='<f4',count=a['count']*3,offset=off).reshape(-1,3).copy()

def normalize_atlas(image,grid):
 """Resize generated source atlases tile-by-tile so no color crosses a UV cell."""
 image=image.convert('RGB');w,h=image.size;tile=1024//grid;result=Image.new('RGB',(1024,1024))
 for row in range(grid):
  for col in range(grid):
   box=(round(col*w/grid),round(row*h/grid),round((col+1)*w/grid),round((row+1)*h/grid))
   sample=image.crop(box).resize((tile,tile),Image.Resampling.LANCZOS)
   result.paste(sample,(col*tile,row*tile))
 return result

def normal_atlas(image,grid,strength):
 """Derive normals per tile; atlas boundaries must never become false ridges."""
 source=np.asarray(image.convert('L'),np.float32)/255.;result=np.empty((1024,1024,3),np.uint8);tile=1024//grid
 for row in range(grid):
  for col in range(grid):
   y0,y1=row*tile,(row+1)*tile;x0,x1=col*tile,(col+1)*tile;gray=source[y0:y1,x0:x1]
   gy,gx=np.gradient(gray);normal=np.dstack((-gx*strength,-gy*strength,np.ones_like(gray)))
   normal/=np.maximum(np.linalg.norm(normal,axis=2,keepdims=True),1e-6)
   result[y0:y1,x0:x1]=((normal*.5+.5)*255).astype(np.uint8)
 return Image.fromarray(result)

# Add generated production atlas plus deterministic normal and ORM companions.
def load_or_generate_city_atlas(path):
 try:
  return normalize_atlas(Image.open(path),4)
 except (FileNotFoundError, OSError):
  image=Image.new('RGB',(1024,1024));draw=ImageDraw.Draw(image)
  palette=[(186,188,184),(76,85,96),(159,151,136),(91,82,78),
           (56,77,102),(157,116,48),(104,66,39),(210,202,177),
           (113,82,52),(104,139,84),(225,230,226),(40,105,139),
           (58,190,224),(113,190,222),(67,116,76),(47,131,158)]
  for tile,color in enumerate(palette):
   x=(tile%4)*256;y=(tile//4)*256;draw.rectangle((x,y,x+255,y+255),fill=color)
   for line in range(16,256,32):
    shade=tuple(max(0,c-18) for c in color)
    draw.line((x,y+line,x+255,y+line+((tile*7)%11)-5),fill=shade,width=3)
   if tile in (0,1,2,3,7,8):
    for row in range(0,256,48):
     offset=24 if (row//48)%2 else 0
     for col in range(-offset,256,64):draw.rectangle((x+col,y+row,x+col+60,y+row+43),outline=tuple(min(255,c+15) for c in color),width=2)
  image.save(path,optimize=True)
  return image
src=load_or_generate_city_atlas(TEX/'four-gates-material-atlas-source.png'); src.save(TEX/'four-gates-material-basecolor.png',optimize=True)
normal_atlas(src,4,1.45).save(TEX/'four-gates-material-normal.png',optimize=True)
orm=np.zeros((1024,1024,3),np.uint8); orm[:,:,0]=235; orm[:,:,1]=185
for c,r,val in [(1,1,195),(2,1,215)]:orm[r*256:(r+1)*256,c*256:(c+1)*256,2]=val
for c,r,val in [(1,1,80),(2,1,120),(0,3,45),(1,3,55),(2,3,70)]:orm[r*256:(r+1)*256,c*256:(c+1)*256,1]=val
Image.fromarray(orm).save(TEX/'four-gates-material-orm.png',optimize=True)

# UVs and normals for every reusable primitive.
for mesh in g['meshes']:
 for p in mesh['primitives']:
  v=read_pos(p['attributes']['POSITION']); n=v.copy(); n[:,1]*=.7; n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-6)
  u=(np.arctan2(v[:,2],v[:,0])/(2*np.pi)+.5)%1; vv=(v[:,1]-v[:,1].min())/max(float(np.ptp(v[:,1])),1e-6); uv=np.column_stack((u,vv)).astype(np.float32)
  t=np.cross(np.tile([0.,1.,0.],(len(n),1)),n);weak=np.linalg.norm(t,axis=1)<1e-5;t[weak]=[1,0,0];t/=np.maximum(np.linalg.norm(t,axis=1,keepdims=True),1e-6);t=np.column_stack((t,np.ones(len(t),np.float32)))
  p['attributes']['NORMAL']=add_acc(n,'VEC3'); p['attributes']['TEXCOORD_0']=add_acc(uv,'VEC2'); p['attributes']['TANGENT']=add_acc(t,'VEC4')

iv=[]
for fn in ['four-gates-material-basecolor.png','four-gates-material-normal.png','four-gates-material-orm.png']:iv.append(add_view((TEX/fn).read_bytes()))
g['images']=[{'name':'four-gates-basecolor','bufferView':iv[0],'mimeType':'image/png'},{'name':'four-gates-normal','bufferView':iv[1],'mimeType':'image/png'},{'name':'four-gates-orm','bufferView':iv[2],'mimeType':'image/png'}]
g['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]; g['textures']=[{'sampler':0,'source':i} for i in range(3)]; g['extensionsUsed']=['KHR_texture_transform']
tile={'stone':(0,0),'dark-stone':(1,0),'paving':(2,0),'rock':(3,0),'roof':(0,1),'bronze':(1,1),'wood':(3,1),'plaster':(0,2),'soil':(1,2),'grass':(2,2),'snow':(3,2),'water':(0,3),'blue-crystal':(1,3),'waterfall':(2,3),'vegetation':(3,3)}
for m in g['materials']:
 c,r=tile[m['name']]; tr={'offset':[c*.25,(3-r)*.25],'scale':[.25,.25]}; ti=lambda i:{'index':i,'extensions':{'KHR_texture_transform':tr}}
 p=m['pbrMetallicRoughness'];alpha=float(p.get('baseColorFactor',[1,1,1,1])[3]);p['baseColorFactor']=[.94,.94,.94,alpha]
 p['baseColorTexture']=ti(0); p['metallicRoughnessTexture']=ti(2); p['metallicFactor']=1; p['roughnessFactor']=1; m['normalTexture']=ti(1); m['occlusionTexture']=ti(2)

# Add maintainable detail nodes using existing shared meshes.
nodes=g['nodes']; byname={n['name']:i for i,n in enumerate(nodes)}; mesh_by_name={m['name']:i for i,m in enumerate(g['meshes'])}
mat_by_name={m['name']:i for i,m in enumerate(g['materials'])}
def ensure_mesh(name,prototype,material):
 if name in mesh_by_name:return
 src=g['meshes'][mesh_by_name[prototype]]; clone={'name':name,'primitives':[dict(src['primitives'][0])]}; clone['primitives'][0]['attributes']=dict(src['primitives'][0]['attributes']); clone['primitives'][0]['material']=mat_by_name[material]; g['meshes'].append(clone); mesh_by_name[name]=len(g['meshes'])-1
ensure_mesh('cube_wood','cube_stone','wood'); ensure_mesh('cube_roof','cube_stone','roof'); ensure_mesh('cylinder_bronze','cylinder_stone','bronze')

# A proper triangular-prism roof replaces the oversized umbrella-like cones on
# ordinary houses.  Vertices are split per face so Godot imports clean normals.
def add_gable_roof_mesh():
 positions=[];normals=[];uv=[];indices=[]
 def face(points,face_uv):
  start=len(positions);a=np.asarray(points,np.float32);normal=np.cross(a[1]-a[0],a[2]-a[0]);normal/=max(float(np.linalg.norm(normal)),1e-6)
  positions.extend(a.tolist());normals.extend([normal.tolist()]*len(points));uv.extend(face_uv)
  if len(points)==3:indices.extend([start,start+1,start+2])
  else:indices.extend([start,start+1,start+2,start,start+2,start+3])
 face([[-.5,-.5,-.5],[.5,-.5,-.5],[.5,-.5,.5],[-.5,-.5,.5]],[[0,0],[1,0],[1,1],[0,1]])
 face([[-.5,-.5,-.5],[-.5,-.5,.5],[0,.5,.5],[0,.5,-.5]],[[0,0],[1,0],[1,1],[0,1]])
 face([[0,.5,-.5],[0,.5,.5],[.5,-.5,.5],[.5,-.5,-.5]],[[0,1],[1,1],[1,0],[0,0]])
 face([[-.5,-.5,-.5],[0,.5,-.5],[.5,-.5,-.5]],[[0,0],[.5,1],[1,0]])
 face([[-.5,-.5,.5],[.5,-.5,.5],[0,.5,.5]],[[0,0],[1,0],[.5,1]])
 n=np.asarray(normals,np.float32);t=np.cross(np.tile([0.,1.,0.],(len(n),1)),n);weak=np.linalg.norm(t,axis=1)<1e-5;t[weak]=[1,0,0];t/=np.maximum(np.linalg.norm(t,axis=1,keepdims=True),1e-6);t=np.column_stack((t,np.ones(len(t),np.float32)))
 primitive={'attributes':{'POSITION':add_acc(positions,'VEC3'),'NORMAL':add_acc(n,'VEC3'),'TEXCOORD_0':add_acc(uv,'VEC2'),'TANGENT':add_acc(t,'VEC4')},'indices':add_acc(np.asarray(indices,np.uint32),'SCALAR',5125,34963),'material':mat_by_name['roof']}
 g['meshes'].append({'name':'gable_roof','primitives':[primitive]});mesh_by_name['gable_roof']=len(g['meshes'])-1
add_gable_roof_mesh()
def add(name,parent,mesh,pos,scale,extras=None):
 d={'name':name,'mesh':mesh_by_name[mesh],'translation':[float(x) for x in pos],'scale':[float(x) for x in scale]};
 if extras:d['extras']=extras
 nodes.append(d); nodes[byname[parent]].setdefault('children',[]).append(len(nodes)-1)
for a in range(0,360,10):
 if min(abs((a-x+180)%360-180) for x in [0,90,180,270])<9:continue
 rad=math.radians(a); x,z=355*math.sin(rad),355*math.cos(rad)
 for j in [-18,0,18]:add(f'Battlement_{a:03}_{j:+03}','City_Walls','cube_stone',(x+j*math.cos(rad),72,z-j*math.sin(rad)),(7,10,15))
for name,axis,start,end in [('South','z',375,555),('North','z',-635,-375),('East','x',375,555),('West','x',-555,-375)]:
 for v in range(start,end+1,30):
  x,z=(0,v) if axis=='z' else (v,0)
  for side in [-1,1]:add(f'Bridge_{name}_Parapet_{v}_{side}',f'Bridge_{name}','cube_stone',(side*21 if axis=='z' else x,39,z if axis=='z' else side*20),(4,12,28) if axis=='z' else (28,12,4))
  if v%60==0:add(f'Bridge_{name}_Pier_{v}',f'Bridge_{name}','cube_dark-stone',(x,3,z),(34,58,15) if axis=='z' else (15,58,34))
for a in range(0,360,30):
 rad=math.radians(a); x,z=70*math.sin(rad),70*math.cos(rad); add(f'Plaza_Bench_{a:03}','Props','cube_wood',(x,33,z),(10,2,3)); add(f'Plaza_Lamp_{a:03}','Props','cylinder_bronze',(x*.88,42,z*.88),(1.3,18,1.3)); add(f'Plaza_Lamp_Crystal_{a:03}','Props','cone_blue-crystal',(x*.88,53,z*.88),(4,7,4),{'effect':'blue-energy'})
for i in range(12):
 x=-210+(i%6)*35;z=-120+(i//6)*45;add(f'Market_Stall_{i:02}','District_Civic','cube_wood',(x,34,z),(24,8,16));add(f'Market_Canopy_{i:02}','District_Civic','cube_roof',(x,40,z),(26,2,18))
for i,x in enumerate(range(-275,276,25)):add(f'Farm_Fence_{i:02}','District_Agricultural','cube_wood',(x,34,218),(3,8,58))
g['asset']['generator']='Eloria Four Gates production environment 0.2'

align4(); g['buffers'][0]['byteLength']=len(buf); jb=json.dumps(g,separators=(',',':')).encode(); jb+=b' '*((-len(jb))%4); total=12+8+len(jb)+8+len(buf)
GLB.write_bytes(struct.pack('<4sII',b'glTF',2,total)+struct.pack('<I4s',len(jb),b'JSON')+jb+struct.pack('<I4s',len(buf),b'BIN\0')+buf)

meta=json.loads((PKG/'four-gates-city.json').read_text()); meta['assetVersion']='0.2.0'; meta['materials']={'strategy':'embedded-4x4-atlas','resolution':[1024,1024],'embeddedTextures':['four-gates-basecolor','four-gates-normal','four-gates-orm'],'channelPacking':{'orm':'R=occlusion,G=roughness,B=metallic'},'extension':'KHR_texture_transform'}; meta['knownLimitations']=[x for x in meta['knownLimitations'] if 'untextured' not in x]; meta['knownLimitations'].append('Atlas UVs are procedural cylindrical projections; landmark-specific authored unwraps remain recommended for final LOD0 close inspection.'); (PKG/'four-gates-city.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({'nodes':len(nodes),'meshes':len(g['meshes']),'materials':len(g['materials']),'embeddedTextures':3,'glbBytes':GLB.stat().st_size},indent=2))
