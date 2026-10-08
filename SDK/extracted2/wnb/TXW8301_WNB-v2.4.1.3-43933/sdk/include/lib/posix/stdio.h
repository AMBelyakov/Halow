#ifndef _HGIC_POSIX_FS_H_
#define _HGIC_POSIX_FS_H_
#include "typesdef.h"
#include <stdarg.h>
#include <fcntl.h>
#include <stdio.h>

#define _SYS_STAT_H

#ifdef __cplusplus
extern "C" {
#endif

#define ACC_MODE(x) ((x)&O_ACCMODE)

typedef int off_t;
off_t lseek(int fd, off_t offset, int whence);
int fsync(int fd);

typedef int mode_t;

struct __stdio_file{
    int fd;
};

struct stat {
    unsigned int    st_size;        /* File size */
    unsigned int    st_mtime;       /* Modified date */
    unsigned char   fattrib;        /* File attribute */
    char            *fname;         /* TODO: long file name File name */
};


extern int stat(const char *__file, struct stat *__buf);
extern int fstat(int fd, struct stat *statbuf);
int access(const char *pathname, int mode);

#define F_OK 0
#define R_OK 1
#define W_OK 2
#define X_OK 3

#ifdef __cplusplus
}
#endif

#endif

