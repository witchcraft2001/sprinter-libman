; Последняя редакция: 30.04.2004
;
; Module LIBMAN v1.3
;
; Доработанный менеджер dll-библиотек, версия v1.3.
; (на 48 байт короче оригинального).
;
; Менеджер работает с форматами L0, L1 библиотек.
;
;
;
; Примечание:
; ~~~~~~~~~~~
; формат "L0":
;   4 нуля (32 бита) перед таблицей перемещений нужны для того,
;   чтобы функция remake "обошла" 32 байта dll-заголовка.
;



; Экспортная версия собирается двумя частями:
;   LIBMAN_LOADER_ONLY  - загрузчик, пригодный для размещения в WIN0;
;   LIBMAN_RUNTIME_ONLY - call/free/info и relocation, размещаемые вместе
;                         с состоянием в постоянно видимом WIN1.

	IFNDEF	LIBMAN_RUNTIME_ONLY

true	equ	1
false	equ	0

	IFNDEF	LIBMAN_MAX_LIBS
	DEFINE	LIBMAN_MAX_LIBS 64
	ENDIF
	ASSERT	LIBMAN_MAX_LIBS >= 1
	ASSERT	LIBMAN_MAX_LIBS <= 64

; В split-режиме эта точка и _L_LOAD могут находиться в WIN0.
coreload:
	jp	_L_LOAD


;==================================================================
;  Таблица загрузки библиотек (LIBMAN_MAX_LIBS, макс. 64 шт.)
;==================================================================
; Размер таблицы: LIBMAN_MAX_LIBS * 4 байта
; Макс. число элементов: 64
; Длина элемента: 4 байта
; Структура отдельного элемента таблицы:
;
;    +00  - 0/1 свободен/занят
;    +01  - дескр. блока памяти
;    +02  - ст.байт адреса начала
;    +03  - ст.байт адреса конца

max_count equ	LIBMAN_MAX_LIBS		; макс. число загр. библиотек




;==================================================================
;  Загрузка библиотеки в память
;==================================================================
;   ld      hl,filename   ;имя файла
;   ld      a,win         ;окно 1,2,3
;   call    l_load
;   jp      c,error
;   ld      (handle),hl   ;дескр. библы
;
_L_LOAD:
	push	ix
	push	iy
	push	de
	push    af
	push    hl
	xor	a
	ld	(ll_tmp_owned),a
	ld	(ll_file_open),a
	ld	(ll_entry_active),a
	ld	(ll_final_new),a
	ld	(llzero+1),a		; do not inherit a partial zero-RLE run
	ld	a,true
	ld	(ll_fr+1),a		; флаг релокации
	ld	(ll_fc+1),a		; флаг компрессии
	in      a,(0E2h)
	ld      (lloldw+1),a		; сохр. начальную Page3
	; выделить блок в 2 страницы
	ld      bc,023Dh
	rst     10h
	jp      c,llerr_before_path	; ошибка выделения
	ld      (llid),a		; дескр. выдел. блока памяти
	ld	a,true
	ld	(ll_tmp_owned),a
	; сразу подготовить одну страницу
	; под загрузку файла библы.
	ld      bc,003Bh		; подкл. 1-ю страницу блока в 3-е окно
	ld	a,(llid)
	rst     10h
	jp      c,llerr_before_path	; ошибка подключения
	pop     hl
	; открыть файл
	ld      a,1			; на чтение
	ld      c,11h
	rst     10h
	jp      c,llerr_after_path
	ld      (llhand),a		; дескр. открытой библы
	ld	a,true
	ld	(ll_file_open),a
	; указатель в конец файла
	ld      hl,0
	push	hl
	pop	ix
	ld      bc,0215h		; MOVE_FP
	rst     10h
	jp      c,llerr_after_path	; ошибка перемещения указателя
	ld      a,h
	or      l
	jp      nz,llerr_after_path	; слишком большой файл
	push    ix			; размер файла, мл.разряд
	; вернуть указатель в начало файла
	ld      hl,0
	push	hl
	pop	ix
	ld      a,(llhand)		; дескр. открытой библы
	ld      bc,0015h		; MOVE_FP
	rst     10h
	pop     hl
	ld      (llsize),hl		; размер библы
	jp      c,llerr_after_path	; ошибка перемещения указателя
	; чтение файла
	ld      c,13h
	ld      de,16			; число чит. байт
	ld      hl,llbuf		; буфер первых 16-ти байт заголовка
	ld      a,(llhand)		; дескр. открытой библы
	rst     10h
	jp      c,llerr_after_path
	; вернуться в начало файла
	ld      hl,0
	push	hl
	pop	ix
	ld      a,(llhand)		; дескр. открытой библы
	ld      bc,0015h		; MOVE_FP
	rst     10h
	jp      c,llerr_after_path	; ошибка перемещения указателя
	; берем данные из первых 16-ти байт заголовка
	ld	ix,llbuf		; буфер первых 16-ти байт заголовка
	ld	a,(ix+0)
	cp	"L"
	jp	nz,llerr_after_path	; не знакомый формат библы
	ld	e,true
	ld	a,(ix+1)
	cp	"1"
	jr	z,ll0s
	cp	"0"
	jp	nz,llerr_after_path	; не верный формат библы
	dec	e
