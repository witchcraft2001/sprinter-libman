// MK_DLL.CPP - Alexander Shabarshin  27.06.2002


#include <stdio.h>
#include <stdlib.h>
#include <string.h>


unsigned char *map = NULL;


int main(int argc, char **argv)
{
   int i, j, k, m, s, b, b1, b2, comp = 1;
   char str[256], s1[100], s2[100], *po;

   if(argc < 2)
     {
       puts("Creator DLL-library for Sprinter-2000.");
       puts(" Syntax: MK_DLL File.ext [0]");
       puts("  where: 0 - not compressed *.dll library.\n");
       puts("Requires z80asm.exe cross-compiler.\n");
       return 0;
     }
   else
      puts("Creator DLL-library for Sprinter-2000.");


   if(argc > 2 && argv[2][0] == '0' && argv[2][1] == 0)
       comp = 0;

   strcpy(s1,"1.a");	// имя первого временного файла
   strcpy(s2,"2.a");	// имя второго временного файла

   FILE *f0 = fopen(argv[1],"rt");

   if(f0 == NULL)
       return 0;

   FILE *f1 = fopen(s1,"wt");

   if(f1 == NULL)
     {
      fclose(f0);
      return 0;
     }

   FILE *f2 = fopen(s2,"wt");

   if(f2 == NULL)
     {
      fclose(f0);
      fclose(f1);
      return 0;
     }

   k = 1;

   while(1)
     {
      fgets(str, 255, f0);
      if(feof(f0))
          break;
      po = strchr(str,'\n');
      if(po != NULL)
          *po = 0;
      po = strchr(str,'\r');
      if(po != NULL)
          *po = ' ';
      po = str;
      while(*po == ' ' || *po == '\t')
         po++;
      if(k && (!strnicmp(po,"ORG ",4) || !strnicmp(po,"ORG\t",4)))
        {
         po[4] = 0;
         strcat(str,"0x0000");
         fprintf(f1,"%s\n",str);
         po[4] = 0;
         strcat(str,"0x0100");
         fprintf(f2,"%s\n",str);
         k = 0;
        }
      else
         {
          fprintf(f1,"%s\n",str);
          fprintf(f2,"%s\n",str);
         }
     }

   fclose(f0);
   fclose(f1);
   fclose(f2);

   system("z80asm.exe 2.a -o 2.bin");
   system("z80asm.exe 1.a -o 1.bin");
   printf("\nz80asm compiling done!\n\n");

   f1 = fopen("1.bin","rb");

   if(f1 == NULL)
       return 0;

   f2 = fopen("2.bin","rb");

   if(f2 == NULL)
     {
      fclose(f1);
      return 0;
     }

   strcpy(str, argv[1]);
   po = strchr(str,'.');

   if(po != NULL)
       *po = 0;

   strcat(str,".dll");
   f0 = fopen(str,"wb");

   if(f0 == NULL)
     {
      fclose(f1);
      fclose(f2);
      return 0;
     }

   fseek(f1, 0, SEEK_END);
   k = ftell(f1);
   fseek(f1, 0, SEEK_SET);
   int codelen = (k & 0xFF00) + ((k & 0x00FF) ? 256 : 0);
   int bmaplen = codelen >> 3;
   int filelen = codelen + bmaplen;
   printf("Size of code: %4.4Xh bytes\n",codelen,codelen);
   printf("Size of bmap: %4.4Xh bytes\n",bmaplen,bmaplen);
   printf("Size of file: %i bytes\n",filelen);
   map = new unsigned char[bmaplen];

   if(map == NULL)
     {
      fclose(f0);
      fclose(f1);
      fclose(f2);
      return 0;
     }

   memset(map,0,bmaplen);
   s = 0;
   b = 0;
   m = 0x80;
   j = 0;

   for(i = 0; i < k; i++)
      {
       b1 = fgetc(f1); 
       b2 = fgetc(f2); 
       if(b1 != b2)
           b |= m;
       m >>= 1;
       if(! m)
         {
          map[j++] = b;
          m = 0x80;
          b = 0;
         }
       fputc(b1, f0);
       if(i >= 0x10)
           s += b1;
      }

   map[j++] = b;
   fclose(f1);
   fclose(f2);

   while(i++ < codelen)
      fputc(0, f0);

   for(i = 0; i < bmaplen; i++) 
      {
       b = map[i];
       fputc(b, f0);
       s += b;
      }

   fclose(f0);

  // +00: 'L'
  // +01: '0'
  // +02: size of file 
  // +03:
  // +04: offset to bitmap
  // +05:
  // +06: size of bitmap
  // +07:
  // +08: cheksum
  // +09:
  // +0A: day
  // +0B: month
  // +0C: year
  // +0D:
  // +0E: version of library
  // +0F:
  // +10..1F: name of library

   f0 = fopen(str,"r+b");

   if(f0 == NULL)
       return 0;

   fputc('L',f0);
   fputc('0',f0);
   // размер файла библы
   fputc(filelen & 0xFF, f0);
   fputc(filelen >> 8, f0);
   // размер заголовка + кода
   fputc(codelen & 0xFF, f0);
   fputc(codelen >> 8, f0);
   // размер таблицы релокаций
   fputc(bmaplen & 0xFF, f0);
   fputc(bmaplen >> 8, f0);
   // CRC, сумма байтов начиная с адpеса 0010h
   fputc(s & 0xFF, f0);
   fputc((s & 0xFF00) >> 8, f0);

   fclose(f0);
  
   delete map;

   if(filelen > 0x4000)
       return 0;

   unlink("1.a");
   unlink("2.a");
   unlink("1.bin");
   unlink("2.bin");
   //unlink("1.lst");
   //unlink("2.lst");
  
   if(comp)
     {
      map = new unsigned char[filelen + 16];
      if(map == NULL)
        {
         fclose(f0);
         return 0;
        }
      f0 = fopen(str,"rb");
      if(f0 == NULL)
          return 0;
      fread(map, 1, filelen, f0);
      fclose(f0);
      f0 = fopen(str,"wb");
      if(f0 == NULL)
          return 0;
      k = 0;
      j = 0;
      for(i = 0; i < filelen; i++)
         {
      b = map[i]; 
      if(b || i < 0x10) 
        {
         if(j)
           {
            k += 2;
            fputc(0, f0); 
            fputc(j, f0);
            j = 0;
           } 
         fputc(b, f0);
         k++;
        }
      else
         {
          j++;
          if(j == 256)
            {
             k += 2;
             fputc(0, f0);
             fputc(0, f0);
             j = 0;
            }
         } 
     }

    if(j)
      {
       k += 2;
       fputc(0, f0); 
       fputc(j, f0);
      } 

    fclose(f0);
    f0 = fopen(str,"r+b");

    if(f0 == NULL)
        return 0;

    fseek(f0, 2, SEEK_SET);
    fputc(k & 0xFF, f0);
    fputc(k >> 8, f0);
    fclose(f0);
    delete map;
    printf("Compressed size: %i bytes\n",k);
   }
  
   printf("\nOk!\n");
  
  return 1;
}
