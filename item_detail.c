#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "elwindows.h"
#include "font.h"
#include "gamewin.h"
#include "item_detail.h"

static int detail_win=-1;
static Uint16 image_id=0;
static Uint32 quantity=0;
static Uint8 equipped=0;
static char item_name[80],category[32],equip_type[32],description[512];
static char stats[256],comparison_name[80],comparison[256];
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static Uint32 read_u32(const Uint8 **p){Uint32 v;memcpy(&v,*p,4);*p+=4;return SDL_SwapLE32(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static int display_handler(window_info *win){char text[192];(void)win;glColor3f(.96f,.86f,.55f);draw_string_zoomed(18,16,(const unsigned char*)item_name,1,1.15f);glColor3f(.68f,.78f,.75f);safe_snprintf(text,sizeof(text),"%s   Quantity %u%s",category,quantity,equipped?"   Equipped":"");draw_string_small(18,48,(const unsigned char*)text,1);glColor3f(.92f,.91f,.84f);draw_string_zoomed(18,78,(const unsigned char*)description,4,.85f);glColor3f(.66f,.78f,.74f);draw_string_small(18,174,(const unsigned char*)"Properties",1);glColor3f(.92f,.91f,.84f);draw_string_zoomed(18,198,(const unsigned char*)stats,3,.85f);if(comparison_name[0]){glColor3f(.66f,.78f,.74f);safe_snprintf(text,sizeof(text),"Compared with equipped %s",comparison_name);draw_string_small(18,278,(const unsigned char*)text,1);glColor3f(.78f,.92f,.68f);draw_string_zoomed(18,302,(const unsigned char*)comparison,3,.85f);}glColor3f(.62f,.70f,.68f);if(equip_type[0])draw_string_small(18,382,(const unsigned char*)"Tip: double-click to equip; right-click any item to inspect.",1);else draw_string_small(18,382,(const unsigned char*)"Tip: right-click inventory items to inspect them.",1);return 1;}
static int close_handler(window_info *win){(void)win;detail_win=-1;return 1;}
void display_item_detail(void){if(detail_win<0){detail_win=create_window("Item Details",game_root_win,0,140,90,650,430,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(detail_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(detail_win,ELW_HANDLER_CLOSE,&close_handler);}else show_window(detail_win);}
void close_item_detail(void){if(detail_win>=0)destroy_window(detail_win);detail_win=-1;}
void item_detail_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;if(len<7)return;image_id=read_u16(&p);quantity=read_u32(&p);equipped=*p++;if(!read_text(&p,end,item_name,sizeof(item_name))||!read_text(&p,end,category,sizeof(category))||!read_text(&p,end,equip_type,sizeof(equip_type))||!read_text(&p,end,description,sizeof(description))||!read_text(&p,end,stats,sizeof(stats))||!read_text(&p,end,comparison_name,sizeof(comparison_name))||!read_text(&p,end,comparison,sizeof(comparison)))return;display_item_detail();}
