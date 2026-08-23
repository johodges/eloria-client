#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "elwindows.h"
#include "font.h"
#include "gamewin.h"
#include "combat_hud.h"

static int combat_win=-1;
static Uint8 combat_event=0;
static Uint16 target_id=0,player_health=0,player_max=1,target_health=0,target_max=1,recent_damage=0;
static Uint32 end_at=0;
static char target_name[80];
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static void bar(int x,int y,int w,Uint16 value,Uint16 maximum,float r,float g,float b){int fill=maximum?value*w/maximum:0;glDisable(GL_TEXTURE_2D);glColor4f(.10f,.10f,.10f,.85f);glBegin(GL_QUADS);glVertex2i(x,y);glVertex2i(x+w,y);glVertex2i(x+w,y+14);glVertex2i(x,y+14);glEnd();glColor4f(r,g,b,.95f);glBegin(GL_QUADS);glVertex2i(x+1,y+1);glVertex2i(x+fill-1,y+1);glVertex2i(x+fill-1,y+13);glVertex2i(x+1,y+13);glEnd();glEnable(GL_TEXTURE_2D);}
static int display_handler(window_info *win){char text[128];const char *event_text="Engaged";if(end_at&&SDL_GetTicks()>end_at){hide_window(win->window_id);return 1;}glColor3f(.96f,.86f,.55f);draw_string_small(12,10,(const unsigned char*)target_name,1);safe_snprintf(text,sizeof(text),"%u / %u",target_health,target_max);draw_string_small(238,10,(const unsigned char*)text,1);bar(12,30,310,target_health,target_max,.72f,.18f,.14f);glColor3f(.78f,.88f,.82f);draw_string_small(12,54,(const unsigned char*)"You",1);safe_snprintf(text,sizeof(text),"%u / %u",player_health,player_max);draw_string_small(238,54,(const unsigned char*)text,1);bar(12,74,310,player_health,player_max,.18f,.58f,.32f);if(combat_event==1)event_text="Hit";else if(combat_event==2)event_text="Miss";else if(combat_event==3)event_text="You were hit";else if(combat_event==4)event_text="Dodged";else if(combat_event==5)event_text=target_health?"Combat ended":"Defeated";glColor3f(combat_event==3?.95f:.72f,combat_event==3?.42f:.82f,.40f);safe_snprintf(text,sizeof(text),recent_damage?"%s: %u damage":"%s",event_text,recent_damage);draw_string_small(12,100,(const unsigned char*)text,1);return 1;}
static int close_handler(window_info *win){(void)win;combat_win=-1;return 1;}
void display_combat_hud(void){if(combat_win<0){combat_win=create_window("Combat",game_root_win,0,20,110,350,135,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(combat_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(combat_win,ELW_HANDLER_CLOSE,&close_handler);}else show_window(combat_win);}
void close_combat_hud(void){if(combat_win>=0)destroy_window(combat_win);combat_win=-1;}
void combat_hud_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;if(len<14)return;combat_event=*p++;target_id=read_u16(&p);player_health=read_u16(&p);player_max=read_u16(&p);target_health=read_u16(&p);target_max=read_u16(&p);recent_damage=read_u16(&p);if(!read_text(&p,end,target_name,sizeof(target_name)))return;end_at=combat_event==5?SDL_GetTicks()+4000:0;display_combat_hud();}
