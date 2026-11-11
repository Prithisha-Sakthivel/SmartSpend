#include "smartspend.h"
#include <assert.h>
#include <stdio.h>
int main(void){
 SS_List*l=ss_list_create();assert(l);SS_Transaction a={2,200,0,0},b={1,500,1,1},o;
 assert(ss_list_append(l,&a)==0&&ss_list_append(l,&b)==0);assert(ss_list_count(l)==2);assert(ss_list_find(l,1,&o)==0&&o.amount_paise==500);assert(ss_list_remove(l,2)==0);ss_list_free(l);
 SS_Stack*s=ss_stack_create();int64_t v;assert(ss_stack_push(s,7)==0&&ss_stack_push(s,9)==0);assert(ss_stack_peek(s,&v)==0&&v==9);assert(ss_stack_pop(s,&v)==0&&v==9);ss_stack_free(s);
 SS_Queue*q=ss_queue_create();assert(ss_queue_enqueue(q,4)==0&&ss_queue_enqueue(q,5)==0);assert(ss_queue_dequeue(q,&v)==0&&v==4);ss_queue_free(q);
 SS_Transaction x[3]={{1,200,0,0},{2,500,0,0},{3,500,0,0}};ss_quick_sort(x,3);assert(x[0].id==2&&x[1].id==3&&x[2].id==1);SS_Transaction sorted[3]={{1,0,0,0},{2,0,0,0},{3,0,0,0}};assert(ss_binary_search_id(sorted,3,2)==1&&ss_binary_search_id(sorted,3,8)==-1);
 int32_t ix[3]={0,1,0};int64_t am[3]={10,20,30},tot[2];assert(ss_category_totals(ix,am,3,tot,2)==0&&tot[0]==40&&tot[1]==20);
 puts("C tests passed");return 0;
}
