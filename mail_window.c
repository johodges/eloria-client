#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
#include "gamewin.h"
#include "mail_window.h"
#include "multiplayer.h"
#include "notepad.h"

#define MAIL_MAX_MESSAGES 12
typedef struct { Uint32 id,created_at; Uint8 read; char sender[32],subject[80],body[1001]; } mail_message;
static mail_message messages[MAIL_MAX_MESSAGES];
static int mail_win=-1,message_count=0,selected=-1;
static INPUT_POPUP compose_popup;
static Uint32 read_u32(const Uint8 **p){Uint32 v;memcpy(&v,*p,4);*p+=4;return SDL_SwapLE32(v);}
static Uint16 read_u16(const Uint8 **p){Uint16 v;memcpy(&v,*p,2);*p+=2;return SDL_SwapLE16(v);}
static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size){const Uint8 *z=memchr(*p,0,end-*p);size_t n;if(!z)return 0;n=z-*p;if(n>=size)n=size-1;memcpy(out,*p,n);out[n]=0;*p=z+1;return 1;}
static void send_raw(const char *cmd){Uint8 b[1200];size_t n=strlen(cmd);if(n+1>=sizeof(b))return;b[0]=RAW_TEXT;memcpy(b+1,cmd,n+1);my_tcp_send(b,n+1);}
static void compose_mail(const char *text,void *data){char cmd[1200];(void)data;if(!strchr(text,'|'))return;safe_snprintf(cmd,sizeof(cmd),"#mail send %s",text);send_raw(cmd);}
static void button(int x,int y,int w,const char *s,int active){glDisable(GL_TEXTURE_2D);glColor4f(active?.24f:.12f,active?.43f:.25f,active?.48f:.28f,.9f);glBegin(GL_QUADS);glVertex2i(x,y);glVertex2i(x+w,y);glVertex2i(x+w,y+24);glVertex2i(x,y+24);glEnd();glEnable(GL_TEXTURE_2D);glColor3f(.95f,.91f,.78f);draw_string_small(x+7,y+5,(const unsigned char*)s,1);}
static int display_handler(window_info *win){int i;char text[180];button(12,10,105,"Compose",1);button(125,10,90,"Refresh",0);glColor3f(.65f,.75f,.72f);draw_string_small(14,48,(const unsigned char*)"From",1);draw_string_small(180,48,(const unsigned char*)"Subject",1);for(i=0;i<message_count;i++){int y=70+i*22;if(i==selected){glDisable(GL_TEXTURE_2D);glColor4f(.20f,.38f,.42f,.85f);glBegin(GL_QUADS);glVertex2i(10,y-3);glVertex2i(win->len_x-10,y-3);glVertex2i(win->len_x-10,y+17);glVertex2i(10,y+17);glEnd();glEnable(GL_TEXTURE_2D);}glColor3f(messages[i].read?.72f:.98f,messages[i].read?.76f:.88f,messages[i].read?.72f:.48f);draw_string_small(14,y,(const unsigned char*)messages[i].sender,1);draw_string_small(180,y,(const unsigned char*)messages[i].subject,1);}if(selected>=0){mail_message *m=&messages[selected];glColor3f(.65f,.75f,.72f);safe_snprintf(text,sizeof(text),"Message #%u from %s",m->id,m->sender);draw_string_small(14,350,(const unsigned char*)text,1);glColor3f(.92f,.91f,.84f);draw_string_zoomed(14,376,(const unsigned char*)m->body,4,.82f);button(500,win->len_y-38,90,"Mark Read",1);button(598,win->len_y-38,85,"Delete",0);}else if(!message_count){glColor3f(.82f,.86f,.82f);draw_string_small(14,76,(const unsigned char*)"Your inbox is empty.",1);}return 1;}
static int click_handler(window_info *win,int mx,int my,Uint32 flags){char cmd[64];int row=(my-68)/22;(void)flags;if(my>=10&&my<=34){if(mx>=12&&mx<=117)display_popup_win(&compose_popup,"Recipient subject | message");else if(mx>=125&&mx<=215)send_raw("#mail inbox");return 1;}if(my>=68&&row>=0&&row<message_count){selected=row;if(!messages[row].read){safe_snprintf(cmd,sizeof(cmd),"#mail read %u",messages[row].id);send_raw(cmd);}return 1;}if(selected>=0&&my>=win->len_y-42){if(mx>=500&&mx<=590){safe_snprintf(cmd,sizeof(cmd),"#mail read %u",messages[selected].id);send_raw(cmd);}else if(mx>=598&&mx<=683){safe_snprintf(cmd,sizeof(cmd),"#mail delete %u",messages[selected].id);send_raw(cmd);}return 1;}return 1;}
static int close_handler(window_info *win){(void)win;mail_win=-1;return 1;}
void display_mail_window(void){if(mail_win<0){mail_win=create_window("Player Mail",game_root_win,0,90,55,720,520,ELW_USE_UISCALE|ELW_WIN_DEFAULT);set_window_handler(mail_win,ELW_HANDLER_DISPLAY,&display_handler);set_window_handler(mail_win,ELW_HANDLER_CLICK,&click_handler);set_window_handler(mail_win,ELW_HANDLER_CLOSE,&close_handler);init_ipu(&compose_popup,mail_win,1000,5,56,NULL,compose_mail);}else show_window(mail_win);}
void close_mail_window(void){if(mail_win>=0)destroy_window(mail_win);mail_win=-1;}
void mail_window_update(const Uint8 *data,int len){const Uint8 *p=data,*end=data+len;int i,count;if(len<2)return;count=read_u16(&p);message_count=0;selected=-1;for(i=0;i<count&&i<MAIL_MAX_MESSAGES;i++){mail_message *m=&messages[message_count];if(end-p<9)break;m->id=read_u32(&p);m->created_at=read_u32(&p);m->read=*p++;if(!read_text(&p,end,m->sender,sizeof(m->sender))||!read_text(&p,end,m->subject,sizeof(m->subject))||!read_text(&p,end,m->body,sizeof(m->body)))break;message_count++;}display_mail_window();}
