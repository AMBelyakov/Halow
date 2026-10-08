
#ifndef __CSKY_OS_TIME_H_
#define __CSKY_OS_TIME_H_

#include <time.h>
#include <sys/time.h>

/*struct timeval */
/* Convenience macros for operations on timevals.
   NOTE: `timercmp' does not work for >= or <=.  */
#define timerisset(tvp)         ((tvp)->tv_sec || (tvp)->tv_usec)
#define timerclear(tvp)         ((tvp)->tv_sec = (tvp)->tv_usec = 0)
#define timercmp(a, b, CMP)                                                   \
  (((a)->tv_sec == (b)->tv_sec) ?                                             \
   ((a)->tv_usec CMP (b)->tv_usec) :                                          \
   ((a)->tv_sec CMP (b)->tv_sec))

#if 1 //see: posix/timer.c
#define timeradd(a, b, result)                                                \
  do {                                                                        \
    (result)->tv_sec = (a)->tv_sec + (b)->tv_sec;                             \
    (result)->tv_usec = (a)->tv_usec + (b)->tv_usec;                          \
    if ((result)->tv_usec >= 1000000)                                         \
      {                                                                       \
        ++(result)->tv_sec;                                                   \
        (result)->tv_usec -= 1000000;                                         \
      }                                                                       \
  } while (0)
#define timersub(a, b, result)                                                \
  do {                                                                        \
    (result)->tv_sec = (a)->tv_sec - (b)->tv_sec;                             \
    (result)->tv_usec = (a)->tv_usec - (b)->tv_usec;                          \
    if ((result)->tv_usec < 0) {                                              \
      --(result)->tv_sec;                                                     \
      (result)->tv_usec += 1000000;                                           \
    }                                                                         \
  } while (0)
#endif

#endif


