#include "smartspend.h"

/* Sort expense rows by descending paise; ties use ascending stable transaction ID. */
static int comes_before(SS_Transaction left, SS_Transaction right) {
    return left.amount_paise > right.amount_paise ||
           (left.amount_paise == right.amount_paise && left.id < right.id);
}
static void swap_rows(SS_Transaction *left, SS_Transaction *right) {
    SS_Transaction temporary = *left; *left = *right; *right = temporary;
}
static void quick_sort_range(SS_Transaction *items, int64_t low, int64_t high) {
    if (low >= high) return;
    SS_Transaction pivot = items[low + (high - low) / 2];
    int64_t left = low, right = high;
    while (left <= right) {
        while (comes_before(items[left], pivot)) left++;
        while (comes_before(pivot, items[right])) right--;
        if (left <= right) { swap_rows(&items[left], &items[right]); left++; right--; }
    }
    if (low < right) quick_sort_range(items, low, right);
    if (left < high) quick_sort_range(items, left, high);
}
void ss_quick_sort(SS_Transaction *items, int64_t count) {
    if (items && count > 1) quick_sort_range(items, 0, count - 1);
}
int64_t ss_binary_search_id(const SS_Transaction *items, int64_t count, int64_t id) {
    if (!items || count < 0) return -1;
    int64_t low = 0, high = count - 1;
    while (low <= high) {
        int64_t middle = low + (high - low) / 2;
        if (items[middle].id == id) return middle;
        if (items[middle].id < id) low = middle + 1; else high = middle - 1;
    }
    return -1;
}
