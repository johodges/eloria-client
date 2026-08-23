#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
#include "gamewin.h"
#include "merchant.h"
#include "multiplayer.h"

#define MERCHANT_MAX_ITEMS 20
typedef struct { Uint16 index, image_id; Uint32 buy, sell, owned; char name[64]; } merchant_item;
static merchant_item items[MERCHANT_MAX_ITEMS];
static int merchant_win = -1, item_count = 0, selected = -1, sell_mode = 0;
static Uint16 merchant_actor = 0;
static Uint32 merchant_gold = 0, merchant_load = 0, merchant_capacity = 0;
static char merchant_name[32];

static Uint16 read_u16(const Uint8 **p) { Uint16 v; memcpy(&v,*p,2); *p+=2; return SDL_SwapLE16(v); }
static Uint32 read_u32(const Uint8 **p) { Uint32 v; memcpy(&v,*p,4); *p+=4; return SDL_SwapLE32(v); }
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size) { const Uint8 *z=memchr(*p,0,end-*p); size_t n; if(!z)return 0; n=z-*p; if(n>=size)n=size-1; memcpy(out,*p,n); out[n]=0; *p=z+1; return 1; }
static void send_command(const char *cmd) { Uint8 b[128]; size_t n=strlen(cmd); if(n+1>=sizeof(b))return; b[0]=RAW_TEXT; memcpy(b+1,cmd,n+1); my_tcp_send(b,n+1); }
static void button(int x,int y,int w,const char *s,int active) { glDisable(GL_TEXTURE_2D); glColor4f(active?.24f:.12f,active?.43f:.25f,active?.48f:.28f,.9f); glBegin(GL_QUADS); glVertex2i(x,y);glVertex2i(x+w,y);glVertex2i(x+w,y+24);glVertex2i(x,y+24);glEnd();glEnable(GL_TEXTURE_2D);glColor3f(.95f,.91f,.78f);draw_string_small(x+8,y+5,(const unsigned char*)s,1); }
static int visible_row(int row) { int i,n=0; for(i=0;i<item_count;i++) if(!sell_mode||items[i].owned){if(n++==row)return i;} return -1; }
static int display_handler(window_info *win) { int i,row=0;char s[160];button(12,10,100,"Buy",!sell_mode);button(120,10,100,"Sell",sell_mode);glColor3f(.82f,.86f,.82f);safe_snprintf(s,sizeof(s),"%s   Gold %u   Carry %u/%u",merchant_name,merchant_gold,merchant_load,merchant_capacity);draw_string_small(240,16,(const unsigned char*)s,1);glColor3f(.65f,.75f,.72f);draw_string_small(14,48,(const unsigned char*)"Item",1);draw_string_small(310,48,(const unsigned char*)"Unit price",1);draw_string_small(440,48,(const unsigned char*)"Owned / Affordable",1);for(i=0;i<item_count;i++){int y;if(sell_mode&&!items[i].owned)continue;y=70+row++*20;if(i==selected){glDisable(GL_TEXTURE_2D);glColor4f(.20f,.38f,.42f,.85f);glBegin(GL_QUADS);glVertex2i(10,y-2);glVertex2i(win->len_x-10,y-2);glVertex2i(win->len_x-10,y+17);glVertex2i(10,y+17);glEnd();glEnable(GL_TEXTURE_2D);}glColor3f(.93f,.91f,.82f);draw_string_small(14,y,(const unsigned char*)items[i].name,1);safe_snprintf(s,sizeof(s),"%u gc",sell_mode?items[i].sell:items[i].buy);draw_string_small(310,y,(const unsigned char*)s,1);safe_snprintf(s,sizeof(s),"%u / %u",items[i].owned,items[i].buy?merchant_gold/items[i].buy:0);draw_string_small(440,y,(const unsigned char*)s,1);}if(selected>=0){button(12,win->len_y-38,80,sell_mode?"Sell 1":"Buy 1",1);button(100,win->len_y-38,90,sell_mode?"Sell 10":"Buy 10",0);button(198,win->len_y-38,105,sell_mode?"Sell Max":"Buy Max",0);}return 1; }
static void trade(const char *quantity) { char cmd[128]; if(selected<0)return;safe_snprintf(cmd,sizeof(cmd),"#shop %s %u %u %s",sell_mode?"sell":"buy",merchant_actor,items[selected].index,quantity);send_command(cmd); }
static int click_handler(window_info *win,int mx,int my,Uint32 flags) { int row,index;(void)flags;if(my>=10&&my<=34){if(mx>=12&&mx<=112){sell_mode=0;selected=-1;}else if(mx>=120&&mx<=220){sell_mode=1;selected=-1;}return 1;}row=(my-68)/20;if(my>=68&&(index=visible_row(row))>=0){selected=index;return 1;}if(selected>=0&&my>=win->len_y-42){if(mx>=12&&mx<=92)trade("1");else if(mx>=100&&mx<=190)trade("10");else if(mx>=198&&mx<=303)trade("max");}return 1; }
static int close_handler(window_info *win) { (void)win;merchant_win=-1;return 1; }
void display_merchant(void) { if(merchant_win<0){merchant_win=create_window("Merchant",game_root_win,0,100,70,720,520,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(merchant_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(merchant_win,ELW_HANDLER_CLICK,&click_handler);set_window_handler(merchant_win,ELW_HANDLER_CLOSE,&close_handler);}else show_window(merchant_win); }
void close_merchant(void) { if(merchant_win>=0)destroy_window(merchant_win);merchant_win=-1; }
void merchant_update(const Uint8 *data,int len) { const Uint8 *p=data,*end=data+len;int i,count;if(len<16)return;merchant_actor=read_u16(&p);merchant_gold=read_u32(&p);merchant_load=read_u32(&p);merchant_capacity=read_u32(&p);count=read_u16(&p);if(!read_text(&p,end,merchant_name,sizeof(merchant_name)))return;item_count=0;selected=-1;for(i=0;i<count&&i<MERCHANT_MAX_ITEMS;i++){merchant_item *e=&items[item_count];if(end-p<16)break;e->index=read_u16(&p);e->buy=read_u32(&p);e->sell=read_u32(&p);e->owned=read_u32(&p);e->image_id=read_u16(&p);if(!read_text(&p,end,e->name,sizeof(e->name)))break;item_count++;}display_merchant(); }
