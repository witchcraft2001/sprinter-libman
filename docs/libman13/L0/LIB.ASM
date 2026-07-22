	org	0

	db	"L0"			; сигнатура формата
	dw	0			; размер файла библиотеки
	dw	0			; размер кода без таблицы перемещений
	dw	0			; размер таблицы перемещений
	dw	0			; контрольная сумма
	db	15			; день
	db	7			; месяц
	dw	2003			; год
	dw	0102h			; v1.2 версия библиотеки
	db	"Sample Library",0,0	; описание, 16 байт

;---
	jp	init
	jp	free
	jp	user

;N0
init:
	ld	hl,_init
	ld	c,5Ch
	rst	10h
	xor	a			; for LIBMAN
	ret
;N1
free:
	ld	hl,_free
	ld	c,5Ch
	rst	10h
	ret
;N2
user:
	ld	hl,_user
	ld	c,5Ch
	rst	10h
	ret


_init:	db	"DLL init",0Dh,0Ah,0
_free:	db	"DLL free",0Dh,0Ah,0
_user:	db	"DLL user",0Dh,0Ah,0
