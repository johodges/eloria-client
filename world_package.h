#ifndef ELORIA_WORLD_PACKAGE_H
#define ELORIA_WORLD_PACKAGE_H
#ifdef __cplusplus
extern "C" {
#endif
typedef void (world_update_func)(char *, float);
/* 1=loaded, 0=package absent/not selected, -1=present but invalid. */
int load_world_package(const char *, world_update_func *);
void destroy_world_package(void);
int world_package_active(void);
void world_gltf_to_eloria(const float source[3], float units_per_meter,
	const float origin[3], float destination[3]);
#ifdef __cplusplus
}
#endif
#endif
