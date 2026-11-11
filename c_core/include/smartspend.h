#ifndef SMARTSPEND_H
#define SMARTSPEND_H
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#ifdef SMARTSPEND_BUILD
#define SS_API __declspec(dllexport)
#else
#define SS_API __declspec(dllimport)
#endif
typedef struct { int64_t id; int64_t amount_paise; int32_t type; int32_t category_index; } SS_Transaction;
typedef struct SS_List SS_List;
typedef struct SS_Stack SS_Stack;
typedef struct SS_Queue SS_Queue;
SS_API SS_List *ss_list_create(void); SS_API void ss_list_free(SS_List *);
SS_API int32_t ss_list_append(SS_List *, const SS_Transaction *); SS_API int32_t ss_list_remove(SS_List *, int64_t);
SS_API int32_t ss_list_find(SS_List *, int64_t, SS_Transaction *); SS_API int64_t ss_list_count(SS_List *);
SS_API int32_t ss_list_get(SS_List *, int64_t, SS_Transaction *);
SS_API SS_Stack *ss_stack_create(void); SS_API void ss_stack_free(SS_Stack *);
SS_API int32_t ss_stack_push(SS_Stack *, int64_t); SS_API int32_t ss_stack_peek(SS_Stack *, int64_t *);
SS_API int32_t ss_stack_pop(SS_Stack *, int64_t *); SS_API void ss_stack_clear(SS_Stack *);
SS_API SS_Queue *ss_queue_create(void); SS_API void ss_queue_free(SS_Queue *);
SS_API int32_t ss_queue_enqueue(SS_Queue *, int64_t); SS_API int32_t ss_queue_peek(SS_Queue *, int64_t *);
SS_API int32_t ss_queue_dequeue(SS_Queue *, int64_t *);
SS_API int32_t ss_category_totals(const int32_t *, const int64_t *, int64_t, int64_t *, int64_t);
SS_API void ss_quick_sort(SS_Transaction *, int64_t);
SS_API int64_t ss_binary_search_id(const SS_Transaction *, int64_t, int64_t);
#ifdef __cplusplus
}
#endif
#endif
