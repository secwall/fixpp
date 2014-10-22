#!/usr/bin/env python

from xml.dom import minidom
import sys
import os
import argparse
import appdirs
import ConfigParser


def parse_enums(xml_field):
    enum_list = xml_field.getElementsByTagName('value')

    enum_hashtable = dict()

    for element in enum_list:
        number = element.attributes['enum'].value
        if number not in enum_hashtable:
            enum_hashtable[number] = element.attributes['description'].value

    return enum_hashtable


def parse_dict(dict_file):
    try:
        config = ConfigParser.SafeConfigParser()
        user_config_dir = appdirs.user_config_dir('fixpp', 'secwall')
        config.read(os.path.join(user_config_dir, 'fixpp.conf'))
        xmldoc = minidom.parse(config.get("quicklink", dict_file))
    except Exception as e:
        sys.stderr.write(e.message + '\nQuick link lookup failed for ' + dict_file + "\n")
        xmldoc = minidom.parse(dict_file)

    fields = xmldoc.getElementsByTagName('fields')

    field_list = fields[0].getElementsByTagName('field')

    int_hashtable = dict()

    for field in field_list:
        number = field.attributes['number'].value
        if number not in int_hashtable:
            int_hashtable[number] = [field.attributes['name'].value, parse_enums(field)]

    return int_hashtable


def print_messages(args):
    int_hashtable = parse_dict(args.dict_file)

    if args.input_file:
        log = open(args.input_file)
    else:
        log = sys.stdin

    for line in log:
        ret = []
        pairs = line.split(args.separator)[:-1]
        for pair in pairs:
            try:
                tag, value = pair.split('=')
                tag_name = int_hashtable[tag]
                value_name = value
                if args.number:
                    tag_name[0] += "(" + tag + ")"
                if tag_name[1]:
                    value_name = tag_name[1][value]
                    if args.number:
                        value_name += "(" + value + ")" 

                ret.append(tag_name[0] + "=" + value_name)
            except Exception:
                ret.append(pair)

        if args.long_format:
            print " \n".join(ret)
            print
        else:
            print ",".join(ret)

    if args.input_file:
        log.close()


def _main():
    parser = argparse.ArgumentParser(description="FIX log pretty printer")
    parser.add_argument("-d", dest='dict_file', required=True, help='Dictionary file path')
    parser.add_argument("-i", dest='input_file', required=False, help='Input file (stdin by default)')
    parser.add_argument("-l", nargs='?', const=True, default=False, dest='long_format', required=False, help='Use long format (separate line for every pair)')
    parser.add_argument("-n", action='store_true', default=False, dest='number', required=False, help='Show field numbers')
    parser.add_argument("-s", default=chr(1), dest='separator', required=False, help='Use this separator instead of default')
    args = parser.parse_args()
    try:
        print_messages(args)
    except Exception:
        pass


if __name__ == "__main__":
    _main()
