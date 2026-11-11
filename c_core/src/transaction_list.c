#include "smartspend.h"
#include <stdlib.h>

typedef struct Node { SS_Transaction value; struct Node *next; } Node;
struct SS_List { Node *head; Node *tail; int64_t count; };

SS_List *ss_list_create(void) { return (SS_List *)calloc(1, sizeof(SS_List)); }
void ss_list_free(SS_List *list) {
    if (!list) return;
    Node *node = list->head;
    while (node) { Node *next = node->next; free(node); node = next; }
    free(list);
}
int32_t ss_list_append(SS_List *list, const SS_Transaction *value) {
    if (!list || !value) return -1;
    Node *node = (Node *)malloc(sizeof(Node));
    if (!node) return -2;
    node->value = *value; node->next = NULL;
    if (list->tail) list->tail->next = node; else list->head = node;
    list->tail = node; list->count++;
    return 0;
}
int32_t ss_list_remove(SS_List *list, int64_t id) {
    if (!list) return -1;
    Node *previous = NULL, *node = list->head;
    while (node && node->value.id != id) { previous = node; node = node->next; }
    if (!node) return 1;
    if (previous) previous->next = node->next; else list->head = node->next;
    if (list->tail == node) list->tail = previous;
    free(node); list->count--;
    return 0;
}
int32_t ss_list_find(SS_List *list, int64_t id, SS_Transaction *out) {
    if (!list || !out) return -1;
    for (Node *node = list->head; node; node = node->next)
        if (node->value.id == id) { *out = node->value; return 0; }
    return 1;
}
int64_t ss_list_count(SS_List *list) { return list ? list->count : -1; }
int32_t ss_list_get(SS_List *list, int64_t index, SS_Transaction *out) {
    if (!list || !out || index < 0) return -1;
    Node *node = list->head;
    while (node && index--) node = node->next;
    if (!node) return 1;
    *out = node->value;
    return 0;
}
