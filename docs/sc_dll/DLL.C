//  Примеры вызова функций обслуживания DLL-библиотек


#include <stdio.h>
#include <conio.h>
#include <dos.h>

union REGS inregs;
int handle;
char buff[32], func;


main()
{
     /*  Загрузить DLL-библиотеку  */

    if((handle = loaddll("lib.dll")) == -1)
       {
         cprintf("Ошибка загрузки библиотеки\n");
         exit(EXIT_FAILURE);
       }


    /*  Вывести строку описания библиотеки  */

    if(infodll(handle, buff) == -1)
      {
        cprintf("Ошибка работы с библиотекой\n");
        exit(EXIT_FAILURE);
      }
    else
        cprintf("%s\n", buff+16);


    /*  Выполнить функцию, входящую в DLL-библиотеку  */

    func=2;     // номер вызываемой функции
     // пример передачи параметров вызываемой функции
    inregs.h.a = 'A';
    inregs.h.h = 0x12;
    inregs.h.l = 0x34;
    inregs.x.bc = 0x5678;
    inregs.x.ix = 0x9ABC;

    if(calldll(handle, func, &inregs) == -1)
      {
        cprintf("Ошибка вызова функции\n");
        exit(EXIT_FAILURE);
      }


    /*  Выгрузить DLL-библиотеку из памяти  */

    if(freedll(handle) != 0)
      {
        cprintf("Ошибка выгрузки библиотеки\n");
        exit(EXIT_FAILURE);
      }
}