ll0s:	ld	a,e
	ld	(l1_form+1),a		; true/false  уст. формат библы
	ld      e,(ix+2)		; общ. размер библы (de идет для функ.чтения)
	ld      d,(ix+3)
	ld	l,(ix+4)		; размер библы без рел-таблицы
	ld	h,(ix+5)
	ld	c,(ix+6)		; размер рел-таблицы
	ld	b,(ix+7)
	; библа сжата ? (de=hl ?)
	add	hl,bc			; заголовок + код библы = размер библы
	ld	a,h
	cp	d
	jr	nz,ll0r			; сжата
	ld	a,l
	cp	e
	jr	nz,ll0r			; сжата
	xor	a			; false
	ld	(ll_fc+1),a		; сбр. флаг компрессии (библа не сжата)
	; библа перемещаемая ?
ll0r:	ld	a,b
	cp	c
	jr	nz,ll0			; да, рел-таблица не равна нулю
	xor	a			; false
	ld	(ll_fr+1),a		; сбр. флаг релокации
	; прочитать всю библу в подгот. страницу
	; de=размер библы
ll0:	ld      c,13h
	ld      hl,0C000h		; буфер чтения
	ld      a,(llhand)		; дескр. библы
	rst     10h
	jp      c,llerr_after_path	; ошибка чтения
	;
	ld      hl,0C000h		; начало 0-й страницы
	ld      d,h			; также для 1-й страницы
	ld      e,l
	; hl - упак. данные в 0-й странице
	; de - распак. данные в 1-й странице
loop:	ld      bc,16			; размер "порции"
	push    de
	ld      de,llbuf		; исп. буфер первых 16-ти байт заголовка
	; The accelerator pseudo-instruction sequence is not reliable while WIN3
	; is repeatedly remapped by DSS.  Deterministic 16-byte LDIR copies keep
	; the temporary DLL image intact on real Sprinter hardware.
	ldir
	push    hl
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,013Bh		; подкл. 2-ю страницу блока в 3-е окно
	rst     10h
	pop     hl
	pop     de
	jp      c,llerr_after_path	; ошибка подкл.
	ld      bc,16
	push    hl
	ld      hl,llbuf		; буфер первых 16-ти байт заголовка
ll_fc:	ld	a,true			; флаг компрессии
	or	a
	jr	z,ll1z			; не было компрессии
	; de == 0C010h ?
	ld      a,d
	cp      0C0h			; ст.байт начала страницы
	jr      nz,ll2
	ld      a,e
	cp      10h			; размер блока
	jr      nc,ll2
	; See the LDIR note in the input copy above.
ll1z:	ld      bc,16
	ldir
	jr      ll3
;-
ll2:	ld	b,c			; b=16
llzero:	ld      a,false			; флаг последовательности нулей
	or      a
	jr      z,ll2a			; false
	xor     a
	ld      (llzero+1),a
	jr      ll2c
	;
ll2a:	ld      a,(hl)
	or      a
	jr      nz,ll2b
	inc     hl
	dec     b
	jr      z,ll2e
ll2c:	ld      (de),a
	inc     de			; de++ for decoding
	dec     (hl)
	jr      nz,ll2c
	inc     hl
	jr      ll2d
	;
