#!/usr/bin/env python3

import argparse
import minorimpact
import scremeter
import sys

trigger_file = scremeter.trigger_file()
scremeter.turnWriteCacheOff()

def main():
    parser = argparse.ArgumentParser(description = 'scremeter trigger')
    parser.add_argument('--now', help = "Generate a trigger file and exit", action='store_true')
    parser.add_argument('--verbose', help = "Verbose output", action='store_true')
    args = parser.parse_args()


    if (args.now):
        with(open(trigger_file, 'w') as t):
            t.write("NOW")
        sys.exit()

    while (True):
        c = minorimpact.getChar(default='y', end='\n', prompt="trigger scremeter? (Y/n) ", echo=True).lower()
        if (c == 'y'):
            print("writing trigger file")
            with(open(trigger_file, 'w') as t):
                t.write("NOW")
        elif (c=='q'):
            sys.exit()

main()


