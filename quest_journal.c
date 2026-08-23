#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "elwindows.h"
#include "font.h"
#include "asc.h"
#define draw_string_small(x, y, text, max_lines) draw_string_small_zoomed((x), (y), (text), (max_lines), 1.0f)
#include "gamewin.h"
#include "client_serv.h"
#include "multiplayer.h"
#include "quest_journal.h"

#define QUEST_MAX_ENTRIES 15
typedef struct { Uint8 ready; Uint32 current,target; char title[80],objective[256],location[80]; } quest_entry;
static quest_entry entries[QUEST_MAX_ENTRIES];
static int journal_win=-1,entry_count=0,selected=0;
static void refresh_journal(void){Uint8 b[]={RAW_TEXT,'#','q','u','e','s','t','s'};my_tcp_send(b,sizeof(b));}
static Uint32 read_u32(const Uint8 **p){Uint32 v;memcpy(&v,*p,4);*p+=4;return SDL_SwapLE32(v);}
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static int display_handler(window_info *win){int i;char s[192];(void)win;glColor3f(.65f,.75f,.72f);draw_string_small(14,14,(const unsigned char*)"Active Quest",1);draw_string_small(470,14,(const unsigned char*)"Progress",1);for(i=0;i<entry_count;i++){int y=38+i*22;if(i==selected){glDisable(GL_TEXTURE_2D);glColor4f(.20f,.38f,.42f,.85f);glBegin(GL_QUADS);glVertex2i(10,y-3);glVertex2i(780,y-3);glVertex2i(780,y+17);glVertex2i(10,y+17);glEnd();glEnable(GL_TEXTURE_2D);}glColor3f(entries[i].ready?.50f:.93f,entries[i].ready?.92f:.91f,entries[i].ready?.55f:.82f);draw_string_small(14,y,(const unsigned char*)entries[i].title,1);safe_snprintf(s,sizeof(s),entries[i].ready?"Ready to turn in":"%u / %u",entries[i].current,entries[i].target);draw_string_small(470,y,(const unsigned char*)s,1);}if(entry_count==0){glColor3f(.82f,.86f,.82f);draw_string_small(14,46,(const unsigned char*)"No active quests.",1);}else{quest_entry *e=&entries[selected];int y=398;glColor3f(.65f,.75f,.72f);draw_string_small(14,y,(const unsigned char*)"Objective",1);glColor3f(.93f,.91f,.82f);draw_string_zoomed(14,y+22,(const unsigned char*)e->objective,2,0.8f);safe_snprintf(s,sizeof(s),"Location: %s",e->location[0]?e->location:"Unknown");glColor3f(.72f,.82f,.78f);draw_string_small(14,478,(const unsigned char*)s,1);}return 1;}
static int click_handler(window_info *win,int mx,int my,Uint32 flags){int row=(my-35)/22;(void)win;(void)flags;if(my<32&&mx>=690){refresh_journal();return 1;}if(my>=35&&row>=0&&row<entry_count)selected=row;return 1;}
static int close_handler(window_info *win){(void)win;journal_win=-1;return 1;}
void display_quest_journal(void){if(journal_win<0){journal_win=create_window("Quest Journal - Refresh",game_root_win,0,90,55,800,510,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(journal_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(journal_win,ELW_HANDLER_CLICK,&click_handler);set_window_handler(journal_win,ELW_HANDLER_CLOSE,&close_handler);}else show_window(journal_win);}
void close_quest_journal(void){if(journal_win>=0)destroy_window(journal_win);journal_win=-1;}
void quest_journal_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;int i,count;if(len<2)return;count=read_u16(&p);entry_count=0;selected=0;for(i=0;i<count&&i<QUEST_MAX_ENTRIES;i++){quest_entry *e=&entries[entry_count];if(end-p<9)break;e->ready=*p++;e->current=read_u32(&p);e->target=read_u32(&p);if(!read_text(&p,end,e->title,sizeof(e->title))||!read_text(&p,end,e->objective,sizeof(e->objective))||!read_text(&p,end,e->location,sizeof(e->location)))break;entry_count++;}display_quest_journal();}