ll2e:	ld      a,true
	ld      (llzero+1),a		; флаг последовательности нулей
	jr      ll3
	;
ll2b:	ld      (de),a
	inc     hl
	inc     de
ll2d:	djnz	ll2a
;-
ll3:	push    de
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,003Bh		; подкл. 1-ю страницу блока в 3-е окно
	rst     10h
	pop     de
	pop     hl			; hl=0C010h ?
	jp	c,llerr_after_path	; ошибка подкл.
	ld      a,(llsize+1)		; ст.байт размера библы
	ld      b,a
	ld      a,h
	sub     0C0h
	cp      b
	jp      c,loop			; назад в цикл
	jr      nz,ll4
	ld      a,(llsize)		; мл.байт размера библы
	ld      b,a
	ld      a,l
	cp      b
	jp      c,loop			; назад в цикл
	;
ll4:	xor     a			; false
	ld      (llzero+1),a		; флаг последов. нулей
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,013Bh		; подкл. 2-ю страницу в 3-е окно
	rst     10h
	jp	c,llerr_after_path
	ld      hl,0C004h		; +4 адрес начала рел-таблицы (заголовок)
	ld      e,(hl)
	inc     hl
	ld      d,(hl)
	inc     hl
	ex      de,hl
	push    hl
	pop     iy			; начало рел-таблицы (для remake)
	dec     hl
ll_fr:	ld	a,true			; флаг релокации
	or	a
	jr	nz,ll4a
	; библа была не перемещаемая (без рел-таблицы)
	ld	hl,4000h		; макс. размер не перемещ. библы
ll4a:	ld      (llsize),hl		; размер библы (код)
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,003Bh		; подкл. 1-ю страницу в 3-е окно
	rst     10h
	jp	c,llerr_after_path
	ld      hl,0C000h
	ld      de,0C001h
	ld      bc,255
	ld      (hl),0
	ldir
	ld      hl,lib_table		; таблица библ
	ld      b,max_count		; макс. число загр. библиотек
ll5:	ld      a,(hl)
	or      a
	jr      z,ll5c
	push    hl
	pop     ix			; адрес в таблице библ
	ld      h,0C0h
	ld      l,(ix+1)
	ld      a,(ix+3)
	and     3Fh
	inc     a
	cp      (hl)
	jr      c,ll5a
	ld      (hl),a
ll5a:	push    ix
	pop     hl
ll5c:	inc     hl
	inc     hl
	inc     hl
	inc     hl
	djnz	ll5
	ld      hl,lib_table		; таблица библ
	ld      b,max_count		; макс. число загр. библиотек
ll5b:	ld      a,(hl)
	or      a
	jr      z,ll6
	inc     hl
	inc     hl
	inc     hl
	inc     hl
	djnz	ll5b
	jp      llerr_after_path	; ошибка
	;
ll6:	push    hl
	pop     ix			; адрес в таблице
	ld	(ll_entry_ptr),hl
	; просканировать таблицу
	ld      hl,0C000h
	ld      bc,256			; размер таблицы
ll7:	ld      a,(hl)
	or      a
	jr      nz,ll8			; занятая запись
ll7a:	inc     hl
	dec     bc
	ld      a,b
	or      c
	jr      nz,ll7
	; выделить блок в 1-ну страницу
	ld      bc,013Dh
	rst     10h
	jp      c,llerr_after_path	; ошибка выделения
	ld	(ll_final_id),a
	ld      l,a
	ld	a,true
	ld	(ll_final_new),a
	ld	a,(llsize+1)
	ld      d,0
	jr      ll8c
	;
ll8:	ld      d,a
	ld      a,(llsize+1)		; ст.байт размера библы
	add     a,d
	cp      40h			; (40)00
	jr      nc,ll7a
ll8c:	ld      e,a
	ld	a,(ll_window)
	; A = окно (1,2,3)
	dec	a			; a=1 ?
	jr      nz,ll8a
	ld      a,40h			; (40)00	page 1
	jr      ll9
ll8a:	dec	a			; a=2 ?
	jr      nz,ll8b
	ld      a,80h			; (80)00	page 2
	jr      ll9
