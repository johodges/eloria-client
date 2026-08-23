#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "elwindows.h"
#include "font.h"
#include "gamewin.h"
#include "navigation_hud.h"

static int navigation_win=-1;
static Uint8 active=0;
static Uint16 waypoint_x=0,waypoint_y=0,distance=0;
static char map_id[80],label[80];
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static int display_handler(window_info *win){char text[192];(void)win;glColor3f(.96f,.86f,.55f);draw_string_small(12,10,(const unsigned char*)label,1);glColor3f(.80f,.88f,.84f);safe_snprintf(text,sizeof(text),"%s  [%u, %u]",map_id,waypoint_x,waypoint_y);draw_string_small(12,34,(const unsigned char*)text,1);glColor3f(.58f,.86f,.68f);safe_snprintf(text,sizeof(text),distance?"%u tile%s away":"Destination map",distance,distance==1?"":"s");draw_string_small(12,58,(const unsigned char*)text,1);return 1;}
static int close_handler(window_info *win){(void)win;navigation_win=-1;return 1;}
void display_navigation_hud(void){if(navigation_win<0){navigation_win=create_window("Navigation",game_root_win,0,20,260,350,95,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(navigation_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(navigation_win,ELW_HANDLER_CLOSE,&close_handler);}else show_window(navigation_win);}
void close_navigation_hud(void){if(navigation_win>=0)destroy_window(navigation_win);navigation_win=-1;}
void navigation_hud_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;if(len<9)return;active=*p++;waypoint_x=read_u16(&p);waypoint_y=read_u16(&p);distance=read_u16(&p);if(!read_text(&p,end,map_id,sizeof(map_id))||!read_text(&p,end,label,sizeof(label)))return;if(!active){if(navigation_win>=0)hide_window(navigation_win);return;}display_navigation_hud();}
