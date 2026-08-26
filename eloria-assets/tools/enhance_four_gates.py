import json, math, struct
from pathlib import Path
import numpy as np
from PIL import Image

PKG=Path('four-gates-city-package'); GLB=PKG/'four-gates-city.glb'; TEX=PKG/'textures'; TEX.mkdir(exist_ok=True)
raw=GLB.read_bytes(); jlen,jtype=struct.unpack_from('<I4s',raw,12); g=json.loads(raw[20:20+jlen]); boff=20+jlen; blen,btype=struct.unpack_from('<I4s',raw,boff); buf=bytearray(raw[boff+8:boff+8+blen])
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

# Add generated production atlas plus deterministic normal and ORM companions.
src=Image.open(TEX/'four-gates-material-atlas-source.png').convert('RGB').resize((1024,1024),Image.Resampling.LANCZOS); src.save(TEX/'four-gates-material-basecolor.png',optimize=True)
gray=np.asarray(src.convert('L'),np.float32)/255.; gy,gx=np.gradient(gray); n=np.dstack((-gx*2.1,-gy*2.1,np.ones_like(gray))); n/=np.linalg.norm(n,axis=2,keepdims=True); Image.fromarray(((n*.5+.5)*255).astype(np.uint8)).save(TEX/'four-gates-material-normal.png',optimize=True)
orm=np.zeros((1024,1024,3),np.uint8); orm[:,:,0]=235; orm[:,:,1]=185
for c,r,val in [(1,1,195),(2,1,215)]:orm[r*256:(r+1)*256,c*256:(c+1)*256,2]=val
for c,r,val in [(1,1,80),(2,1,120),(0,3,45),(1,3,55),(2,3,70)]:orm[r*256:(r+1)*256,c*256:(c+1)*256,1]=val
Image.fromarray(orm).save(TEX/'four-gates-material-orm.png',optimize=True)

# UVs and normals for every reusable primitive.
for mesh in g['meshes']:
 for p in mesh['primitives']:
  v=read_pos(p['attributes']['POSITION']); n=v.copy(); n[:,1]*=.7; n/=np.maximum(np.linalg.norm(n,axis=1,keepdims=True),1e-6)
  u=(np.arctan2(v[:,2],v[:,0])/(2*np.pi)+.5)%1; vv=(v[:,1]-v[:,1].min())/max(float(np.ptp(v[:,1])),1e-6); uv=np.column_stack((u,vv)).astype(np.float32)
  p['attributes']['NORMAL']=add_acc(n,'VEC3'); p['attributes']['TEXCOORD_0']=add_acc(uv,'VEC2')

iv=[]
for fn in ['four-gates-material-basecolor.png','four-gates-material-normal.png','four-gates-material-orm.png']:iv.append(add_view((TEX/fn).read_bytes()))
g['images']=[{'name':'four-gates-basecolor','bufferView':iv[0],'mimeType':'image/png'},{'name':'four-gates-normal','bufferView':iv[1],'mimeType':'image/png'},{'name':'four-gates-orm','bufferView':iv[2],'mimeType':'image/png'}]
g['samplers']=[{'magFilter':9729,'minFilter':9987,'wrapS':10497,'wrapT':10497}]; g['textures']=[{'sampler':0,'source':i} for i in range(3)]; g['extensionsUsed']=['KHR_texture_transform']
tile={'stone':(0,0),'dark-stone':(1,0),'paving':(2,0),'rock':(3,0),'roof':(0,1),'bronze':(1,1),'wood':(3,1),'plaster':(0,2),'soil':(1,2),'grass':(2,2),'snow':(3,2),'water':(0,3),'blue-crystal':(1,3),'waterfall':(2,3),'vegetation':(3,3)}
for m in g['materials']:
 c,r=tile[m['name']]; tr={'offset':[c*.25,(3-r)*.25],'scale':[.25,.25]}; ti=lambda i:{'index':i,'extensions':{'KHR_texture_transform':tr}}
 p=m['pbrMetallicRoughness']; p['baseColorTexture']=ti(0); p['metallicRoughnessTexture']=ti(2); p['metallicFactor']=1; p['roughnessFactor']=1; m['normalTexture']=ti(1); m['occlusionTexture']=ti(2)

# Add maintainable detail nodes using existing shared meshes.
nodes=g['nodes']; byname={n['name']:i for i,n in enumerate(nodes)}; mesh_by_name={m['name']:i for i,m in enumerate(g['meshes'])}
mat_by_name={m['name']:i for i,m in enumerate(g['materials'])}
def ensure_mesh(name,prototype,material):
 if name in mesh_by_name:return
 src=g['meshes'][mesh_by_name[prototype]]; clone={'name':name,'primitives':[dict(src['primitives'][0])]}; clone['primitives'][0]['attributes']=dict(src['primitives'][0]['attributes']); clone['primitives'][0]['material']=mat_by_name[material]; g['meshes'].append(clone); mesh_by_name[name]=len(g['meshes'])-1
ensure_mesh('cube_wood','cube_stone','wood'); ensure_mesh('cube_roof','cube_stone','roof'); ensure_mesh('cylinder_bronze','cylinder_stone','bronze')
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
