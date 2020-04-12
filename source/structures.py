# XXX: at now just define a malloc_state struct and unpack to that...
# should get struct definition from debug_info
import cstruct

class malloc_state(cstruct.CStruct):
    __byte_order__ = cstruct.LITTLE_ENDIAN
    __struct__ = """
        int mutex;
        int flags;
        unsigned long long fastbinsY[10];
        unsigned long long top;
        unsigned long long last_remainder;
        unsigned long long bins[254];
        unsigned int binmap[4];
        unsigned long long next;
        unsigned long long next_free;
        unsigned long long attached_threads;
        unsigned long long system_mem;
        unsigned long long max_system_mem;
    """