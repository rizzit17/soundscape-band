CFLAGS = -std=c99 -O2 -Wall -Wextra -Wpedantic -Wconversion -Wno-sign-conversion -Wno-float-conversion
all: deda_host_double deda_host_float
deda_host_double: deda.c doa_gcc.c host_main.c deda.h
	$(CC) $(CFLAGS) -DDEDA_REAL=double -o $@ deda.c doa_gcc.c host_main.c -lm
deda_host_float: deda.c doa_gcc.c host_main.c deda.h
	$(CC) $(CFLAGS) -o $@ deda.c doa_gcc.c host_main.c -lm
size: deda.c doa_gcc.c
	$(CC) -std=c99 -Os -c deda.c doa_gcc.c && size deda.o doa_gcc.o
clean:
	rm -f deda_host_double deda_host_float *.o
