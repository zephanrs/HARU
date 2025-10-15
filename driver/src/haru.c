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

#include "haru.h"
#include "misc.h"
#include <stdio.h>
#include <string.h>

/*
 * init and release
 */

int32_t haru_init(haru_t *haru) {

    fprintf(stderr, "Initializing HARU... (kernel module!)\n");

    uint32_t ret;

    // Initialize axi_dma
    ret = axi_dma_init(&haru->axi_dma, HARU_AXI_DMA_ADDR_BASE, HARU_AXI_DMA_SIZE);
    if (ret != 0) {
        fprintf(stderr, "Error: Failed to initialize AXI DMA\n");
        return -1;
    }

    // Initialize dtw_accel
    ret = dtw_accel_init(&haru->dtw_accel, HARU_DTW_ACCEL_ADDR_BASE, HARU_DTW_ACCEL_SIZE);
    if (ret != 0) {
        fprintf(stderr, "Error: Failed to initialize DTW_ACCEL\n");
        return -1;
    }

    haru_check_key(haru);
    uint32_t version = haru_get_version(haru);
    printf("HARU version: %x\n", version);
    return 0;
}

void haru_release(haru_t *haru) {
    axi_dma_release(&haru->axi_dma);
    dtw_accel_release(&haru->dtw_accel);
}

void haru_check_key(haru_t *haru) {
    uint32_t key = dtw_accel_get_key(&haru->dtw_accel);
    if (key != 0x0ca7cafe) {
        fprintf(stderr, "Error: Invalid key (%x)\n", key);
        return;
    }
    fprintf(stderr, "Key is correct (%x)\n", key);
}

uint32_t haru_get_version(haru_t *haru) {
    uint32_t version = dtw_accel_get_version(&haru->dtw_accel);
    return version;
}

void haru_set_dtw(haru_t *haru) { 
    dtw_accel_dtw(&haru->dtw_accel); 
}

void haru_set_sdtw(haru_t *haru) { 
    dtw_accel_sdtw(&haru->dtw_accel); 
}

void haru_get_results(haru_t *haru, uint32_t count, search_result_t *results) {
    dtw_accel_t *dtw_accel = &haru->dtw_accel;

    while (dtw_accel_get_count(dtw_accel) < count);

    results->qid = dtw_accel_get_qid(dtw_accel);
    results->idx = dtw_accel_get_idx(dtw_accel);
    results->position = dtw_accel_get_pos(dtw_accel);
    results->score = dtw_accel_get_score(dtw_accel);
}

void haru_process_reference(haru_t *haru, int32_t *ref, uint32_t size) {
    // copy reference into src buffer and DMA
    memset((void *)haru->axi_dma.v_src_addr, 0, 0xffff);
    memcpy((void *)haru->axi_dma.v_src_addr, (void *)ref, size * sizeof(int32_t));
    axi_dma_mm2s_transfer(&haru->axi_dma, size * sizeof(int32_t));
}

void haru_load_query(haru_t *haru, int32_t qid, int32_t *query, uint32_t size) {
    dtw_accel_reset(&haru->dtw_accel);
    memset((void *)haru->axi_dma.v_src_addr, 0, 0xffff);
    int32_t *src = (int32_t *)haru->axi_dma.v_src_addr;
    src[0] = qid;
    // copy query into src buffer and DMA
    memcpy(&src[1], query, size * sizeof(int32_t));
    axi_dma_mm2s_transfer(&haru->axi_dma, (size + 1) * sizeof(int32_t));
}
