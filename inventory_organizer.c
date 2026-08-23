#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
#include "asc.h"
#define draw_string_small(x, y, text, max_lines) draw_string_small_zoomed((x), (y), (text), (max_lines), 1.0f)
#include "gamewin.h"
#include "inventory_organizer.h"
#include "multiplayer.h"
#include "notepad.h"

#define ORGANIZER_MAX_ITEMS 36
#define ORGANIZER_ROWS 16
typedef struct { Uint8 slot,flags; Uint16 image_id; Uint32 quantity,emu; char name[80],category[32]; } organizer_item;
static organizer_item items[ORGANIZER_MAX_ITEMS];
static int organizer_win=-1,item_count=0,selected=-1,page=0,category_filter=0;
static Uint32 gold=0,carried=0,capacity=0;
static char search_text[64]="";
static INPUT_POPUP search_popup,drop_popup;
static const char *filter_names[]={"All","Equipment","Consumables","Resources","Other"};
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static Uint32 read_u32(const Uint8 **p){Uint32 v;memcpy(&v,*p,4);*p+=4;return SDL_SwapLE32(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static int contains_casefold(const char *text,const char *query){size_t i,j;if(!query[0])return 1;for(i=0;text[i];i++){for(j=0;query[j]&&text[i+j]&&tolower((unsigned char)text[i+j])==tolower((unsigned char)query[j]);j++);if(!query[j])return 1;}return 0;}
static int category_matches(const organizer_item *e){int equipment=!strcmp(e->category,"Weapons")||!strcmp(e->category,"Armor")||!strcmp(e->category,"Clothes")||!strcmp(e->category,"Jewelry");int consumable=!strcmp(e->category,"Food")||!strcmp(e->category,"Potions")||!strcmp(e->category,"Books");int resource=!strcmp(e->category,"Flowers")||!strcmp(e->category,"Ores")||!strcmp(e->category,"Metals")||!strcmp(e->category,"Minerals")||!strcmp(e->category,"Essences")||!strcmp(e->category,"Animal");if(!category_filter)return 1;if(category_filter==1)return equipment;if(category_filter==2)return consumable;if(category_filter==3)return resource;return !equipment&&!consumable&&!resource;}
static int visible_index(int ordinal){int i,n=0;for(i=0;i<item_count;i++)if(category_matches(&items[i])&&contains_casefold(items[i].name,search_text)){if(n++==ordinal)return i;}return -1;}
static void send_raw(const char *cmd){Uint8 b[128];size_t n=strlen(cmd);if(n+1>=sizeof(b))return;b[0]=RAW_TEXT;memcpy(b+1,cmd,n+1);my_tcp_send(b,n+1);}
static void refresh(void){send_raw("#inventory");}
static void set_search(const char *text,void *data){(void)data;safe_strncpy(search_text,text,sizeof(search_text));page=0;selected=-1;}
static void drop_quantity(const char *text,void *data){long amount;char *end;(void)data;if(selected<0)return;amount=strtol(text,&end,10);if(*end||amount<1||amount>items[selected].quantity)return;{Uint8 b[6];b[0]=DROP_ITEM;b[1]=items[selected].slot;*((Uint32*)(b+2))=SDL_SwapLE32((Uint32)amount);my_tcp_send(b,6);}refresh();}
static void button(int x,int y,int w,const char *s,int active){glDisable(GL_TEXTURE_2D);glColor4f(active?.24f:.12f,active?.43f:.25f,active?.48f:.28f,.9f);glBegin(GL_QUADS);glVertex2i(x,y);glVertex2i(x+w,y);glVertex2i(x+w,y+24);glVertex2i(x,y+24);glEnd();glEnable(GL_TEXTURE_2D);glColor3f(.95f,.91f,.78f);draw_string_small(x+7,y+5,(const unsigned char*)s,1);}
static int display_handler(window_info *win){int row,index;char text[180];button(12,10,105,"Search",search_text[0]);button(125,10,125,filter_names[category_filter],category_filter>0);button(258,10,90,"Refresh",0);glColor3f(.82f,.86f,.82f);safe_snprintf(text,sizeof(text),"Gold %u   Carry %u/%u",gold,carried,capacity);draw_string_small(380,16,(const unsigned char*)text,1);glColor3f(.65f,.75f,.72f);draw_string_small(14,48,(const unsigned char*)"Item",1);draw_string_small(350,48,(const unsigned char*)"Category",1);draw_string_small(500,48,(const unsigned char*)"Quantity",1);draw_string_small(610,48,(const unsigned char*)"Weight",1);for(row=0;row<ORGANIZER_ROWS;row++){int ordinal=page*ORGANIZER_ROWS+row;int y=70+row*22;index=visible_index(ordinal);if(index<0)break;if(index==selected){glDisable(GL_TEXTURE_2D);glColor4f(.20f,.38f,.42f,.85f);glBegin(GL_QUADS);glVertex2i(10,y-3);glVertex2i(win->len_x-10,y-3);glVertex2i(win->len_x-10,y+17);glVertex2i(10,y+17);glEnd();glEnable(GL_TEXTURE_2D);}glColor3f(.93f,.91f,.82f);draw_string_small(14,y,(const unsigned char*)items[index].name,1);draw_string_small(350,y,(const unsigned char*)items[index].category,1);safe_snprintf(text,sizeof(text),"%u",items[index].quantity);draw_string_small(500,y,(const unsigned char*)text,1);safe_snprintf(text,sizeof(text),"%u EMU",items[index].quantity*items[index].emu);draw_string_small(610,y,(const unsigned char*)text,1);}button(12,win->len_y-38,85,"Previous",page>0);button(105,win->len_y-38,70,"Next",visible_index((page+1)*ORGANIZER_ROWS)>=0);if(selected>=0){button(250,win->len_y-38,90,"Inspect",1);button(348,win->len_y-38,80,"Use",0);button(436,win->len_y-38,120,"Drop Qty",0);button(564,win->len_y-38,110,"Drop All",0);}return 1;}
static int click_handler(window_info *win,int mx,int my,Uint32 flags){int row,index;(void)flags;if(my>=10&&my<=34){if(mx>=12&&mx<=117)display_popup_win(&search_popup,"Item name contains");else if(mx>=125&&mx<=250){category_filter=(category_filter+1)%5;page=0;selected=-1;}else if(mx>=258&&mx<=348)refresh();return 1;}if(my>=68&&my<68+ORGANIZER_ROWS*22){row=(my-68)/22;index=visible_index(page*ORGANIZER_ROWS+row);if(index>=0)selected=index;return 1;}if(my>=win->len_y-42){if(mx>=12&&mx<=97&&page>0)page--;else if(mx>=105&&mx<=175&&visible_index((page+1)*ORGANIZER_ROWS)>=0)page++;else if(selected>=0&&mx>=250&&mx<=340){Uint8 b[2]={LOOK_AT_INVENTORY_ITEM,items[selected].slot};my_tcp_send(b,2);}else if(selected>=0&&mx>=348&&mx<=428){Uint8 b[2]={USE_INVENTORY_ITEM,items[selected].slot};my_tcp_send(b,2);refresh();}else if(selected>=0&&mx>=436&&mx<=556)display_popup_win(&drop_popup,"Quantity to drop");else if(selected>=0&&mx>=564&&mx<=674){char q[24];safe_snprintf(q,sizeof(q),"%u",items[selected].quantity);drop_quantity(q,NULL);}return 1;}return 1;}
static int close_handler(window_info *win){(void)win;organizer_win=-1;return 1;}
void display_inventory_organizer(void){if(organizer_win<0){organizer_win=create_window("Inventory Organizer",game_root_win,0,80,55,760,500,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(organizer_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(organizer_win,ELW_HANDLER_CLICK,&click_handler);set_window_handler(organizer_win,ELW_HANDLER_CLOSE,&close_handler);init_ipu(&search_popup,organizer_win,63,1,28,NULL,set_search);init_ipu(&drop_popup,organizer_win,10,1,12,NULL,drop_quantity);}else show_window(organizer_win);}
void close_inventory_organizer(void){if(organizer_win>=0)destroy_window(organizer_win);organizer_win=-1;}
void inventory_organizer_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;int i,count;if(len<14)return;gold=read_u32(&p);carried=read_u32(&p);capacity=read_u32(&p);count=read_u16(&p);item_count=0;selected=-1;for(i=0;i<count&&i<ORGANIZER_MAX_ITEMS;i++){organizer_item *e=&items[item_count];if(end-p<12)break;e->slot=*p++;e->image_id=read_u16(&p);e->quantity=read_u32(&p);e->emu=read_u32(&p);e->flags=*p++;if(!read_text(&p,end,e->name,sizeof(e->name))||!read_text(&p,end,e->category,sizeof(e->category)))break;item_count++;}for(i=1;i<item_count;i++){organizer_item key=items[i];int j=i-1;while(j>=0&&strcmp(items[j].name,key.name)>0){items[j+1]=items[j];j--;}items[j+1]=key;}page=0;display_inventory_organizer();}