ll8b:	ld      a,0C0h			; (C0)00	page 3
ll9:	ld	c,a
	add     a,d
	ld      d,a
	ld	a,c			; восст."a"
	add     a,e
	ld      e,a
	ld      (ix+0),true		; флаг "занятый элемент" в таблице
	ld      (ix+1),l		; дескр. страницы библы
	ld      (ix+2),d		; ст.байт адреса начала библы
	ld      (ix+3),e		; ст.байт адреса конца библы
	ld	a,true
	ld	(ll_entry_active),a
	push	de
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,013Bh		; подкл. 2-ю страницу в 3-е окно
	rst     10h
	pop	bc			; новый адрес кода
	jp	c,llerr_with_entry
	ld	de,0C000h
	add     iy,de			; начало рел-таблицы + 0C000h
	ex	de,hl			; hl=0C000h адрес исх. кода
l1_form:ld	a,true			; флаг формата библы
	or	a
	jr	z,nofix			; "L0" формат
	; "L1" формат
	ld	de,32			; длина заголовка
	add	hl,de			; скоррект. начало исх. кода
nofix:	ld      de,(llsize)		; длина кода (размер библы)
	ld	a,(ll_fr+1)		; флаг релокации
	or	a
	call	nz,remake		; настроить переходы
	ld      hl,0C000h
	ld      a,(ix+2)
	or      0C0h
	ld      d,a
	ld      e,0
ll10:	push    de
	ld      de,llbuf		; буфер первых 16-ти байт заголовка
	ld      bc,16
	ldir
	pop     de
	push    hl
	push	de
	ld      a,(ix+1)		; дескр. блока из 2-х страниц
	ld      bc,003Bh		; подкл. 1-ю страницу в 3-е окно
	rst     10h
	pop	de
	jp	c,llcopy_map_final_error
	ld      hl,llbuf		; буфер первых 16-ти байт заголовка
	ld      bc,16
	ldir
	push	de
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      bc,013Bh		; подкл. 2-ю страницу в 3-е окно
	rst     10h
	pop	de
	pop     hl
	jp	c,llerr_with_entry
	ld      a,(ix+3)
	or      0C0h
	cp      d
	jr      nc,ll10
	ld      a,(ix+1)		; дескр. блока из 2-х страниц
	ld      bc,003Bh		; подкл. 1-ю страницу в 3-е окно
	rst     10h
	jp	c,llerr_with_entry
	ld      a,(llid)		; дескр. выдел. блока из 2-х страниц
	ld      c,3Eh			; освободить блок памяти
	rst     10h
	jp	c,llerr_with_entry	; ошибка освобождения
	xor	a
	ld	(ll_tmp_owned),a
	ld	hl,(ll_entry_ptr)
	ld      bc,lib_table		; таблица библ
	or	a
	sbc     hl,bc
	ld      a,l
	rra				; 2-й бит (4-ки) на место 0-го
	rra				; адрес ячейки в таблице библ -> в номер дескр.
	ld      l,a			; номер дескр. загр. библы
	ld      h,0
	ld      b,h			; 0-й номер функции
lloldw:	ld      a,-1			; сохр. начальная Page3
	out     (0E2h),a		; восст. страницу
	call    corecall		; иниц. (загрузить) библу
	push	af
	push	hl
	call	ll_close_file
	jr	c,ll_close_error
	pop	hl
	pop	af
	jr	c,ll_init_error
	push	af
	xor	a
	ld	(ll_entry_active),a
	ld	(ll_final_new),a
	pop	af
	pop	bc			; удалить сохраненное целевое окно
	pop	de
	pop	iy
	pop	ix
	ret

ll_init_error:
	push	af
	call	corefree		; выгрузить библу
	jr	c,ll_init_free_error
	xor	a
	ld	(ll_final_new),a
ll_init_free_error:
	xor	a
	ld	(ll_entry_active),a
	call	ll_cleanup_partial
	pop	af
	pop	bc			; удалить сохраненное целевое окно
	pop	de
	pop	iy
	pop	ix
	ret

llcopy_map_final_error:
	pop	hl			; снять сохраненный адрес источника
	jr	llerr_with_entry

ll_close_error:
	pop	hl			; handle
	pop	af			; результат init больше не возвращается
	call	corefree
	jr	c,ll_close_free_error
	xor	a
	ld	(ll_final_new),a
