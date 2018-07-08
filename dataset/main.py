from __future__ import print_function
import sys
import os
import argparse
import exp


def parseArgs():
    parser = argparse.ArgumentParser()
    parser.add_argument('--table', nargs='+', type=str, help='database tables to be exported.',
                        default=None)
    parser.add_argument('--fields', nargs='+', type=str, help='fields to be exported.',
                        default=None)
    parser.add_argument('--dest', type=str, help='destination folder.',
                        default=None)
    parser.add_argument('--format', type=str, help='exported file format (avro, json).',
                        default='avro')
    parser.add_argument('--zip', type=bool, help='compress exported file.',
                        default=False)
    parser.add_argument('--train', type=bool, help='export relevant materials for training.',
                        default=False)
    parser.add_argument('options', nargs=argparse.REMAINDER)
    return parser.parse_args()


def run(args):
    args.dest = args.dest or '/Users/jx/ProgramData/mysql/avro'
    table = args.table
    args.table = None
    for tab in table:
        exp.export(tab, args)


if __name__ == '__main__':
    args = parseArgs()
    run(args)