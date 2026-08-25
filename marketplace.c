#include <stdio.h>
#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
#include "asc.h"
#define draw_string_small(x, y, text, max_lines) draw_string_small_zoomed((x), (y), (text), (max_lines), 1.0f)
#include "gamewin.h"
#include "marketplace.h"
#include "multiplayer.h"
#include "notepad.h"

#define MARKET_MAX_LISTINGS 20

typedef struct
{
	Uint32 id, quantity, unit_price, seconds_left;
	Uint16 image_id;
	char item[64], seller[24];
} marketplace_listing;

static marketplace_listing listings[MARKET_MAX_LISTINGS];
static int marketplace_win = -1, listing_count = 0;
static int selected_listing = -1, market_view = 0;
static Uint32 pending_gold = 0, pending_returns = 0;
static INPUT_POPUP listing_popup;

static Uint32 read_u32(const Uint8 **p)
{
	Uint32 value;
	memcpy(&value, *p, 4); *p += 4;
	return SDL_SwapLE32(value);
}

static Uint16 read_u16(const Uint8 **p)
{
	Uint16 value;
	memcpy(&value, *p, 2); *p += 2;
	return SDL_SwapLE16(value);
}

static int read_text(const Uint8 **p, const Uint8 *end, char *out, size_t size)
{
	const Uint8 *zero = memchr(*p, 0, end - *p);
	size_t length;
	if (!zero) return 0;
	length = zero - *p;
	if (length >= size) length = size - 1;
	memcpy(out, *p, length); out[length] = 0; *p = zero + 1;
	return 1;
}

static void send_command(const char *command)
{
	Uint8 buffer[160];
	size_t length = strlen(command);
	if (length + 1 >= sizeof(buffer)) return;
	buffer[0] = RAW_TEXT;
	memcpy(buffer + 1, command, length + 1);
	my_tcp_send(buffer, length + 1);
}

static void submit_listing(const char *text, void *data)
{
	int slot, quantity, price;
	char command[96];
	(void)data;
	if (sscanf(text, "%d %d %d", &slot, &quantity, &price) != 3 ||
		slot < 0 || slot > 35 || quantity < 1 || price < 1) return;
	safe_snprintf(command, sizeof(command), "#auction sell %d %d %d", slot, quantity, price);
	send_command(command);
}

static void panel(int x, int y, int width, int height, float r, float g, float b, float alpha)
{
	glDisable(GL_TEXTURE_2D);
	glColor4f(r, g, b, alpha);
	glBegin(GL_QUADS);
	glVertex2i(x, y); glVertex2i(x + width, y);
	glVertex2i(x + width, y + height); glVertex2i(x, y + height);
	glEnd(); glEnable(GL_TEXTURE_2D);
}

static void button(int x, int y, int width, const char *label, int active)
{
	panel(x, y, width, 26, active ? .16f : .075f, active ? .39f : .19f,
		active ? .43f : .22f, .96f);
	glDisable(GL_TEXTURE_2D); glColor4f(active ? .39f : .23f, active ? .76f : .49f,
		active ? .78f : .52f, .95f);
	glBegin(GL_LINE_LOOP);
	glVertex2i(x, y); glVertex2i(x + width, y); glVertex2i(x + width, y + 26); glVertex2i(x, y + 26);
	glEnd(); glEnable(GL_TEXTURE_2D);
	glColor3f(.95f, .91f, .78f);
	draw_string_small(x + 8, y + 6, (const unsigned char *)label, 1);
}

static int display_handler(window_info *win)
{
	int i;
	char text[256];
	panel(6, 5, win->len_x - 12, win->len_y - 10, .025f, .055f, .064f, .78f);
	panel(8, 7, win->len_x - 16, 38, .055f, .15f, .17f, .94f);
	glColor3f(.92f, .78f, .43f);
	draw_string_small(16, 16, (const unsigned char *)"NYMARA EXCHANGE", 1);
	button(168, 11, 92, "Browse", market_view == 0);
	button(268, 11, 112, "My Listings", market_view == 1);
	button(388, 11, 86, "Refresh", 0);
	button(482, 11, 98, "Collect", 0);
	button(588, 11, 104, "List Item", 0);
	glColor3f(.72f, .88f, .85f);
	safe_snprintf(text, sizeof(text), "Escrow %u gc / %u items", pending_gold, pending_returns);
	draw_string_small(704, 17, (const unsigned char *)text, 1);
	panel(9, 52, win->len_x - 18, 25, .10f, .18f, .19f, .96f);
	glColor3f(.67f, .82f, .78f);
	draw_string_small(18, 59, (const unsigned char *)"ID", 1);
	draw_string_small(74, 59, (const unsigned char *)"Item", 1);
	draw_string_small(334, 59, (const unsigned char *)"Quantity", 1);
	draw_string_small(424, 59, (const unsigned char *)"Unit price", 1);
	draw_string_small(519, 59, (const unsigned char *)"Seller / Remaining", 1);
	for (i = 0; i < listing_count; i++)
	{
		int y = 83 + i * 22;
		panel(10, y - 3, win->len_x - 20, 21,
			(i & 1) ? .045f : .065f, (i & 1) ? .085f : .12f, (i & 1) ? .095f : .13f, .88f);
		if (i == selected_listing)
		{
			panel(10, y - 3, win->len_x - 20, 21, .16f, .38f, .40f, .92f);
		}
		glColor3f(.93f, .91f, .82f);
		safe_snprintf(text, sizeof(text), "#%u", listings[i].id);
		draw_string_small(14, y, (const unsigned char *)text, 1);
		draw_string_small(70, y, (const unsigned char *)listings[i].item, 1);
		safe_snprintf(text, sizeof(text), "%u", listings[i].quantity);
		draw_string_small(330, y, (const unsigned char *)text, 1);
		safe_snprintf(text, sizeof(text), "%u gc", listings[i].unit_price);
		draw_string_small(420, y, (const unsigned char *)text, 1);
		safe_snprintf(text, sizeof(text), "%s / %ud", listings[i].seller,
			(listings[i].seconds_left + 86399) / 86400);
		draw_string_small(515, y, (const unsigned char *)text, 1);
	}
	if (!listing_count)
	{
		glColor3f(.53f, .66f, .64f);
		draw_string_small(24, 96, (const unsigned char *)"No listings in this view. Refresh or list an inventory item.", 1);
	}
	panel(9, win->len_y - 48, win->len_x - 18, 39, .055f, .13f, .145f, .96f);
	if (selected_listing >= 0)
	{
		if (market_view) {
			button(12, win->len_y - 38, 170, "Renew for 365 days", 1);
			button(190, win->len_y - 38, 145, "Cancel listing", 0);
		} else {
			button(12, win->len_y - 38, 100, "Buy one", 1);
			button(120, win->len_y - 38, 110, "Buy all", 0);
		}
	}
	return 1;
}

