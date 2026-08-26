#ifndef ACTOR_GLB_RUNTIME_H
#define ACTOR_GLB_RUNTIME_H
#ifdef __cplusplus
extern "C" {
#endif
int actor_glb_is_luminous(const void *act);
int actor_glb_draw(void *act, unsigned int use_lightning, unsigned int use_textures);
void actor_glb_runtime_destroy(void);
#ifdef __cplusplus
}
#endif
#endif
