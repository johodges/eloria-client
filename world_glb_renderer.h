#ifndef ELORIA_WORLD_GLB_RENDERER_H
#define ELORIA_WORLD_GLB_RENDERER_H
#ifdef __cplusplus
extern "C" {
#endif
int world_glb_load(const char *, float, const float[3]);
void world_glb_draw(int);
void world_glb_destroy(void);
#ifdef __cplusplus
}
#endif
#endif
