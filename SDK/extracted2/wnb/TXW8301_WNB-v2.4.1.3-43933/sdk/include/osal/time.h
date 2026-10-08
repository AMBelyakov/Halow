#ifndef __OS_TIME_H_
#define __OS_TIME_H_

#ifdef __CSKY__
#include "osal/csky/time.h"
#endif

#ifdef __cplusplus
extern "C" {
#endif

#define MICROSECONDS_PER_SECOND    ( 1000000LL )                                   /**< Microseconds per second. */
#define NANOSECONDS_PER_SECOND     ( 1000000000LL )                                /**< Nanoseconds per second. */
#define NANOSECONDS_PER_TICK       ( NANOSECONDS_PER_SECOND / OS_HZ ) /**< Nanoseconds per FreeRTOS tick. */

uint64 os_jiffies(void);
void os_systime(struct timespec *tm);
int gettimeofday(struct timeval *ptimeval, struct timezone *ptimezone);
int settimeofday(const struct timeval *tv, const struct timezone *tz);
long time(long *t);
int32 timespec_detal_ticks(const struct timespec *abstime, const struct timespec *curtime, uint64 *result);
int32 timespec_to_ticks(const struct timespec *time, uint64 *result);
void nanosec_to_timespec(int64 llSource, struct timespec *time);
int32 timespec_add(const struct timespec *x, const struct timespec *y, struct timespec *result);
int32 timespec_add_nanosec(const struct timespec *x, int64 llNanoseconds, struct timespec *result);
int32 timespec_sub(const struct timespec *x, const struct timespec *y, struct timespec *result);
int32 timespec_cmp(const struct timespec *x, const struct timespec *y);
int32 timespec_validate(const struct timespec *time);
int clock_gettime(uint32 clk_id, struct timespec *tp);

#ifdef __cplusplus
}
#endif

#endif