ll_close_free_error:
	xor	a
	ld	(ll_entry_active),a
	call	ll_cleanup_partial
	jr	llerr_return

llerr_with_entry:
	call	ll_drop_entry
	jr	llerr_after_path

llerr_before_path:
	pop	hl			; имя еще находилось в стеке
llerr_after_path:
	call	ll_cleanup_partial
llerr_return:
	pop	bc			; удалить сохраненное целевое окно
	pop	de
	pop	iy
	pop	ix
	scf
	ld	a,-1
	ret

	ENDIF				; !LIBMAN_RUNTIME_ONLY


	IFNDEF	LIBMAN_LOADER_ONLY

corefree:
	jp	_L_FREE

corecall:
	jp	_L_CALL

coreinfo:
	jp	_L_INFO



;==================================================================
;  Коррекция адресов переходов по таблице перемещений
;==================================================================
; de = длина кода
; bc = новый адрес кода (b=старший байт)
; hl = адрес коррект. кода
; iy = начало рел-таблицы
;
remake:	ld	c,b
rmk1:	ld	b,8			; разрядность байта
	ld	a,(iy+0)
rmk2:	rla
	call	c,reloc			; правка ст.байта адреса
	ex	af,af'
	inc	hl
	dec	de
	ld	a,d
	or	e
	ret	z
	ex	af,af'
	djnz	rmk2
	inc	iy
	jr	rmk1
	;
reloc:	ex	af,af'
	ld	a,(hl)
	add	a,c
	ld	(hl),a
	ex	af,af'
	ret





;==================================================================
;  Выгрузка библиотеки из памяти
;==================================================================
;
;    ld      hl,(handle)
;    call    l_free
;    jp      c,error
;
_L_FREE:
	push	de
	push	bc
	ld      b,1			; номер функции
	call    corecall
	;ld      d,0
	;ld      e,l
	ex	de,hl			; поставил
	ld      hl,lib_table		; таблица библ
	add     hl,de
	add     hl,de
	add     hl,de
	add     hl,de
	ld      a,(hl)			; +0 свободна/занята
	or      a
	scf
	jr      z,lf_ee
	ld      (hl),0
	inc     hl
	ld      c,(hl)			; +1 дескр. окна
	ld      hl,lib_table		; таблица библ
	ld      b,max_count		; макс. число загр. библиотек
	ld      e,0
lf1:	ld      a,(hl)
	jr      z,lf2
	inc     hl
	ld      a,(hl)
	cp      c
	jr      nz,lf3
	inc     e
	jr      lf3
	;
lf2:	inc     hl
lf3:	inc     hl
	inc     hl
	inc     hl
	djnz	lf1
	ld      a,e
	or      a
	jr      nz,lf_e
	ld      a,c			; дескр. блока
	ld      c,3Eh			; освободить блок
	rst     10h
	jr	lf_ee
	;
lf_e:	xor     a
lf_ee:	pop	bc
	pop	de
	ret




;==================================================================
;  Вызов процедур библиотеки на исполнение
;==================================================================
; Передаваемые параметры в: a,de,ix,iy and alt. regs
;
;    ld      hl,(handle)  ;дескр. библы
;    ld      b,function   ;номер функции
;    call    l_call
;    jp      c,error
;
;    out: hl=handle
;
_L_CALL:
	push    hl
	push    de
	push    bc
	push    af
	xor	a
	ld	(lcflag),a
	ld	a,b			; номер функции
	ld	(lc_fun),a
	ld      a,l			; дескр. библы
	rla				; 0-й бит на место 2-го
	rla				; восст. адрес ячейки в таблице библ
	ld      l,a
	ld      de,lib_table		; таблица библ
	add     hl,de			; перейти на адрес элемента таблицы
	ld      a,(hl)			; +0 ячейка занятости
	or      a
	jp      z,lc_er2		; ошибка, элемент не занят
	inc     hl
	ld      a,(hl)			; +1 дескр. блока памяти
	push    af
	inc     hl
	ld      h,(hl)			; +2 ст.байт адрес начала
	ld      l,20h			; смещ. на размер заголовка
	ld      (lcstart),hl		; начало кода библы в окне
	ld      a,h
	and     0C0h
	ld      (lcoldp),a
	cp      40h
	jr      nz,lc1
	in      a,(0A2h)
	jr      lc3
	;
