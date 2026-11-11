#include "smartspend.h"
#include <stdlib.h>
#include <stdint.h>

struct SS_Stack { int64_t *data; int64_t size; int64_t capacity; };
SS_Stack *ss_stack_create(void) { return (SS_Stack *)calloc(1, sizeof(SS_Stack)); }
void ss_stack_free(SS_Stack *stack) { if (stack) { free(stack->data); free(stack); } }
void ss_stack_clear(SS_Stack *stack) { if (stack) stack->size = 0; }
int32_t ss_stack_push(SS_Stack *stack, int64_t value) {
    if (!stack) return -1;
    if (stack->size == stack->capacity) {
        if (stack->capacity > INT64_MAX / 2 / (int64_t)sizeof(int64_t)) return -2;
        int64_t capacity = stack->capacity ? stack->capacity * 2 : 16;
        int64_t *data = (int64_t *)realloc(stack->data, (size_t)capacity * sizeof(int64_t));
        if (!data) return -2;
        stack->data = data; stack->capacity = capacity;
    }
    stack->data[stack->size++] = value;
    return 0;
}
int32_t ss_stack_peek(SS_Stack *stack, int64_t *out) {
    if (!stack || !out) return -1;
    if (!stack->size) return 1;
    *out = stack->data[stack->size - 1];
    return 0;
}
int32_t ss_stack_pop(SS_Stack *stack, int64_t *out) {
    int32_t result = ss_stack_peek(stack, out);
    if (!result) stack->size--;
    return result;
}
