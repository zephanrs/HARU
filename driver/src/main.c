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

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "haru.h"
#include "haru_test.h"

#define REFERENCE_SIZE 256
#define QUERY_SIZE 256

int main(int argc, char *argv[]) {
    int32_t ret;
    
    haru_t haru;
    ret = haru_init(&haru);
    if (ret != 0) {
        printf("haru_init failed\n");
        return -1;
    }

    int32_t ref[REFERENCE_SIZE];
    int32_t query[QUERY_SIZE + 2];
    search_result_t results;

    memset(ref, 0, sizeof(ref));
    memset(query, 0, sizeof(query));

    for (int i = 0; i < REFERENCE_SIZE; i++) {
        ref[i] = rand() % 100;
    }

    for (int i = 0; i < QUERY_SIZE; i++) {
        query[i+2] = ref[i] + 1;
    }

    haru_process_dtw(&haru, ref, query, 256, &results);

    printf("results:\n\tqid:%d\n\tposition:%d\n\tscore:%d\n",
           results.qid, results.position, results.score);

    haru_release(&haru);
    return 0;
}