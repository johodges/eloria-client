#include <string.h>
#include <SDL.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
#include "asc.h"
#define draw_string_small(x, y, text, max_lines) draw_string_small_zoomed((x), (y), (text), (max_lines), 1.0f)
#include "gamewin.h"
#include "multiplayer.h"
#include "tutorial_window.h"

#define TUTORIAL_MAX_OPTIONS 6
typedef struct { char label[64], command[128]; } tutorial_option;
static tutorial_option options[TUTORIAL_MAX_OPTIONS];
static char page_title[80], page_progress[80], page_body[3001];
static int tutorial_win=-1, option_count=0;

static int read_text(const Uint8 **p,const Uint8 *end,char *out,size_t size)
{
	const Uint8 *z=memchr(*p,0,end-*p); size_t n;
	if(!z)return 0; n=z-*p; if(n>=size)n=size-1;
	memcpy(out,*p,n); out[n]=0; *p=z+1; return 1;
}
static void send_command(const char *command)
{
	Uint8 buffer[160]; size_t length=strlen(command);
	if(length+1>=sizeof(buffer))return;
	buffer[0]=RAW_TEXT; memcpy(buffer+1,command,length+1);
	my_tcp_send(buffer,length+1);
}
static void draw_button(int x,int y,int width,const char *label)
{
	glDisable(GL_TEXTURE_2D); glColor4f(.20f,.38f,.42f,.92f);
	glBegin(GL_QUADS); glVertex2i(x,y); glVertex2i(x+width,y);
	glVertex2i(x+width,y+28); glVertex2i(x,y+28); glEnd();
	glEnable(GL_TEXTURE_2D); glColor3f(.96f,.91f,.76f);
	draw_string_small(x+9,y+7,(const unsigned char*)label,1);
}
static int display_handler(window_info *win)
{
	int i; (void)win;
	glColor3f(.91f,.69f,.28f);
	draw_string_zoomed(18,16,(const unsigned char*)page_title,1,1.15f);
	glColor3f(.60f,.80f,.76f);
	draw_string_small(18,48,(const unsigned char*)page_progress,1);
	glColor3f(.93f,.91f,.82f);
	draw_string_zoomed(18,82,(const unsigned char*)page_body,18,0.82f);
	for(i=0;i<option_count;i++)
		draw_button(18+(i%3)*250,468+(i/3)*36,230,options[i].label);
	return 1;
}
static int click_handler(window_info *win,int mx,int my,Uint32 flags)
{
	int column,row,index; (void)win; (void)flags;
	if(my<468)return 0;
	column=(mx-18)/250; row=(my-468)/36;
	if(column<0||column>2||row<0||row>1)return 0;
	index=row*3+column;
	if(index<option_count && mx>=18+column*250 && mx<=248+column*250 &&
	   my<=496+row*36) send_command(options[index].command);
	return 1;
}
static int close_handler(window_info *win){(void)win;tutorial_win=-1;return 1;}
void display_tutorial_window(void)
{
	if(tutorial_win<0){
		tutorial_win=create_window("Eloria Tutorial",game_root_win,0,75,45,780,550,
			ELW_USE_UISCALE|ELW_WIN_DEFAULT);
		set_window_handler(tutorial_win,ELW_HANDLER_DISPLAY,&display_handler);
		set_window_handler(tutorial_win,ELW_HANDLER_CLICK,&click_handler);
		set_window_handler(tutorial_win,ELW_HANDLER_CLOSE,&close_handler);
	}else show_window(tutorial_win);
}
void close_tutorial_window(void)
{
	if(tutorial_win>=0)destroy_window(tutorial_win); tutorial_win=-1;
}
void tutorial_window_update(const Uint8 *data,int len)
{
	const Uint8 *p=data,*end=data+len; int i,count;
	if(len<2)return; count=*p++; option_count=0;
	if(!read_text(&p,end,page_title,sizeof(page_title))||
	   !read_text(&p,end,page_progress,sizeof(page_progress))||
	   !read_text(&p,end,page_body,sizeof(page_body)))return;
	for(i=0;i<count&&i<TUTORIAL_MAX_OPTIONS;i++){
		if(!read_text(&p,end,options[i].label,sizeof(options[i].label))||
		   !read_text(&p,end,options[i].command,sizeof(options[i].command)))break;
		option_count++;
	}
	display_tutorial_window();
}
