#ifndef ELORIA_QUEST_JOURNAL_H
#define ELORIA_QUEST_JOURNAL_H
#include "platform.h"
void quest_journal_update(const Uint8 *data, int len);
void display_quest_journal(void);
void close_quest_journal(void);
#endif
