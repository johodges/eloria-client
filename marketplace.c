#include <stdio.h>
#include <string.h>
#include <SDL.h>
#include <SDL_endian.h>
#include "client_serv.h"
#include "elwindows.h"
#include "font.h"
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

static void button(int x, int y, int width, const char *label, int active)
{
	glDisable(GL_TEXTURE_2D);
	glColor4f(active ? .24f : .12f, active ? .43f : .25f, active ? .48f : .28f, .90f);
	glBegin(GL_QUADS);
	glVertex2i(x, y); glVertex2i(x + width, y);
	glVertex2i(x + width, y + 24); glVertex2i(x, y + 24);
	glEnd(); glEnable(GL_TEXTURE_2D);
	glColor3f(.95f, .91f, .78f);
	draw_string_small(x + 8, y + 5, (const unsigned char *)label, 1);
}

static int display_handler(window_info *win)
{
	int i;
	char text[256];
	button(12, 10, 100, "Browse", market_view == 0);
	button(120, 10, 110, "My Listings", market_view == 1);
	button(238, 10, 90, "Refresh", 0);
	button(336, 10, 105, "Collect", 0);
	button(449, 10, 105, "List Item", 0);
	glColor3f(.82f, .86f, .82f);
	safe_snprintf(text, sizeof(text), "Escrow %u gc / %u items", pending_gold, pending_returns);
	draw_string_small(570, 16, (const unsigned char *)text, 1);
	glColor3f(.65f, .75f, .72f);
	draw_string_small(14, 48, (const unsigned char *)"ID", 1);
	draw_string_small(70, 48, (const unsigned char *)"Item", 1);
	draw_string_small(330, 48, (const unsigned char *)"Quantity", 1);
	draw_string_small(420, 48, (const unsigned char *)"Price", 1);
	draw_string_small(515, 48, (const unsigned char *)"Seller / Remaining", 1);
	for (i = 0; i < listing_count; i++)
	{
		int y = 70 + i * 20;
		if (i == selected_listing)
		{
			glDisable(GL_TEXTURE_2D); glColor4f(.20f, .38f, .42f, .85f);
			glBegin(GL_QUADS);
			glVertex2i(10, y - 2); glVertex2i(win->len_x - 10, y - 2);
			glVertex2i(win->len_x - 10, y + 17); glVertex2i(10, y + 17);
			glEnd(); glEnable(GL_TEXTURE_2D);
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
	if (my >= 10 && my <= 34)
	{
		if (mx >= 12 && mx <= 112) send_command("#auction ui browse");
		else if (mx >= 120 && mx <= 230) send_command("#auction ui mine");
		else if (mx >= 238 && mx <= 328) send_command(market_view ? "#auction ui mine" : "#auction ui browse");
		else if (mx >= 336 && mx <= 441) send_command("#auction collect");
		else if (mx >= 449 && mx <= 554)
			display_popup_win(&listing_popup, "Inventory slot, quantity, unit price");
		return 1;
	}
	row = (my - 68) / 20;
	if (my >= 68 && row >= 0 && row < listing_count) {
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
