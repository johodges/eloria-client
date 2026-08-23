#include <string.h>
#include <SDL.h>
#include "elwindows.h"
#include "font.h"
#include "asc.h"
#define draw_string_small(x, y, text, max_lines) draw_string_small_zoomed((x), (y), (text), (max_lines), 1.0f)
#include "gamewin.h"
#include "special_event_window.h"

#define EVENT_LINE_COUNT 10
#define EVENT_LINE_LENGTH 160
static int event_win = -1;
static int event_line_count = 0;
static char event_lines[EVENT_LINE_COUNT][EVENT_LINE_LENGTH];

static int event_display_handler(window_info *win)
{
	int i;
	(void)win;
	for (i = 0; i < event_line_count; ++i)
	{
		if (i == 0) glColor3f(0.96f, 0.72f, 0.30f);
		else if (i == 1) glColor3f(0.54f, 0.86f, 0.86f);
		else glColor3f(0.86f, 0.88f, 0.82f);
		draw_string_small(12, 12 + i * 22,
			(const unsigned char *)event_lines[i], 1);
	}
	return 1;
}

static int event_close_handler(window_info *win)
{
	(void)win;
	event_win = -1;
	return 1;
}

void display_special_event_window(void)
{
	if (event_win < 0)
	{
		event_win = create_window("Special Event", game_root_win, 0, 20, 90,
			430, 250, ELW_USE_UISCALE | ELW_WIN_DEFAULT);
		set_window_handler(event_win, ELW_HANDLER_DISPLAY, &event_display_handler);
		set_window_handler(event_win, ELW_HANDLER_CLOSE, &event_close_handler);
	}
	else show_window(event_win);
}

void close_special_event_window(void)
{
	if (event_win >= 0) destroy_window(event_win);
	event_win = -1;
}

void special_event_window_update(const Uint8 *data, int len)
{
	const Uint8 *p = data, *end = data + len;
	event_line_count = 0;
	while (p < end && event_line_count < EVENT_LINE_COUNT)
	{
		const Uint8 *zero = memchr(p, 0, end - p);
		size_t count;
		if (!zero) break;
		count = zero - p;
		if (count >= EVENT_LINE_LENGTH) count = EVENT_LINE_LENGTH - 1;
		memcpy(event_lines[event_line_count], p, count);
		event_lines[event_line_count][count] = 0;
		++event_line_count;
		p = zero + 1;
	}
	if (event_line_count) display_special_event_window();
}
