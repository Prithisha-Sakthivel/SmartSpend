#include "smartspend.h"
#include <stdint.h>

int32_t ss_category_totals(const int32_t *indexes, const int64_t *amounts,
                           int64_t item_count, int64_t *totals, int64_t category_count) {
    if ((item_count > 0 && (!indexes || !amounts)) || !totals || item_count < 0 || category_count < 0) return -1;
    for (int64_t i = 0; i < category_count; i++) totals[i] = 0;
    for (int64_t i = 0; i < item_count; i++) {
        int32_t category = indexes[i];
        if (category < 0 || category >= category_count || amounts[i] < 0 || totals[category] > INT64_MAX - amounts[i]) return -2;
        totals[category] += amounts[i];
    }
    return 0;
}