static int click_handler(window_info *win, int mx, int my, Uint32 flags)
{
	char command[96];
	int row;
	(void)flags;
	if (my >= 10 && my <= 37)
	{
		if (mx >= 168 && mx <= 260) send_command("#auction ui browse");
		else if (mx >= 268 && mx <= 380) send_command("#auction ui mine");
		else if (mx >= 388 && mx <= 474) send_command(market_view ? "#auction ui mine" : "#auction ui browse");
		else if (mx >= 482 && mx <= 580) send_command("#auction collect");
		else if (mx >= 588 && mx <= 692)
			display_popup_win(&listing_popup, "Inventory slot, quantity, unit price");
		return 1;
	}
	row = (my - 80) / 22;
	if (my >= 80 && row >= 0 && row < listing_count) {
		selected_listing = row; return 1;
	}
	if (selected_listing >= 0 && my >= win->len_y - 42)
	{
		if (market_view && mx >= 12 && mx <= 182)
			safe_snprintf(command, sizeof(command), "#auction renew %u", listings[selected_listing].id);
		else if (market_view && mx >= 190 && mx <= 335)
			safe_snprintf(command, sizeof(command), "#auction cancel %u", listings[selected_listing].id);
		else if (!market_view && mx >= 12 && mx <= 112)
			safe_snprintf(command, sizeof(command), "#auction buy %u 1", listings[selected_listing].id);
		else if (!market_view && mx >= 120 && mx <= 230)
			safe_snprintf(command, sizeof(command), "#auction buy %u all", listings[selected_listing].id);
		else return 1;
		send_command(command);
	}
	return 1;
}

static int close_handler(window_info *win)
{
	(void)win; marketplace_win = -1; return 1;
}

void display_marketplace(void)
{
	if (marketplace_win < 0)
	{
		marketplace_win = create_window("Nymara Exchange", game_root_win, 0,
			80, 60, 840, 520, ELW_USE_UISCALE | ELW_WIN_DEFAULT);
		set_window_handler(marketplace_win, ELW_HANDLER_DISPLAY, &display_handler);
		set_window_handler(marketplace_win, ELW_HANDLER_CLICK, &click_handler);
		set_window_handler(marketplace_win, ELW_HANDLER_CLOSE, &close_handler);
		init_ipu(&listing_popup, marketplace_win, 64, 1, 28, NULL, submit_listing);
	}
	else show_window(marketplace_win);
}

void close_marketplace(void)
{
	if (marketplace_win >= 0) destroy_window(marketplace_win);
	marketplace_win = -1;
}

void marketplace_update(const Uint8 *data, int length)
{
	const Uint8 *p = data, *end = data + length;
	int i, count;
	if (length < 11) return;
	market_view = *p++;
	pending_gold = read_u32(&p);
	pending_returns = read_u32(&p);
	count = read_u16(&p);
	listing_count = 0; selected_listing = -1;
	for (i = 0; i < count && i < MARKET_MAX_LISTINGS; i++)
	{
		marketplace_listing *entry = &listings[listing_count];
		if (end - p < 18) break;
		entry->id = read_u32(&p);
		entry->quantity = read_u32(&p);
		entry->unit_price = read_u32(&p);
		entry->seconds_left = read_u32(&p);
		entry->image_id = read_u16(&p);
		if (!read_text(&p, end, entry->item, sizeof(entry->item)) ||
			!read_text(&p, end, entry->seller, sizeof(entry->seller))) break;
		listing_count++;
	}
	display_marketplace();
}
