/*
 *	STDLIB.H
 *
 *	A header for a standart library CLIB.
 *	(c) 2004, SOLID C  Sprinter-2000
 */


#ifndef	_C_TYPES_
#include <types.h>
#endif

#ifndef	_STD_LIB_
#define	_STD_LIB_

char errno;			/* must be declaration here */


/* for "div" function */
typedef struct divt {
        uint	quot;		/* частное */
        uint	rem;		/* остаток */
} div_t;


int abs();
int atoi();
int min();
int max();
int strtol();
int rand();
void *bsearch();
void qsort();
void srand();
void perror();
void exit();
void _exit();
void abort();
char atexit();
char *sysenv();
char *getenv();
uint putenv();
struct divt *div();
int loaddll();
int freedll();
int calldll();
int infodll();
void hex8();
void hex16();
void hex32();
void dec8();
void dec16();
void dec32();

#endif
