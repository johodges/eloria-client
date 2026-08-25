#include "world_package.h"
#include "world_glb_renderer.h"
#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <sstream>
#include <string>
#include <vector>
#include <nlohmann/json.hpp>
extern "C" {
#include "asc.h"
#include "errors.h"
#include "io/map_io.h"
#include "tiles.h"
extern unsigned char *tile_map, *height_map;
extern int tile_map_size_x, tile_map_size_y;
extern float ambient_r, ambient_g, ambient_b;
extern int dungeon;
}
namespace {
using json=nlohmann::json;
bool active=false;
uint32_t le32(const unsigned char *p) { return p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24; }
bool exists(const std::string&p) { std::ifstream f(p.c_str(),std::ios::binary); return f.good(); }
std::string dir(const std::string&p) { size_t n=p.find_last_of("/\\"); return n==std::string::npos?".":p.substr(0,n); }
bool safe_rel(const std::string&p) {
	if(p.empty()||p.size()>240||p[0]=='/'||p[0]=='\\'||(p.size()>1&&p[1]==':')||p.find('\\')!=std::string::npos)return false;
	std::stringstream s(p); std::string c; while(std::getline(s,c,'/'))if(c.empty()||c=="."||c=="..")return false; return true;
}
bool read(const std::string&p,size_t max,std::vector<unsigned char>&v,std::string&e) {
	std::ifstream f(p.c_str(),std::ios::binary|std::ios::ate); if(!f){e="cannot open '"+p+"'";return false;}
	std::streamoff n=f.tellg(); if(n<0||uint64_t(n)>max){e="file exceeds size limit";return false;}
	v.resize(size_t(n)); f.seekg(0); if(n&&!f.read((char*)v.data(),n)){e="short read";return false;} return true;
}
bool vec3(const json&v,float o[3],const char*n,std::string&e) {
	if(!v.is_array()||v.size()!=3){e=std::string(n)+" must have three numbers";return false;}
	for(int i=0;i<3;i++){if(!v[i].is_number()){e=std::string(n)+" contains a non-number";return false;}o[i]=v[i].get<float>();if(!std::isfinite(o[i])){e=std::string(n)+" contains a non-finite number";return false;}}return true;
}
bool glb(const std::string&p,std::string&e) {
	std::vector<unsigned char>b;if(!read(p,1024u*1024u*1024u,b,e))return false;
	if(b.size()<20||le32(b.data())!=0x46546c67||le32(b.data()+4)!=2||le32(b.data()+8)!=b.size()){e="invalid GLB 2.0 header or length";return false;}
	size_t o=12;json j;bool got=false;while(o<b.size()){if(b.size()-o<8){e="truncated GLB chunk";return false;}uint32_t n=le32(b.data()+o),t=le32(b.data()+o+4);o+=8;if(n>b.size()-o){e="GLB chunk out of range";return false;}if(t==0x4e4f534a&&!got){try{j=json::parse(b.begin()+o,b.begin()+o+n);}catch(const std::exception&x){e=std::string("invalid GLB JSON: ")+x.what();return false;}got=true;}o+=n;}
	if(!got||!j.contains("asset")||j["asset"].value("version","")!="2.0"){e="missing glTF 2.0 asset metadata";return false;}
	if(!j.contains("meshes")||!j["meshes"].is_array()){e="GLB contains no meshes";return false;}
	if(!j.value("extensionsRequired",json::array()).empty()){e="required glTF extensions are unsupported";return false;}return true;
}
bool collision(const std::string&p,int w,int h,std::string&e) {
	std::vector<unsigned char>b;if(!read(p,256u*1024u*1024u,b,e))return false;
	if(b.size()<16||memcmp(b.data(),"EWCG",4)){e="collision has invalid EWCG signature";return false;}
	unsigned ver=b[4]|unsigned(b[5])<<8;uint32_t bw=le32(b.data()+8),bh=le32(b.data()+12);uint64_t cells=uint64_t(bw)*bh;
	if(ver!=1){e="unsupported collision version";return false;}if(bw!=unsigned(w)||bh!=unsigned(h)){e="collision dimensions mismatch";return false;}
	if(cells>256u*1024u*1024u||b.size()!=16+cells){e="collision payload size mismatch";return false;}
	height_map=(unsigned char*)malloc(size_t(cells));if(!height_map){e="collision allocation failed";return false;}memcpy(height_map,b.data()+16,size_t(cells));return true;
}
void rollback(){free(tile_map);free(height_map);tile_map=height_map=NULL;tile_map_size_x=tile_map_size_y=0;}
}
extern "C" void world_gltf_to_eloria(const float s[3],float u,const float o[3],float d[3]){d[0]=o[0]+s[0]/u;d[1]=o[1]-s[2]/u;d[2]=o[2]+s[1]/u;}
extern "C" int load_world_package(const char *name,world_update_func *update){
	std::string in=name?name:"",m;if(in.size()>5&&in.substr(in.size()-5)==".json")m=in;else if(in.find('.')==std::string::npos)m="./maps/"+in+"/world.json";else return 0;
	if(!exists(m))return 0;std::vector<unsigned char>b;std::string e;if(!read(m,4u*1024u*1024u,b,e)){LOG_ERROR("World package '%s': %s",m.c_str(),e.c_str());return -1;}
	json r;try{r=json::parse(b.begin(),b.end());}catch(const std::exception&x){LOG_ERROR("World package '%s': invalid JSON: %s",m.c_str(),x.what());return -1;}
	if(!r.is_object()||r.value("format","")!="eloria-world"){LOG_ERROR("World package '%s': format must be 'eloria-world'",m.c_str());return -1;}
	if(!r.contains("version")||!r["version"].is_number_unsigned()||r["version"]!=1){LOG_ERROR("World package '%s': unsupported version (supported: 1)",m.c_str());return -1;}
	std::string id=r.value("id",""),scene=r.value("scene","world.glb"),col=r.value("collision","");
	if(id.empty()||id.size()>64||!std::all_of(id.begin(),id.end(),[](char c){return std::isalnum((unsigned char)c)||c=='_'||c=='-';})){LOG_ERROR("World package '%s': invalid id",m.c_str());return -1;}
	if(!safe_rel(scene)||!safe_rel(col)){LOG_ERROR("World package '%s': unsafe scene/collision path",m.c_str());return -1;}std::string scene_path=dir(m)+"/"+scene;if(!glb(scene_path,e)){LOG_ERROR("World package '%s': scene: %s",m.c_str(),e.c_str());return -1;}
	float lo[3],hi[3];if(!r.contains("bounds")||!vec3(r["bounds"]["minimum"],lo,"bounds.minimum",e)||!vec3(r["bounds"]["maximum"],hi,"bounds.maximum",e)){LOG_ERROR("World package '%s': %s",m.c_str(),e.c_str());return -1;}
	for(int i=0;i<3;i++)if(lo[i]>=hi[i]){LOG_ERROR("World package '%s': inverted bounds",m.c_str());return -1;}
	int w=r.value("collision_width",int(std::ceil((hi[0]-lo[0])*2))),h=r.value("collision_height",int(std::ceil((hi[2]-lo[2])*2)));
	if(w<=0||h<=0||w%6||h%6||uint64_t(w)*h>256u*1024u*1024u){LOG_ERROR("World package '%s': collision dimensions must be positive multiples of six",m.c_str());return -1;}
	if(!collision(dir(m)+"/"+col,w,h,e)){LOG_ERROR("World package '%s': collision: %s",m.c_str(),e.c_str());return -1;}
	tile_map_size_x=(w+5)/6;tile_map_size_y=(h+5)/6;tile_map=(unsigned char*)malloc(size_t(tile_map_size_x)*tile_map_size_y);if(!tile_map){rollback();return -1;}memset(tile_map,255,size_t(tile_map_size_x)*tile_map_size_y);
	json env=r.value("environment",json::object());float a[3];if(!vec3(env.value("ambient_color",json::array({.6,.65,.75})),a,"environment.ambient_color",e)){rollback();LOG_ERROR("World package '%s': %s",m.c_str(),e.c_str());return -1;}
	float intensity=env.value("ambient_intensity",1.0f);if(!std::isfinite(intensity)||intensity<0||intensity>16){rollback();LOG_ERROR("World package '%s': invalid ambient intensity",m.c_str());return -1;}
	json coordinates=r.value("coordinates",json::object());float origin[3];if(!vec3(coordinates.value("origin",json::array({0,0,0})),origin,"coordinates.origin",e)){rollback();LOG_ERROR("World package '%s': %s",m.c_str(),e.c_str());return -1;}float units=coordinates.value("units_per_meter",1.0f);if(!std::isfinite(units)||units<=0||coordinates.value("up_axis","Y")!="Y"||coordinates.value("forward_axis","-Z")!="-Z"){rollback();LOG_ERROR("World package '%s': unsupported coordinates",m.c_str());return -1;}if(!world_glb_load(scene_path.c_str(),units,origin)){world_glb_destroy();rollback();LOG_ERROR("World package '%s': GLB render resource creation failed",m.c_str());return -1;}
	ambient_r=a[0]*intensity;ambient_g=a[1]*intensity;ambient_b=a[2]*intensity;dungeon=0;safe_strncpy(map_file_name,m.c_str(),sizeof(map_file_name));active=true;if(update)update((char*)"Loading portable world",100);LOG_INFO("Loaded package '%s' (%dx%d)",m.c_str(),w,h);return 1;
}
extern "C" void destroy_world_package(){world_glb_destroy();active=false;}extern "C" int world_package_active(){return active?1:0;}
extern "C" void world_package_draw(int transparent){if(active)world_glb_draw(transparent);}
