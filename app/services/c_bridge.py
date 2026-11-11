import ctypes
import os
from functools import lru_cache


class CTransaction(ctypes.Structure):
    _fields_ = [("id", ctypes.c_int64), ("amount_paise", ctypes.c_int64), ("type", ctypes.c_int32), ("category_index", ctypes.c_int32)]


@lru_cache(maxsize=1)
def library(path):
    if not os.path.isfile(path):
        return None
    dll = ctypes.CDLL(path)
    dll.ss_stack_create.restype = ctypes.c_void_p
    dll.ss_stack_free.argtypes = [ctypes.c_void_p]
    dll.ss_stack_push.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    dll.ss_stack_push.restype = ctypes.c_int32
    dll.ss_stack_peek.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
    dll.ss_stack_peek.restype = ctypes.c_int32
    dll.ss_stack_pop.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
    dll.ss_stack_pop.restype = ctypes.c_int32
    dll.ss_queue_create.restype = ctypes.c_void_p
    dll.ss_queue_free.argtypes = [ctypes.c_void_p]
    dll.ss_queue_enqueue.argtypes = [ctypes.c_void_p, ctypes.c_int64]
    dll.ss_queue_enqueue.restype = ctypes.c_int32
    dll.ss_queue_dequeue.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int64)]
    dll.ss_queue_dequeue.restype = ctypes.c_int32
    dll.ss_quick_sort.argtypes = [ctypes.POINTER(CTransaction), ctypes.c_int64]
    dll.ss_binary_search_id.argtypes = [ctypes.POINTER(CTransaction), ctypes.c_int64, ctypes.c_int64]
    dll.ss_binary_search_id.restype = ctypes.c_int64
    dll.ss_list_create.restype = ctypes.c_void_p
    dll.ss_list_free.argtypes = [ctypes.c_void_p]
    dll.ss_list_append.argtypes = [ctypes.c_void_p, ctypes.POINTER(CTransaction)]
    dll.ss_list_append.restype = ctypes.c_int32
    dll.ss_list_count.argtypes = [ctypes.c_void_p]
    dll.ss_list_count.restype = ctypes.c_int64
    dll.ss_category_totals.argtypes = [ctypes.POINTER(ctypes.c_int32), ctypes.POINTER(ctypes.c_int64), ctypes.c_int64, ctypes.POINTER(ctypes.c_int64), ctypes.c_int64]
    dll.ss_category_totals.restype = ctypes.c_int32
    return dll


def available(path):
    try:
        return library(path) is not None
    except OSError:
        return False


def newest_undo_id(path, event_ids):
    dll = library(path)
    if dll is None:
        return event_ids[-1] if event_ids else None
    stack = dll.ss_stack_create()
    if not stack:
        raise MemoryError("C undo stack could not be allocated")
    try:
        for event_id in event_ids:
            if dll.ss_stack_push(stack, event_id):
                raise RuntimeError("C undo stack push failed")
        value = ctypes.c_int64()
        result = dll.ss_stack_peek(stack, ctypes.byref(value))
        return value.value if result == 0 else None
    finally:
        dll.ss_stack_free(stack)


def cooling_order(path, rows):
    dll = library(path)
    if dll is None or not rows:
        return rows
    queue = dll.ss_queue_create()
    if not queue:
        raise MemoryError("C cooling-off queue could not be allocated")
    try:
        by_id = {r["id"]: r for r in rows}
        for row in rows:
            if dll.ss_queue_enqueue(queue, row["id"]):
                raise RuntimeError("C cooling-off queue enqueue failed")
        ordered = []
        value = ctypes.c_int64()
        while dll.ss_queue_dequeue(queue, ctypes.byref(value)) == 0:
            ordered.append(by_id[value.value])
        return ordered
    finally:
        dll.ss_queue_free(queue)


def rank_expenses(path, rows):
    if not rows:
        return rows
    dll = library(path)
    if dll is None:
        return sorted(rows, key=lambda r: (-r["amount_paise"], r["id"]))
    arr_type = CTransaction * len(rows)
    arr = arr_type(*(CTransaction(r["id"], r["amount_paise"], 1, r["category_id"] or 0) for r in rows))
    dll.ss_quick_sort(arr, len(rows))
    indexed = {r["id"]: r for r in rows}
    return [indexed[arr[i].id] for i in range(len(rows))]


def binary_search(path, sorted_rows, transaction_id):
    if not sorted_rows:
        return None
    if any(sorted_rows[i]["id"] > sorted_rows[i + 1]["id"] for i in range(len(sorted_rows) - 1)):
        raise ValueError("Binary-search input must be sorted by transaction ID")
    dll = library(path)
    if dll is None:
        lo, hi = 0, len(sorted_rows) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if sorted_rows[mid]["id"] == transaction_id:
                return sorted_rows[mid]
            if sorted_rows[mid]["id"] < transaction_id:
                lo = mid + 1
            else:
                hi = mid - 1
        return None
    arr_type = CTransaction * len(sorted_rows)
    arr = arr_type(*(CTransaction(r["id"], r["amount_paise"], 0, r["category_id"] or 0) for r in sorted_rows))
    index = dll.ss_binary_search_id(arr, len(sorted_rows), transaction_id)
    return sorted_rows[index] if index >= 0 else None


def transaction_list_count(path, rows):
    dll = library(path)
    if dll is None:
        return len(rows)
    handle = dll.ss_list_create()
    if not handle:
        raise MemoryError("C transaction list could not be allocated")
    try:
        for row in rows:
            item = CTransaction(row["id"], row["amount_paise"], 0 if row["type"] == "income" else 1, row["category_id"] or 0)
            if dll.ss_list_append(handle, ctypes.byref(item)):
                raise RuntimeError("C transaction list append failed")
        return dll.ss_list_count(handle)
    finally:
        dll.ss_list_free(handle)


def category_totals(path, rows, category_ids):
    dll = library(path)
    if not category_ids:
        return {}
    positions = {category_id: index for index, category_id in enumerate(category_ids)}
    indexes = [positions[row["category_id"]] for row in rows if row["category_id"] in positions]
    amounts = [row["amount_paise"] for row in rows if row["category_id"] in positions]
    if dll is None:
        totals = [0] * len(category_ids)
        for index, amount in zip(indexes, amounts):
            totals[index] += amount
    else:
        index_arr = (ctypes.c_int32 * len(indexes))(*indexes)
        amount_arr = (ctypes.c_int64 * len(amounts))(*amounts)
        output = (ctypes.c_int64 * len(category_ids))()
        result = dll.ss_category_totals(index_arr, amount_arr, len(indexes), output, len(category_ids))
        if result:
            raise RuntimeError("C category aggregation failed")
        totals = list(output)
    return dict(zip(category_ids, totals))
