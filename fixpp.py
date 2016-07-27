#!/usr/bin/env python

from xml.dom import minidom
import sys
import os
import re
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
        if not args.separator:
            # auto-detect separator using the sequence number field
            # that should always be present
            args.separator = re.search("([^0-9])34=", line).group(1)

        ret = []
        pairs = line.split(args.separator)[:-1]
        for pair in pairs:
            try:
                tag, value = pair.split('=')
                tag_entry = int_hashtable[tag]
                tag_name = str(tag_entry[0])
                if args.number:
                    tag_name += "(" + tag + ")"
                if tag_entry[1]:
                    value_name = str(tag_entry[1][value])
                    if args.number:
                        value_name += "(" + value + ")" 
                else:
                    value_name = value

                if args.long_format:
                    ret.append("%30s: %s" % (tag_name, value_name))
                else:
                    ret.append("%s=%s" % (tag_name, value_name))
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
    parser.add_argument("-l", action='store_true', default=False, dest='long_format', required=False, help='Use long format (separate line for every pair)')
    parser.add_argument("-n", action='store_true', default=False, dest='number', required=False, help='Show field numbers')
    parser.add_argument("-s", dest='separator', required=False, help='Use this separator instead of auto-detection')
    parser.add_argument("input_file", help='Input file (stdin by default)', nargs='?')
    args = parser.parse_args()

    print_messages(args)


if __name__ == "__main__":
    _main()
