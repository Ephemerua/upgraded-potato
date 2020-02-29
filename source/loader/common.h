
// returns a buffer, containing the str wanted
#define alloc_printf(_str...) ({ \
    char* _tmp; \
    size_t _len = snprintf(NULL, 0, _str); \
    if (_len < 0) {perror("Whoa, snprintf() fails?!"); abort();}\
    _tmp = malloc(_len + 1); \
    snprintf((char*)_tmp, _len + 1, _str); \
    _tmp; \
  })

//print debug info
#define debug_info(_str...) \
do {\
    printf("%s, %d: ", __FILE__, __LINE__); \
    printf(_str); \
}while(0)