lc1:	cp      80h
	jr      nz,lc2
	in      a,(0C2h)
	jr      lc3
	;
lc2:	cp      0C0h
	jr      nz,lc_er3
	in      a,(0E2h)
lc3:	ld      (lc4_+1),a
	pop     af			; дескр. блока памяти (из +1)
	; Estex-DSS generic SETWIN derives the wrong port for WIN1.  Select the
	; explicit API entry point and preserve public IX/IY arguments around it.
	push	ix
	push	iy
	ld	b,0
	bit	7,h
	jr	z,lc_map_win1
	bit	6,h
	jr	z,lc_map_win2
	ld	c,3Bh
	jr	lc_map
lc_map_win1:
	ld	c,39h
	jr	lc_map
lc_map_win2:
	ld	c,3Ah
lc_map:
	rst     10h
	jr	c,lc_setwin_error
	pop	iy
	pop	ix
	pop     af
	pop     bc
	pop     de
	; возможные передаваемые
	; аргументы функции:
	; a,de,ix,iy and alt. regs
	ld      hl,(lcstart)		; начало кода библы в окне
	ld      c,b			; номер передаваемой функции
	ld      b,0
	add     hl,bc			;1+1=2 обойти init, free (0,1) функции
	add     hl,bc			;2+1=3
	add     hl,bc			;3+1=4
	ld      bc,lc_
	push    bc			; в стек точку возврата
	jp      (hl)			; Вызов функции

lc_:	pop     hl			; восст. вход. дескриптор (и баланс стека)
	ld	c,a			; сохр."a"
	jr	nc,lc4_
	ld	a,(lc_fun)
	or	a			; тест на 0-ю функцию
	jr	nz,lc4_
	dec	a			; a=0FFh
	ld	(lcflag),a
lc4_:	ld      a,-1
	ld      b,a
	ld      a,(lcoldp)
	cp      40h
	jr      nz,lc1_
	ld      a,b
	out     (0A2h),a
	jr      lc3_
	;
lc1_:	cp      80h
	jr      nz,lc2_
	ld      a,b
	out     (0C2h),a
	jr      lc3_
	;
lc2_:	cp      0C0h
	jr      nz,lc_er0
	ld      a,b
	out     (0E2h),a
lc3_:	ld	a,(lcflag)
	rlca				; уст. carry-флаг
	ld	a,c			; восст."a"
	ret
	;
lc_setwin_error:
	pop	iy
	pop	ix
	jr	lc_er2
lc_er3:	pop     af
lc_er2:	pop     af
	pop     bc
	pop     de
lc_er1:	pop     hl
lc_er0:	scf
	ret


;==================================================================
;  Получить информацию о библиотеке
;==================================================================
; copy lib info to buffer
;
;    ld      hl,(handle)    ;дескр. библы
;    ld      de,buffer32    ;буфер, 32 байта
;    call    l_info
;    jp      c,error
;
_L_INFO:
	push    hl
	push    de
	push    bc
	ld      a,l
	add	a,a
	add	a,a
	ld	l,a
	ld      bc,lib_table		; таблица библ
	add     hl,bc
	ld      a,(hl)			;+0 флаг "свободна/занята"
	or      a
	scf
	jr      z,li_er			; ошибка
	inc     hl
	ld      b,(hl)			;+1 дескр. страницы библы
	inc     hl
	ld      a,(hl)
	or      0C0h
	ld      h,a
	ld      l,0
	in      a,(0E2h)
	ld      (lioldw+1),a
	push	hl
	push	de
	ld      a,b			; дескр. страницы библы
	ld      bc,003Bh		; подкл. в 3-е окно
	rst     10h
	pop	de
	pop	hl
	jr	c,li_map_error
	ld      bc,32			; длина info
	ldir
lioldw:	ld	a,-1			; восст. порт
	out	(0E2h),a
	xor	a
	jr	li_er
li_map_error:
	push	af
	ld	a,(lioldw+1)
	out	(0E2h),a
	pop	af
	scf
li_er:	pop	bc
	pop	de
	pop	hl
	ret

	ENDIF				; !LIBMAN_LOADER_ONLY
