#!/usr/bin/env python3
"""Import the supplied static Four Gates guard GLB into compact authored sources."""
from __future__ import annotations
import argparse, hashlib, io, json, struct
from pathlib import Path
import numpy as np
from PIL import Image

COMPONENTS={5126:"<f4",5125:"<u4",5123:"<u2"}
WIDTHS={"SCALAR":1,"VEC2":2,"VEC3":3,"VEC4":4}

def load_glb(path: Path):
 data=path.read_bytes(); magic,version,total=struct.unpack_from("<4sII",data,0)
 if magic!=b"glTF" or version!=2 or total!=len(data): raise ValueError("expected a complete glTF 2.0 binary")
 pos=12; chunks=[]
 while pos<total:
  length,kind=struct.unpack_from("<II",data,pos);pos+=8;chunks.append((kind,memoryview(data)[pos:pos+length]));pos+=length
 document=json.loads(bytes(chunks[0][1])); binary=next(chunk for kind,chunk in chunks if kind==0x004E4942)
 return data,document,binary

def accessor(document,binary,index):
 item=document["accessors"][index]; view=document["bufferViews"][item["bufferView"]]
 offset=view.get("byteOffset",0)+item.get("byteOffset",0); width=WIDTHS[item["type"]]
 return np.frombuffer(binary[offset:],dtype=COMPONENTS[item["componentType"]],count=item["count"]*width).reshape(-1,width)

def main():
 parser=argparse.ArgumentParser();parser.add_argument("source",type=Path);parser.add_argument("output",type=Path)
 parser.add_argument("--grid",type=int,default=37);parser.add_argument("--uv-grid",type=int,default=44);args=parser.parse_args()
 raw,doc,binary=load_glb(args.source)
 if doc.get("skins") or doc.get("animations"): raise ValueError("import contract expects the original static GLB")
 primitives=doc["meshes"][0]["primitives"]
 if len(primitives)!=1: raise ValueError("import contract expects one mesh primitive")
 primitive=primitives[0]; attrs=primitive["attributes"]
 source_pos=accessor(doc,binary,attrs["POSITION"]).astype(np.float64)
 source_norm=accessor(doc,binary,attrs["NORMAL"]).astype(np.float64)
 source_uv=accessor(doc,binary,attrs["TEXCOORD_0"]).astype(np.float64)
 indices=accessor(doc,binary,primitive["indices"]).reshape(-1,3).astype(np.int64)
 minimum=source_pos.min(0); span=np.maximum(source_pos.max(0)-minimum,1e-9)
 qpos=np.minimum(args.grid-1,((source_pos-minimum)/span*args.grid).astype(np.int32))
 quv=np.minimum(args.uv_grid-1,(np.clip(source_uv,0,1)*args.uv_grid).astype(np.int32))
 _,first,inverse=np.unique(np.c_[qpos,quv],axis=0,return_index=True,return_inverse=True)
 count=int(inverse.max())+1; weights=np.bincount(inverse,minlength=count)
 def average(values): return np.column_stack([np.bincount(inverse,weights=values[:,i],minlength=count)/weights for i in range(values.shape[1])])
 pos=average(source_pos); norm=average(source_norm); uv=average(source_uv)
 norm/=np.maximum(np.linalg.norm(norm,axis=1,keepdims=True),1e-9)
 faces=inverse[indices]; faces=faces[(faces[:,0]!=faces[:,1])&(faces[:,1]!=faces[:,2])&(faces[:,0]!=faces[:,2])]
 faces=np.unique(faces,axis=0)
 # glTF Y-up to Eloria Z-up, 1.9 metre character height, feet on z=0.
 pos=np.column_stack((pos[:,0],-pos[:,2],pos[:,1]-minimum[1]))*1.9
 norm=np.column_stack((norm[:,0],-norm[:,2],norm[:,1]));uv[:,1]=1.0-uv[:,1]
 z=pos[:,2]; x=pos[:,0]; ax=np.abs(x)
 bone=np.full(count,2,dtype=np.int16)
 left=x<0
 bone[z<.95]=np.where(left[z<.95],8,11);bone[z<.55]=np.where(left[z<.55],9,12);bone[z<.20]=np.where(left[z<.20],10,13)
 bone[z>1.52]=3; arm=(ax>.27)&(z>.68)&(z<1.62)
 bone[arm]=np.where(left[arm],4,6); fore=arm&(ax>.48);bone[fore]=np.where(left[fore],5,7); hand=arm&(ax>.70);bone[hand]=np.where(left[hand],16,17)
 # The spear and shield are authored as many disconnected metal/wood shells.
 # Weight each extreme connected shell rigidly to one hand; spatial weighting
 # otherwise cuts a long prop between torso, arm, and head bones.
 parent=np.arange(count,dtype=np.int32)
 def find(value):
  while parent[value]!=value: parent[value]=parent[parent[value]];value=parent[value]
  return value
 def union(first,second):
  first,second=find(int(first)),find(int(second))
  if first!=second: parent[second]=first
 for first,second,third in faces: union(first,second);union(first,third)
 roots=np.array([find(i) for i in range(count)])
 for component in np.unique(roots):
  members=roots==component; center=pos[members].mean(0); bounds=np.ptp(pos[members],axis=0)
  if center[0]<-.32 and (bounds[2]>.35 or center[0]<-.43): bone[members]=16
  elif center[0]>.34 and (max(bounds)>.30 or center[0]>.43): bone[members]=17
 # Keep one continuous mesh. Splitting faces at arbitrary height planes creates
 # visible cracks as independently weighted body-slot meshes animate.
 part=np.ones(len(faces),dtype=np.uint8)
 args.output.mkdir(parents=True,exist_ok=True)
 np.savez_compressed(args.output/"guard_mesh.npz",positions=pos.astype(np.float32),normals=norm.astype(np.float32),uv=uv.astype(np.float32),faces=faces.astype(np.uint32),bones=bone,parts=part)
 image=doc["images"][doc["textures"][doc["materials"][0]["pbrMetallicRoughness"]["baseColorTexture"]["index"]]["source"]]
 view=doc["bufferViews"][image["bufferView"]]; embedded=bytes(binary[view.get("byteOffset",0):view.get("byteOffset",0)+view["byteLength"]])
 texture=Image.open(io.BytesIO(embedded)).convert("RGB").resize((2048,2048),Image.Resampling.LANCZOS)
 # Avoid optimizer-dependent output and write atomically so interrupted imports
 # cannot leave a plausible-looking but truncated authored texture.
 temporary=args.output/"guard_atlas.webp.tmp"
 texture.save(temporary,format="WEBP",quality=95,method=6)
 temporary.replace(args.output/"guard_atlas.webp")
 metadata={"source_file":args.source.name,"source_sha256":hashlib.sha256(raw).hexdigest(),"source_vertices":len(source_pos),"source_triangles":len(indices),"converted_vertices":len(pos),"converted_triangles":len(faces),"source_generator":doc.get("asset",{}).get("generator"),"source_had_skin":False,"source_had_animations":False,"coordinate_conversion":"glTF Y-up to Eloria Z-up; 1.9m height"}
 (args.output/"SOURCE.json").write_text(json.dumps(metadata,indent=2)+"\n")
 print(json.dumps(metadata,indent=2))
if __name__=="__main__":main()
