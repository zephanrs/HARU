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

#ifndef DTW_ACCEL_H
#define DTW_ACCEL_H

#include <stdint.h>

// DTW Accel register addresses
#define DTW_ACCEL_CR_ADDR                   0 << 2
#define DTW_ACCEL_SR_ADDR                   1 << 2
#define DTW_ACCEL_VERSION_ADDR              2 << 2
#define DTW_ACCEL_KEY_ADDR                  3 << 2
#define DTW_ACCEL_DBG_REF_DIN_ADDR          4 << 2
#define DTW_ACCEL_QID_ADDR                  5 << 2
#define DTW_ACCEL_COUNT_ADDR                6 << 2
#define DTW_ACCEL_IDX_ADDR                  7 << 2
#define DTW_ACCEL_POS_ADDR                  8 << 2
#define DTW_ACCEL_SCORE_ADDR                9 << 2

// Status register bit offsets
#define DTW_ACCEL_SR_OFFSET_BUSY            0x00
#define DTW_ACCEL_SR_OFFSET_LOAD_DONE       0x01
#define DTW_ACCEL_SR_OFFSET_STATE_LSB       0x04
#define DTW_ACCEL_SR_OFFSET_STATE_MSB       0x05

// Key value
#define DTW_ACCEL_KEY                       0x0ca7cafe

typedef struct {
    uint32_t *v_baseaddr;    // Memory mapped virtual base address
    uint32_t p_baseaddr;    // Physical base address
    uint32_t size;          // Size of device
} dtw_accel_t;

int32_t dtw_accel_init(dtw_accel_t *device, uint32_t baseaddr, uint32_t size);
void dtw_accel_release(dtw_accel_t *device);

void dtw_accel_reset(dtw_accel_t *device);
void dtw_accel_dtw(dtw_accel_t *device);
void dtw_accel_sdtw(dtw_accel_t *device);

uint32_t dtw_accel_get_cr(dtw_accel_t *device);
uint32_t dtw_accel_get_sr(dtw_accel_t *device);
uint32_t dtw_accel_get_version(dtw_accel_t *device);
uint32_t dtw_accel_get_key(dtw_accel_t *device);

uint32_t dtw_accel_get_qid(dtw_accel_t *device);
uint32_t dtw_accel_get_count(dtw_accel_t *device);
uint32_t dtw_accel_get_idx(dtw_accel_t *device);
uint32_t dtw_accel_get_pos(dtw_accel_t *device);
uint32_t dtw_accel_get_score(dtw_accel_t *device);

uint32_t dtw_accel_busy(dtw_accel_t *device);
uint32_t dtw_accel_load_done(dtw_accel_t *device);
uint32_t dtw_accel_state(dtw_accel_t *device);

#endif