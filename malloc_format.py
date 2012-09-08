#!/usr/bin/env python -u

"""This utility script takes combined stderr/stdout output from a binary
instrumented by malloc_instrument.so and calculates memory differentials
between actual output lines and periods of inactivity.
"""

__author__ = "JT Olds <jt@spacemonkey.com>"

import re
import sys
import Queue
import threading

OUTPUT_PREFIX = "|||||||||||||||||||||| "


def process(stream):
    queue = Queue.Queue()

    def readingThread(queue):
        for line in stream:
            queue.put(line)

    thread = threading.Thread(target=readingThread, args=(queue,))
    thread.daemon = True
    thread.start()

    sizes = {}
    current_total = 0
    last_total = 0

    malloc_re = re.compile(r'^malloc\(([0-9]+)\) = (.*)\n$')
    free_re = re.compile(r'^free\((.*)\)\n$')
    realloc_re = re.compile(r'^realloc\(([^,]*), ([0-9]+)\) = (.*)\n$')
    calloc_re = re.compile(r'^calloc\(([0-9]+), ([0-9]+)\) = (.*)\n$')

    while True:
        try:
            line = queue.get(timeout=1.0)
        except Queue.Empty:
            line = None
        if line is None or line[:len(OUTPUT_PREFIX)] != OUTPUT_PREFIX:
            diff = current_total - last_total
            last_total = current_total
            if diff != 0:
                sys.stdout.write("diff: %d bytes\n" % diff)
            if line is not None:
                sys.stdout.write(line)
            continue
        line = line[len(OUTPUT_PREFIX):]
        match = malloc_re.match(line)
        if match:
            size = int(match.group(1))
            address = match.group(2)
            current_total += size
            sizes[address] = size
            continue
        match = free_re.match(line)
        if match:
            address = match.group(1)
            if address in sizes:
                size = sizes[address]
                current_total -= size
                del sizes[address]
            continue
        match = realloc_re.match(line)
        if match:
            old_address = match.group(1)
            if old_address in sizes:
                size = sizes[old_address]
                current_total -= size
                del sizes[old_address]
            size = int(match.group(2))
            new_address = match.group(3)
            current_total += size
            sizes[new_address] = size
            continue
        match = calloc_re.match(line)
        if match:
            size = int(match.group(1)) * int(match.group(2))
            address = match.group(3)
            current_total += size
            sizes[address] = size
            continue
        sys.stdout.write("unhandled malloc line: %s" % line)


def main():
    process(sys.stdin)


if __name__ == "__main__":
    main()