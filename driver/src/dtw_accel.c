/* MIT License

Copyright (c) 2022 Po Jui Shih
Copyright (c) 2022 Hassaan Saadat
Copyright (c) 2022 Sri Parameswaran
Copyright (c) 2022 Hasindu Gamaarachchi

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE. */

#include "dtw_accel.h"
#include "misc.h"

#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

/*
 * Init and release functions
 */
int32_t dtw_accel_init(dtw_accel_t *device, uint32_t baseaddr, uint32_t size) {
    int dev_fd = open("/dev/mem", O_RDWR | O_SYNC);
    if (dev_fd < 0) {
        return -1;
    }

    device->size = size;
    device->p_baseaddr = baseaddr;
    device->v_baseaddr = (uint32_t *) mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED, dev_fd, baseaddr);
    if (device->v_baseaddr == MAP_FAILED) {
        close(dev_fd);
        return -1;
    }

    dtw_accel_reset(device);
    close(dev_fd);
    return 0;
}

void dtw_accel_release(dtw_accel_t *device) {
    munmap(device->v_baseaddr, device->size);
}

/*
 * Setter functions
 */
void dtw_accel_reset(dtw_accel_t *device) {
    uint32_t cr = _reg_get(device->v_baseaddr, DTW_ACCEL_CR_ADDR) & ~1;
    _reg_set(device->v_baseaddr, DTW_ACCEL_CR_ADDR, cr | 1);
    _reg_set(device->v_baseaddr, DTW_ACCEL_CR_ADDR, cr);
}

void dtw_accel_dtw(dtw_accel_t *device) {
    uint32_t cr = _reg_get(device->v_baseaddr, DTW_ACCEL_CR_ADDR) & ~2;
    _reg_set(device->v_baseaddr, DTW_ACCEL_CR_ADDR, cr);
}

void dtw_accel_sdtw(dtw_accel_t *device) {
    uint32_t cr = _reg_get(device->v_baseaddr, DTW_ACCEL_CR_ADDR) & ~2;
    _reg_set(device->v_baseaddr, DTW_ACCEL_CR_ADDR, cr | 2);
}

/*
 * Register getter functions
 */
uint32_t dtw_accel_get_cr(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_CR_ADDR);
}

uint32_t dtw_accel_get_sr(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_SR_ADDR);
}

uint32_t dtw_accel_get_version(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_VERSION_ADDR);
}

uint32_t dtw_accel_get_key(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_KEY_ADDR);
}

uint32_t dtw_accel_get_qid(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_QID_ADDR);
}

uint32_t dtw_accel_get_count(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_COUNT_ADDR);
}

uint32_t dtw_accel_get_idx(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_IDX_ADDR);
}

uint32_t dtw_accel_get_pos(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_POS_ADDR);
}

uint32_t dtw_accel_get_score(dtw_accel_t *device) {
    return _reg_get(device->v_baseaddr, DTW_ACCEL_SCORE_ADDR);
}

/*
 * Bit getter functions
 */
uint32_t dtw_accel_busy(dtw_accel_t *device) {
    uint32_t sr = _reg_get(device->v_baseaddr, DTW_ACCEL_SR_ADDR);
    return (sr >> DTW_ACCEL_SR_OFFSET_BUSY) & 1;
}

uint32_t dtw_accel_load_done(dtw_accel_t *device) {
    uint32_t sr = _reg_get(device->v_baseaddr, DTW_ACCEL_SR_ADDR);
    return (sr >> DTW_ACCEL_SR_OFFSET_LOAD_DONE) & 1;
}

uint32_t dtw_accel_state(dtw_accel_t *device) {
    uint32_t sr = _reg_get(device->v_baseaddr, DTW_ACCEL_SR_ADDR);
    return (sr >> DTW_ACCEL_SR_OFFSET_STATE_LSB) & ((1 << 2)-1);
}
