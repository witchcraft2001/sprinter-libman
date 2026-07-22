;
; Тестовый пример использования LIBMAN.
;



; описание ds xx
%imacro ds 1
times %1 db 0
%endmacro

; описание ds xx,yy
%imacro ds 2
times %1 db %2
%endmacro




	org	7F00h

	db	"EXE"			; exe ID
	db	0			; exe версия
	dw	512			; 512, мл. смещ. кода
	dw	0			; ст. смещ. кода
	dw	0			; end-beg, первичный загрузчик
	dw	0,0,0			; резерв
	dw	entry			; адрес загрузки кода
	dw	entry			; адрес передачи управления
	dw	entry			; адрес стека
	ds	490

entry:
	; вывод приветствия
	ld	hl,msg			; "DLL test"
	ld	c,5Ch
	rst	10h

	; загрузка библиотеки
	ld	hl,file1		; имя dll-файла
	ld	a,3			; в 3 окно
	call	l_load
	jp	c,error
	ld	(handle),hl 		; дескр. загруж. библы

	; вторичная загрузка библы для теста
	ld	hl,file1		; имя dll-файла
	ld	a,1			; в 1 окно
	call	l_load
	jp	c,error

	; узнать информацию о библе
	ld	hl,(handle)
	ld	de,buff			; буфер 32 байта
	call	l_info
	jp	c,error
	
	; вывести строку описания библиотеки
	ld	hl,buff+16		; описание
	ld	c,5Ch
	rst	10h
	ld	hl,msg2			; "loaded!"
	ld	c,5Ch
	rst	10h

	; выполнить 2-ю функцию библиотеки
	ld	hl,(handle)
	ld	b,2			; номер функции
	call	l_call
	jp	c,error

	; выгрузить библиотеку
	ld	hl,(handle)
	call	l_free
	jp	c,error

	; ждем нажатия клавиши
;	ld	c,30h
;	rst	10h

	; выход в ДОС
exit:	ld	bc,0041h 
	rst	10h      
	ret

error:	ld	hl,msg3
	ld	c,5Ch
	rst	10h
	jr	exit




handle:	dw	0			; дескр. библиотеки

buff:	ds	32			; буфер для info

msg:	db	0Dh,0Ah,"DLL test",0Dh,0Ah,0
msg2:	db	" - success loaded!",0Dh,0Ah,0
msg3:	db	"Error...",0Dh,0Ah,0

file1:	db	"LIB.DLL",0


	%include "libman13.asm"
