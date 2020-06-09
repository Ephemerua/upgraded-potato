"""
## global
+ tips: 辅助性提示

## call_analysis 
+ return_address_overwritten: 返回地址修改
+ strange_return: 异常返回
+ unrecorded_strange_return: 未记录的异常返回

## heap_analysis
+ malloc: malloc信息
+ free: free信息
+ alloc_warn: 分配过程中的异常行为
+ free_warn: 释放过程中的异常行为
+ heap_overflow: 堆溢出
+ redzone_write: 写入不可访问区域

## got_analysis
+ got_mismatch: got表项错误
+ got_change: got表项被修改

## leak_analysis
+ leak: 存在信息泄漏
+ leak_trace: 发生信息泄漏位置

"""


desc_dict = {
    "malloc"    :"Calling (void*)malloc(size_t size) to allocate memory.",
    "free"      :"Calling free(void* addr) to free memory.",
    "alloc_warn":"Misbehaviour found during allocating memory.",
    "free_warn" :"Misbehaviour found during freeing memory.",
    "heap_overflow":"A memory write operation causes overflow in heap.",
    "redzone_write":"A memory write operation trys to access unavailable area.",
    "got_mismatch" :"Function pointer in got table mismatch with its real address\n.Probably modified by user.",
    "got_change"   :"Found illegal write to got table.",
    "return_address_overwritten":"Stack return address modified by user.\nProbably stack overflow.",
    "strange_return":"Function return's destnation mismatch with previous saved address.\nProbably caused by stack overflow or ROP attack.",
    "unrecorded_strange_return": "Function returns while no frame in stack.\nProbably ROP attack.",
    "leak"      :"Memory address found in output, causing information leakage.",
    "leak_trace":"Found memory information leakage scene.",
    "tips"      :"No detailed information."

}

key_replace_dict = {
    "backtrace":"Stack backtrace",
    "size":"Chunk size",
    "mtype":"Redzone type",
}