#!/usr/bin/env python

from __future__ import absolute_import, print_function, unicode_literals

import argparse
import os
import re
import sys
from xml.dom import minidom

import appdirs
import multimap

try:
    from configparser import ConfigParser
except:
    from ConfigParser import SafeConfigParser as ConfigParser


class TagExpression:
    def __init__(self, tag):
        self.tag = tag

    def evaluate(self, msg_dict, stack, index):
        return (index - 1, self.tag in msg_dict)


class TagEqualExpression:
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value

    def evaluate(self, msg_dict, stack, index):
        return (index - 1, self.value in msg_dict.getall(self.tag))


class TagNotEqualExpression:
    def __init__(self, tag, value):
        self.tag = tag
        self.value = value

    def evaluate(self, msg_dict, stack, index):
        return (index - 1, self.value not in msg_dict.getall(self.tag))


class OperatorAnd:
    def evaluate(self, msg_dict, stack, index):

        index -= 1
        index, value1 = stack[index].evaluate(msg_dict, stack, index)
        index, value2 = stack[index].evaluate(msg_dict, stack, index)
        return (index, value1 and value2)


class OperatorOr:
    def evaluate(self, msg_dict, stack, index):

        index -= 1
        index, value1 = stack[index].evaluate(msg_dict, stack, index)
        index, value2 = stack[index].evaluate(msg_dict, stack, index)
        return (index, value1 or value2)


class OperatorNot:
    def evaluate(self, msg_dict, stack, index):
        index -= 1
        index, value = stack[index].evaluate(msg_dict, stack, index)
        return (index, not value)


def parse_expression(expression, stack, index):
    '''
    expression has the following syntax:
         expr = and_expr
              | and_expr '|' expr

         and_expr = simple_expr
              | simple_expr '&' and_expr

         simple_expr = tag
              | tag '=' value
              | tag '!=' value
              | '(' expr ')'
              | '!' simple_expr
    '''

    index = parse_and_expression(expression, stack, index)
    while index < len(expression) and expression[index] == "|":
        index = parse_and_expression(expression, stack, index + 1)
        stack.append(OperatorOr())

    return index


def parse_and_expression(expression, stack, index):
    index = parse_simple_expression(expression, stack, index)
    while index < len(expression) and expression[index] == "&":
        index = parse_simple_expression(expression, stack, index + 1)
        stack.append(OperatorAnd())

    return index


def parse_simple_expression(expression, stack, index):
    strlen = len(expression)
    if index < strlen and expression[index] == "(":
        index = parse_expression(expression, stack, index + 1)
        if index >= strlen or expression[index] != ')':
            raise ValueError("missing closing parenthesis: '%s'" % expression)
        # consume closing parenthesis
        index += 1
    elif index < strlen and expression[index] == "!":
        index = parse_simple_expression(expression, stack, index + 1)
        stack.append(OperatorNot())
    else:
        index = parse_const_expression(expression, stack, index)

    return index


def parse_const_expression(expression, stack, index):
    index, tag = parse_number(expression, index)
    if expression[index:index + 2] == "!=":
        index, value = parse_value(expression, index + 2)
        stack.append(TagNotEqualExpression(tag, value))
    elif expression[index:index + 1] == "=":
        index, value = parse_value(expression, index + 1)
        stack.append(TagEqualExpression(tag, value))
    else:
        stack.append(TagExpression(tag))

    return index


def parse_number(expression, index):
    start = index
    strlen = len(expression)
    while index < strlen and expression[index].isdigit():
        index += 1

    if index == start:
        raise ValueError("number expected in expression: '%s'" % expression)

    return (index, expression[start:index])


def parse_value(expression, index):
    start = index
    strlen = len(expression)
    while index < strlen and expression[index] not in (')', '&', '|'):
        index += 1

    return (index, expression[start:index])


def get_expression_stack(expression):
    stack = []
    index = parse_expression(expression, stack, 0)
    if index != len(expression):
        raise ValueError("failed to parse expression: '%s'" % expression)

    return stack


def eval_expression(filter_stack, msg_dict):
    index = len(filter_stack) - 1
    index, result = filter_stack[index].evaluate(msg_dict, filter_stack, index)

    return result


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
        config = ConfigParser()
        user_config_dir = appdirs.user_config_dir('fixpp', 'secwall')
        config.read(os.path.join(user_config_dir, 'fixpp.conf'))
        xmldoc = minidom.parse(config.get("quicklink", dict_file))
    except Exception as e:
        sys.stderr.write(e.message + '\nQuick link lookup failed for '
                         + dict_file + "\n")
        xmldoc = minidom.parse(dict_file)

    fields = xmldoc.getElementsByTagName('fields')

    field_list = fields[0].getElementsByTagName('field')

    int_hashtable = dict()

    for field in field_list:
        number = field.attributes['number'].value
        if number not in int_hashtable:
            int_hashtable[number] = [field.attributes['name'].value,
                                     parse_enums(field)]

    return int_hashtable


def make_tag_value_list(line, separator):
    def make_pair(token):
        if len(token) == 1:
            token.append(None)
        return token

    return [make_pair(token.split('='))
            for token in line.split(separator)[:-1]]


def print_messages(args):
    int_hashtable = parse_dict(args.dict_file)

    if args.input_file:
        log = open(args.input_file)
    else:
        log = sys.stdin
    if args.filter:
        stack = get_expression_stack(args.filter)
    else:
        stack = None

    for line in log:
        if not args.separator:
            # auto-detect separator using the sequence number field
            # that should always be present
            args.separator = re.search("([^0-9])34=", line).group(1)

        pairs = make_tag_value_list(line, args.separator)
        if stack and not eval_expression(stack, multimap.MultiMap(pairs)):
            continue

        ret = []
        for tag, value in pairs:
            if value is None:
                ret.append(tag)
            else:
                try:
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

                except Exception:
                    tag_name = tag
                    value_name = value

                if args.long_format:
                    ret.append("%30s: %s" % (tag_name, value_name))
                else:
                    ret.append("%s=%s" % (tag_name, value_name))

        if ret:
            if args.long_format:
                print(" \n".join(ret))
                print()
            else:
                print(",".join(ret))

    if args.input_file:
        log.close()


def _main():
    usage = "%(prog)s [-h] -d DICT_FILE [-l] [-n] [-e FILTER] " \
        "[-s SEPARATOR] [input_file]\n" \
        "Expression can be used for filtering messages, syntax:\n" \
        "    expr = and_expr\n" \
        "         | and_expr '|' expr\n" \
        "    and_expr = simple_expr\n" \
        "         | simple_expr '&' and_expr\n" \
        "    simple_expr = tag\n" \
        "         | tag '=' value\n" \
        "         | tag '!=' value\n" \
        "         | '(' expr ')'\n" \
        "         | '!' simple_expr\n"

    parser = argparse.ArgumentParser(description="FIX log pretty printer",
                                     usage=usage)
    parser.add_argument("-d", dest='dict_file', required=True,
                        help='Dictionary file path')
    parser.add_argument("-l", action='store_true', default=False,
                        dest='long_format', required=False,
                        help='Use long format (separate line for every pair)')
    parser.add_argument("-n", action='store_true', default=False,
                        dest='number', required=False,
                        help='Show field numbers')
    parser.add_argument("-e", action='store', dest='filter', required=False,
                        help='expression to filter the output')
    parser.add_argument("-s", dest='separator', required=False,
                        help='Use this separator instead of auto-detection')
    parser.add_argument("input_file", help='Input file (stdin by default)',
                        nargs='?')
    args = parser.parse_args()

    print_messages(args)


if __name__ == "__main__":
    _main()
