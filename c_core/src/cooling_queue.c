#include "smartspend.h"
#include <stdlib.h>
#include <stdint.h>

struct SS_Queue { int64_t *data; int64_t size; int64_t capacity; int64_t front; };
SS_Queue *ss_queue_create(void) { return (SS_Queue *)calloc(1, sizeof(SS_Queue)); }
void ss_queue_free(SS_Queue *queue) { if (queue) { free(queue->data); free(queue); } }
static int32_t grow(SS_Queue *queue) {
    if (queue->capacity > INT64_MAX / 2 / (int64_t)sizeof(int64_t)) return -2;
    int64_t capacity = queue->capacity ? queue->capacity * 2 : 16;
    int64_t *data = (int64_t *)malloc((size_t)capacity * sizeof(int64_t));
    if (!data) return -2;
    for (int64_t i = 0; i < queue->size; i++)
        data[i] = queue->data[(queue->front + i) % queue->capacity];
    free(queue->data); queue->data = data; queue->capacity = capacity; queue->front = 0;
    return 0;
}
int32_t ss_queue_enqueue(SS_Queue *queue, int64_t value) {
    if (!queue) return -1;
    if (queue->size == queue->capacity) { int32_t result = grow(queue); if (result) return result; }
    queue->data[(queue->front + queue->size) % queue->capacity] = value;
    queue->size++;
    return 0;
}
int32_t ss_queue_peek(SS_Queue *queue, int64_t *out) {
    if (!queue || !out) return -1;
    if (!queue->size) return 1;
    *out = queue->data[queue->front];
    return 0;
}
int32_t ss_queue_dequeue(SS_Queue *queue, int64_t *out) {
    int32_t result = ss_queue_peek(queue, out);
    if (!result) { queue->front = (queue->front + 1) % queue->capacity; queue->size--; }
    return result;
}
